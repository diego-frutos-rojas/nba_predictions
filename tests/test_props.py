"""Tests del modelo de jugadores: sin fuga temporal, distribución coherente y modelo congelado solo con DEV."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nba_model import props, props_eval
from nba_model.data import add_rest

ROOT = Path(__file__).resolve().parents[1]


def _league(n_games=70, seed=1):
    """Liga sintética: 4 equipos de 9 jugadores, con descansos y alguna ausencia."""
    rng = np.random.default_rng(seed)
    teams = ["AAA", "BBB", "CCC", "DDD"]
    roster = {t: [1000 * (i + 1) + j for j in range(9)] for i, t in enumerate(teams)}
    games, boxes = [], []
    d0 = pd.Timestamp("2020-11-01")
    for i in range(n_games):
        h, a = rng.choice(teams, 2, replace=False)
        games.append({"game_id": str(i), "date": d0 + pd.Timedelta(days=i // 2), "season": 2021 if i < 50 else 2022,
                      "home": h, "away": a, "close_spread_home": float(rng.integers(-8, 9)) if i % 3 else np.nan,
                      "close_total": 220.0 if i % 3 else np.nan})
        for t in (h, a):
            for j, pid in enumerate(roster[t]):
                played = rng.random() > 0.12
                mins = float(rng.integers(8, 36)) if played else 0.0
                boxes.append({"game_id": str(i), "team": t, "pid": pid, "name": f"J{pid}", "pos": "G", "minutes": mins,
                              "played": played, "starter": j < 5, "pts": float(rng.poisson(0.5 * mins)),
                              "reb": float(rng.poisson(0.2 * mins)), "ast": float(rng.poisson(0.1 * mins)),
                              "fg3m": float(rng.poisson(0.05 * mins))})
    g = pd.DataFrame(games)
    g["home_pts"], g["away_pts"], g["neutral"] = 100, 98, False
    return add_rest(g), pd.DataFrame(boxes)


def test_props_features_no_leak():
    """Cambiar la caja de un partido futuro no puede alterar las variables de partidos anteriores."""
    g, b = _league()
    f1 = props.build_features(g, b)
    cut = "40"
    b2 = b.copy()
    later = b2.game_id.astype(int) >= int(cut)
    b2.loc[later, ["pts", "reb", "ast", "fg3m"]] = b2.loc[later, ["pts", "reb", "ast", "fg3m"]] * 3 + 7
    b2.loc[later, "minutes"] = b2.loc[later, "minutes"].clip(upper=20)
    f2 = props.build_features(g, b2)
    feat = [c for c in f1.columns if c not in ("minutes", "pts", "reb", "ast", "fg3m", "name", "date", "team", "opp")]
    a = f1[f1.game_id.astype(int) <= int(cut)].reset_index(drop=True)
    c = f2[f2.game_id.astype(int) <= int(cut)].reset_index(drop=True)
    assert len(a) > 100
    pd.testing.assert_frame_equal(a[feat], c[feat])
    # y sí cambian las posteriores (el test detectaría un modelo que ignorase los datos)
    assert not np.allclose(f1[f1.game_id.astype(int) > 45].rs_pts.values, f2[f2.game_id.astype(int) > 45].rs_pts.values)


def test_features_use_only_prior_games_of_player():
    g, b = _league()
    f = props.build_features(g, b)
    n_prev = b[b.played].assign(i=lambda d: d.game_id.astype(int)).sort_values("i").groupby("pid").cumcount()
    prior = dict(zip(zip(b[b.played].assign(i=lambda d: d.game_id.astype(int)).sort_values("i").game_id,
                         b[b.played].assign(i=lambda d: d.game_id.astype(int)).sort_values("i").pid), n_prev))
    assert all(prior[(gid, pid)] == n for gid, pid, n in zip(f.game_id, f.pid, f.n_prev))
    assert f.n_prev.min() >= props.ELIGIBLE_GAMES and f.min_fast.min() >= props.ELIGIBLE_MINUTES


def test_fit_and_predict_on_synthetic():
    g, b = _league(n_games=200, seed=3)
    f = props.build_features(g, b)
    m = props.fit(f)
    mu = props.predict(m, f)
    assert set(mu) == {"min", *props.ALL_MARKETS}
    assert np.allclose(mu["pra"], mu["pts"] + mu["reb"] + mu["ast"])
    assert (mu["min"] >= 1).all() and (mu["min"] <= 44).all() and (mu["fg3m"] > 0).all()
    assert abs((mu["pts"] - f.pts).mean()) < 0.5                       # sin sesgo en la propia muestra


@pytest.fixture(scope="module")
def frozen():
    return props.load_model(ROOT / "models/props_v1.json")


def test_frozen_model_file(frozen):
    meta = json.load(open(ROOT / "models/props_v1.json"))
    assert meta["tuned_on"] == "DEV 2014-2019"
    assert tuple(meta["minutes_features"]) == props.MIN_FEATURES and tuple(meta["stat_features"]) == props.STAT_FEATURES
    assert len(frozen["minutes"]) == len(props.MIN_FEATURES)
    assert all(len(frozen["stats"][s]) == len(props.STAT_FEATURES) for s in props.STATS)
    assert set(frozen["var"]) == set(props.ALL_MARKETS)


def test_dev_rows_never_include_val_or_test():
    f = pd.DataFrame({"season": [2012, 2013, 2014, 2019, 2020, 2022, 2027]})
    assert props_eval.dev_rows(f).season.tolist() == [2014, 2019]


@pytest.mark.parametrize("market,mu", [("pts", 24.3), ("reb", 6.1), ("ast", 0.8), ("fg3m", 0.15), ("pra", 41.0)])
def test_survival_is_a_distribution(frozen, market, mu):
    sv = props.survival(frozen, market, mu)
    assert sv[0] == 1.0 and all(x >= y - 1e-12 for x, y in zip(sv, sv[1:])) and sv[-1] < 1e-3
    assert math.isclose(sum(sv[1:]), mu, rel_tol=0.01, abs_tol=0.02)   # E[X] = suma de P(X >= k), k >= 1
    pmf = np.diff(-np.array(sv + [0.0]))
    var = float((pmf * (np.arange(len(pmf)) - mu) ** 2).sum())
    assert math.isclose(var, props.variance(frozen, market, mu), rel_tol=0.03)


def test_prob_over_scalar_vector_and_push(frozen):
    mu = np.array([3.2, 11.7, 25.4, 0.6])
    for market in ("pts", "fg3m", "ra"):
        for line in (0.5, 2.5, 10.5, 24.5, 12.0):
            vec = props.prob_over_vec(frozen, market, mu, np.full(len(mu), line))
            one = [props.prob_over(frozen, market, float(x), line) for x in mu]
            assert np.allclose(vec, one, atol=1e-9)
    assert props.prob_push(frozen, "pts", 20.0, 19.5) == 0.0
    p_over, p_push = props.prob_over(frozen, "pts", 20.0, 20.0), props.prob_push(frozen, "pts", 20.0, 20.0)
    assert 0 < p_push < 0.1 and math.isclose(p_over + p_push, props.prob_over(frozen, "pts", 20.0, 19.5))
    assert props.prob_over(frozen, "pts", 25.0, 19.5) > props.prob_over(frozen, "pts", 20.0, 19.5) > props.prob_over(frozen, "pts", 20.0, 24.5)


def test_hierarchical_shrinkage_and_play_weight():
    tr = props.PropsTracker()
    rows = [(1, "Pivot", "C", 30.0, True, True, 12.0, 10.0, 1.0, 0.0), (2, "Tirador", "G", 30.0, True, True, 15.0, 2.0, 3.0, 4.0),
            (3, "Fondo", "G", 0.0, False, False, 0.0, 0.0, 0.0, 0.0)]
    miss = {k: 0.0 for k in ("min",) + props.STATS}
    for _ in range(40):
        tr.update_team_game("AAA", "BBB", 2021, rows, miss)
    assert tr.rate(tr.players[1], "fg3m", fast=False) < 0.002 < tr.league["fg3m"]      # el pívot no hereda triples de la liga
    assert tr.rate(tr.players[2], "fg3m", fast=False) > 0.12
    assert tr.play_weight("AAA", 1) == 1.0 and tr.play_weight("AAA", 3) == 0.0
    assert 3 not in tr.players and set(tr.candidates("AAA", 2021)) == {1, 2}
    assert tr.lineup_minutes({1: 1.0, 2: 0.5}) == pytest.approx(45.0)
