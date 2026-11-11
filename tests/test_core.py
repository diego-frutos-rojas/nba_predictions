import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nba_model.availability import AvailabilityTracker
from nba_model.data import _repair_sbr_lines, add_rest, rest_days_before
from nba_model.elo import Params, run_elo
from nba_model.injuries import PLAY_PROB
from nba_model.market import cover_prob_home, needed_adjustment_pts, reference_prob
from nba_model.metrics import log_loss, paired_bootstrap_diff
from nba_model.odds import american_to_decimal, american_to_implied, expected_value, kelly_fraction, remove_vig

ROOT = Path(__file__).resolve().parents[1]


def _games(n=60, seed=0):
    rng = np.random.default_rng(seed)
    teams = ["AAA", "BBB", "CCC", "DDD"]
    rows = []
    d0 = pd.Timestamp("2020-11-01")
    for i in range(n):
        h, a = rng.choice(teams, 2, replace=False)
        rows.append({"game_id": str(i), "date": d0 + pd.Timedelta(days=i), "season": 2021, "home": h, "away": a,
                     "home_pts": int(rng.integers(90, 120)), "away_pts": int(rng.integers(90, 120)), "neutral": False})
    df = pd.DataFrame(rows)
    df["home_margin"] = df.home_pts - df.away_pts
    return add_rest(df)


def test_odds_basics():
    assert math.isclose(american_to_implied(-110), 110 / 210)
    assert math.isclose(american_to_decimal(+150), 2.5)
    ph, pa, vig = remove_vig(american_to_implied(-110), american_to_implied(-110))
    assert math.isclose(ph, 0.5) and vig > 0
    assert expected_value(0.5, +100) == 0 and kelly_fraction(0.4, +100) == 0.0


def test_reference_priority():
    both = {"odds": {"home": 324, "away": -432}, "spread_home_margin": -9.5, "provider_home_prob": 0.2}
    assert reference_prob(both)["kind"] == "ml_no_vig"
    assert reference_prob({"odds": {}, "spread_home_margin": 15.5, "provider_home_prob": 0.9})["kind"] == "spread_converted"
    ref = reference_prob({"odds": {}, "provider_home_prob": 0.47})
    assert ref["kind"] == "provider" and not ref["is_market"]


def test_market_helpers():
    need = needed_adjustment_pts(-2.2, 0.225, 12.0)
    from nba_model.odds import normal_cdf
    assert math.isclose(normal_cdf((-2.2 + need) / 12.0), 0.225, abs_tol=1e-6)
    assert math.isclose(cover_prob_home(-5.5, -5.5), 0.5)


def test_sbr_swap_repair():
    a = pd.DataFrame({"home_close_spread": [178.0, -4.5, 197.5], "close_over_under": [4.0, 190.0, 3.0],
                      "home_close_ml": [155, -200, -150], "away_close_ml": [-175, 170, 130]})
    r = _repair_sbr_lines(a)
    assert r.home_close_spread.tolist() == [4.0, -4.5, -3.0]     # signo sale del favorito de la moneyline
    assert r.close_over_under.tolist() == [178.0, 190.0, 197.5]


def test_rest_days_have_no_lookahead():
    df = pd.DataFrame({"game_id": ["1", "2", "3"], "season": 2021, "date": pd.to_datetime(["2020-11-01", "2020-11-02", "2020-11-06"]),
                       "home": ["A", "A", "A"], "away": ["B", "C", "B"], "home_pts": 1, "away_pts": 0, "neutral": False})
    r = add_rest(df)
    assert r.rest_home.tolist() == [7, 1, 4]          # primer partido de la temporada = 7; ayer = 1; 4 días
    assert r.rest_away.tolist() == [7, 7, 5]


def test_elo_predictions_use_only_the_past():
    g = _games()
    p = Params()
    base = run_elo(g, p)["margin_pred"]
    g2 = g.copy()
    k = 40
    g2.loc[k, "home_pts"] += 40                         # cambiamos el resultado del partido 40
    g2["home_margin"] = g2.home_pts - g2.away_pts
    alt = run_elo(g2, p)["margin_pred"]
    assert np.allclose(base[: k + 1], alt[: k + 1])    # nada hasta el partido 40 (incluido) cambia
    assert not np.allclose(base[k + 1:], alt[k + 1:])   # lo posterior sí


def test_elo_hca_adapts_and_probs_valid():
    g = _games(200, seed=1)
    out = run_elo(g, Params())
    assert ((out["prob_home"] > 0) & (out["prob_home"] < 1)).all()
    assert out["state"].var > 0


def test_elo_avail_clips_each_side_independently():
    """Regresión: con avail_home > AVAIL_CLIP el término del visitante se descartaba (precedencia del condicional)."""
    from nba_model.elo import AVAIL_CLIP
    g = _games(1)
    p = Params(avail=0.05)
    base = run_elo(g.assign(avail_home=0.0, avail_away=0.0), p)["margin_pred"][0]
    for ah, aa in ((AVAIL_CLIP + 15, -30.0), (-AVAIL_CLIP - 15, 20.0), (25.0, AVAIL_CLIP + 15), (10.0, -5.0)):
        m = run_elo(g.assign(avail_home=ah, avail_away=aa), p)["margin_pred"][0]
        want = p.avail * (max(-AVAIL_CLIP, min(AVAIL_CLIP, ah)) - max(-AVAIL_CLIP, min(AVAIL_CLIP, aa)))
        assert math.isclose(m - base, want), (ah, aa)


def test_availability_signs():
    tr = AvailabilityTracker()
    season = 2021
    star, role = 1, 2
    for i in range(12):                                  # la estrella juega siempre: T habitual estable
        d, T = tr.delta_for("AAA", season, {star, role})
        tr.update("AAA", season, [(star, 34.0, True, 30.0), (role, 20.0, True, 9.0)], T)
    assert abs(tr.expected_delta("AAA", season, {})) < 1e-6                       # todos disponibles => ~0
    assert tr.expected_delta("AAA", season, {star: PLAY_PROB["out"]}) < -20       # estrella fuera => delta muy negativo
    assert tr.expected_delta("AAA", season, {star: PLAY_PROB["questionable"]}) > tr.expected_delta("AAA", season, {star: 0.0})


def test_metrics():
    assert log_loss([0.999, 0.001], [1, 0]) < 0.01
    d, lo, hi = paired_bootstrap_diff(np.array([0.5, 0.6, 0.7]), np.array([0.6, 0.7, 0.8]))
    assert lo <= d <= hi and d < 0


def test_frozen_params_load():
    import json
    meta = json.load(open(ROOT / "models/params_v2.json"))
    p = Params(**meta["params"])
    assert 0 < p.k < 0.2 and 0 < p.carry < 1 and p.w_s == 0.0


@pytest.mark.skipif(not (ROOT / "data/raw/sbr.json").exists(), reason="datos crudos no descargados (scripts/run_pipeline.py --fetch)")
def test_real_dataset_integrity():
    from nba_model.data import build_games
    g = build_games(ROOT / "data/raw")
    assert len(set(g.home) | set(g.away)) == 30
    x = g[(g.season >= 2014) & (g.season <= 2019)].dropna(subset=["close_spread_home"])
    assert np.corrcoef(-x.close_spread_home, x.home_margin)[0, 1] > 0.4     # líneas reparadas: correlación esperada ~0.46
    assert (g.close_spread_home.abs().dropna() < 40).all()


def test_rest_days_before_convention():
    df = pd.DataFrame({"date": pd.to_datetime(["2020-11-01", "2020-11-05"]), "home": ["A", "A"], "away": ["B", "C"]})
    assert rest_days_before(df, "A", "2020-11-06") == 1          # jugó ayer = back-to-back
    assert rest_days_before(df, "A", "2020-11-08") == 3
    assert rest_days_before(df, "Z", "2020-11-08") == 7          # sin partidos previos
    assert rest_days_before(df, "A", "2020-11-05") == 4          # ignora el propio día


@pytest.mark.skipif(not (ROOT / "data/raw/sbr.json").exists(), reason="datos crudos no descargados")
def test_web_state_schema_and_parity_reference():
    from nba_model.webstate import build_web_state
    s = build_web_state(ROOT, ROOT / "data/snapshot_2026-11-10/market_2026-11-10.json", ROOT / "data/snapshot_2026-11-10/games.csv", "2026-11-10")
    assert len(s["teams"]) == 30 and s["model"]["sigma"] > 5 and 0 < s["model"]["hca"] < 4
    assert all(len(t["roster"]) >= 5 for t in s["teams"].values())
    assert len(s["parity"]) == len(s["slate"]) == 6
    assert all(abs(p["margin"]) < 30 and 0 < p["prob_home"] < 1 for p in s["parity"])
