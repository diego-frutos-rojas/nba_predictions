"""Tests del código que produce las conclusiones: metrics, baselines, evaluate, props_eval y tune (ROADMAP, fase 2).

Todo con valores conocidos a mano o datos sintéticos: no necesitan data/raw, así que también corren en CI."""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_core import _games
from test_props import _league

from nba_model import evaluate, props, props_eval, tune
from nba_model.baselines import SIGMA_MARKET, market_prob, ridge_v0_walk_forward
from nba_model.data import add_rest
from nba_model.elo import Params
from nba_model.metrics import (
    accuracy,
    brier,
    calibration_error,
    calibration_table,
    log_loss,
    logit,
    paired_bootstrap_diff,
    per_game_logloss,
    sigmoid,
)
from nba_model.ratings import SIGMA_V0

ROOT = Path(__file__).resolve().parents[1]
LN2 = math.log(2)


# ----------------------------------------------------------------------------------------------- metrics (2.1)
def test_log_loss_known_values():
    assert math.isclose(log_loss([0.5, 0.5, 0.5], [1, 0, 1]), LN2)
    assert math.isclose(log_loss([0.8, 0.2], [1, 0]), -math.log(0.8))
    assert log_loss([1.0, 0.0], [1, 0]) < 1e-8                      # predictor perfecto
    assert math.isfinite(log_loss([0.0], [1]))                      # el recorte evita el infinito
    assert log_loss([0.9], [0]) > log_loss([0.6], [0])              # castiga más cuanto más seguro y equivocado


def test_per_game_logloss_is_consistent_with_mean():
    p, y = np.array([0.1, 0.4, 0.7, 0.95]), np.array([0, 1, 1, 1])
    pg = per_game_logloss(p, y)
    assert pg.shape == (4,) and math.isclose(pg.mean(), log_loss(p, y))
    assert math.isclose(pg[2], -math.log(0.7))


def test_brier_and_accuracy_trivial_cases():
    assert brier([1, 0, 1], [1, 0, 1]) == 0.0
    assert brier([0, 1], [1, 0]) == 1.0
    assert math.isclose(brier([0.5, 0.5], [1, 0]), 0.25)
    assert accuracy([0.9, 0.2, 0.6, 0.4], [1, 0, 0, 1]) == 0.5
    assert accuracy([0.5], [1]) == 0.0                              # 0,5 exacto no cuenta como acierto del local


def test_logit_and_sigmoid_are_inverse():
    p = np.array([0.02, 0.3, 0.5, 0.77, 0.99])
    assert np.allclose(sigmoid(logit(p)), p)
    assert logit(0.5) == 0.0 and sigmoid(0.0) == 0.5
    assert np.isfinite(logit([0.0, 1.0])).all()


def test_calibration_error_known_values():
    assert calibration_error([0.0, 1.0, 1.0, 0.0], [0, 1, 1, 0]) == 0.0          # predictor perfecto
    assert math.isclose(calibration_error(np.full(10, 0.8), [1] * 6 + [0] * 4), 0.2)
    # dos tramos: 0,25 (real 0,5 -> error 0,25) y 0,75 (real 0,75 -> error 0), mitad de la muestra cada uno
    p = np.array([0.25] * 4 + [0.75] * 4)
    y = np.array([1, 1, 0, 0, 1, 1, 1, 0])
    assert math.isclose(calibration_error(p, y), 0.125)


def test_calibration_table_bins():
    p = np.array([0.1, 0.15, 0.55, 1.0])
    tab = calibration_table(p, [0, 1, 1, 1])
    assert [r["bin"] for r in tab] == ["0.0-0.2", "0.5-0.6", "0.8-1.0"]         # los tramos vacíos no salen; 1,0 entra en el último
    assert sum(r["n"] for r in tab) == 4
    assert math.isclose(tab[0]["pred"], 0.125) and tab[0]["real"] == 0.5


def test_paired_bootstrap_properties():
    rng = np.random.default_rng(1)
    a, b = rng.random(300), rng.random(300) + 0.2
    d, lo, hi = paired_bootstrap_diff(a, b)
    assert math.isclose(d, (a - b).mean()) and lo < d < hi and hi < 0       # A claramente mejor
    assert paired_bootstrap_diff(a, b) == (d, lo, hi)                       # determinista con la semilla por defecto
    assert paired_bootstrap_diff(a, b, seed=1) != (d, lo, hi)
    assert paired_bootstrap_diff(a, a) == (0.0, 0.0, 0.0)


# --------------------------------------------------------------------------------------------- baselines (2.2)
def test_market_prob_known_values():
    assert market_prob([0.0])[0] == 0.5
    s = np.array([-12.5, -3.0, 1.5, 7.0])
    assert np.allclose(market_prob(s) + market_prob(-s), 1.0)              # simetría
    assert (np.diff(market_prob(s)) < 0).all()                             # más spread a favor del visitante, menos prob local
    assert market_prob([-5.0])[0] > 0.5                                    # spread negativo = local favorito
    assert math.isclose(market_prob([-SIGMA_MARKET])[0], 0.8413447, abs_tol=1e-6)   # una sigma
    out = market_prob([np.nan, -2.0, None])
    assert np.isnan(out[0]) and np.isnan(out[2]) and np.isfinite(out[1])    # sin línea -> NaN, no 0,5


def _v0_frame(n=40, seed=0):
    g = _games(n, seed)
    g.loc[n // 2:, "season"] = 2022
    return g[["season", "date", "home", "away", "home_pts", "away_pts", "neutral"]].copy()


def test_ridge_v0_first_day_and_neutral():
    from statistics import NormalDist
    g = _v0_frame()
    g.loc[0, "neutral"] = True
    p = ridge_v0_walk_forward(g)
    assert ((p > 0) & (p < 1)).all()
    assert p[0] == 0.5                                                      # sin partidos previos y campo neutral
    first_s2 = g.index[g.season == 2022][0]
    assert math.isclose(p[first_s2], NormalDist().cdf(3.0 / SIGMA_V0))      # cada temporada empieza de cero: solo HCA


def test_ridge_v0_uses_only_the_past():
    g = _v0_frame()
    base = ridge_v0_walk_forward(g)
    g2 = g.copy()
    g2.loc[25, ["home_pts", "away_pts"]] = [150, 60]
    alt = ridge_v0_walk_forward(g2)
    assert np.array_equal(base[:26], alt[:26])                              # el pasado (y el propio partido) no cambian
    assert not np.array_equal(base[26:], alt[26:])


# ---------------------------------------------------------------------------------------------- evaluate (2.3)
def test_logit_fit_recovers_coefficients():
    rng = np.random.default_rng(0)
    X = np.c_[np.ones(20000), rng.normal(size=20000)]
    y = (rng.random(20000) < sigmoid(X @ np.array([0.3, -1.2]))).astype(float)
    w = evaluate._logit_fit(X, y)
    assert np.allclose(w, [0.3, -1.2], atol=0.06)


def _roi_frame(margins, spreads, model_margins):
    return pd.DataFrame({"home_margin": margins, "close_spread_home": spreads, "m_v2": model_margins})


def test_roi_at_minus_110():
    # mercado: local -4 (spread -4). El modelo dice +10 -> apuesta al local en todos.
    n = 10
    win = _roi_frame([10] * n, [-4.0] * n, [10.0] * n)
    m = np.ones(n, bool)
    assert math.isclose(evaluate._roi(win, m, 1)["roi"], 100 / 110)
    half = _roi_frame([10] * 5 + [0] * 5, [-4.0] * n, [10.0] * n)             # 50 % de acierto
    r = evaluate._roi(half, m, 1)
    assert r["n"] == n and math.isclose(r["roi"], (100 / 110 - 1) / 2) and math.isclose(r["roi"], -0.0454545, abs_tol=1e-6)
    assert r["lo"] < r["roi"] < r["hi"]
    push = _roi_frame([4] * n, [-4.0] * n, [10.0] * n)                        # empate con la línea: se devuelve
    assert evaluate._roi(push, m, 1)["roi"] == 0.0
    away = _roi_frame([0] * n, [-4.0] * n, [-10.0] * n)                       # el modelo va con el visitante y cubre
    assert math.isclose(evaluate._roi(away, m, 1)["roi"], 100 / 110)


def test_roi_threshold_selects_bets():
    g = _roi_frame([10, 10, 10, 10], [-4.0] * 4, [4.5, 6.5, 9.5, 1.0])        # discrepancias: +0,5 +2,5 +5,5 -3
    m = np.ones(4, bool)
    assert [evaluate._roi(g, m, t)["n"] for t in (1, 2, 3, 5)] == [3, 3, 1, 1]
    assert evaluate._roi(g, np.array([True, False, False, False]), 0)["n"] == 1    # respeta la máscara de bloque


def _eval_dataset(per_season=30, seed=0):
    """Partidos sintéticos 2012-2027 con spread informativo, descansos y disponibilidad."""
    rng = np.random.default_rng(seed)
    teams = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    strength = dict(zip(teams, [6, 3, 1, -1, -3, -6], strict=True))
    rows = []
    for season in range(2012, 2028):
        d0 = pd.Timestamp(f"{season - 1}-11-01")
        for i in range(per_season):
            h, a = rng.choice(teams, 2, replace=False)
            exp = strength[h] - strength[a] + 2.5
            margin = int(round(exp + rng.normal(0, 12))) or 1
            spread = np.nan if i % 7 == 0 else -round((exp + rng.normal(0, 2)) * 2) / 2
            rows.append({"game_id": f"{season}_{i}", "date": d0 + pd.Timedelta(days=i), "season": season, "home": h, "away": a,
                         "home_pts": 100 + margin, "away_pts": 100, "neutral": False, "close_spread_home": spread,
                         "avail_home": float(rng.normal(0, 20)), "avail_away": float(rng.normal(0, 20))})
    g = pd.DataFrame(rows)
    g["home_margin"] = g.home_pts - g.away_pts
    return add_rest(g)


@pytest.fixture(scope="module")
def eval_res():
    g = _eval_dataset()
    return g, evaluate.run_full_evaluation(g, Params())


def test_full_evaluation_structure_and_blocks(eval_res):
    g, res = eval_res
    assert res["n_games"] == 30 * 15                                         # 2027 queda fuera
    assert set(res["blocks"]) == {"DEV", "VAL", "TEST"}
    n = {k: v["v2_elo"]["n"] for k, v in res["blocks"].items()}
    assert n == {"DEV": 180, "VAL": 60, "TEST": 150}                         # 6, 2 y 5 temporadas
    for row in res["blocks"].values():
        assert row["mercado"]["n"] < row["v2_elo"]["n"]                      # el mercado solo cuenta partidos con línea
        for v in row.values():
            assert 0 < v["log_loss"] < 2 and 0 <= v["brier"] <= 1 and 0 <= v["accuracy"] <= 1 and 0 <= v["ece"] <= 1
        assert row["siempre_local"]["mae_margin"] is None and row["mercado"]["mae_margin"] > 0
    assert set(res["per_season_test"]) == {2022, 2023, 2024, 2025, 2026}
    assert set(res["roi_spread_-110"]) == {"1", "2", "3", "4", "5"}
    for v in res["test_bootstrap"].values():
        assert v["lo"] <= v["diff"] <= v["hi"]
    assert math.isclose(res["blend"]["test_ll_mercado"], res["blocks"]["TEST"]["mercado"]["log_loss"])


def test_full_evaluation_always_home_baseline_by_hand(eval_res):
    g, res = eval_res
    y = (g.home_margin > 0).astype(int).values
    S = g.season.values
    rate = y[(S >= 2012) & (S <= 2019)].mean()                               # tasa local: solo temporadas hasta 2019
    t = (S >= 2022) & (S <= 2026)
    assert math.isclose(res["blocks"]["TEST"]["siempre_local"]["log_loss"], log_loss(np.full(t.sum(), rate), y[t]))


def test_full_evaluation_dev_is_blind_to_test(eval_res):
    """Lo que se ajusta o mide en DEV no puede depender de lo que pase en VAL/TEST."""
    g, res = eval_res
    g2 = g.copy()
    late = g2.season >= 2020
    g2.loc[late, "home_margin"] = -g2.loc[late, "home_margin"]
    g2.loc[late, ["home_pts", "away_pts"]] = g2.loc[late, ["away_pts", "home_pts"]].values
    res2 = evaluate.run_full_evaluation(g2, Params())
    assert res2["blocks"]["DEV"] == res["blocks"]["DEV"]
    assert res2["blend"]["coef_dev"] == res["blend"]["coef_dev"]
    assert res2["gap_info"]["DEV"] == res["gap_info"]["DEV"]
    assert res2["contrastes_mercado"]["DEV"] == res["contrastes_mercado"]["DEV"]
    assert res2["blocks"]["TEST"] != res["blocks"]["TEST"]


def test_results_markdown_and_load_params(eval_res):
    md = evaluate.results_markdown(eval_res[1])
    assert md.count("| DEV |") == 4 and md.count("| TEST |") == 4 and "v2_menos_mercado" in md and "| 5 |" in md
    p = evaluate.load_params(ROOT / "models/params_v2.json")
    assert isinstance(p, Params) and 0 < p.k < 1


# -------------------------------------------------------------------------------------------- props_eval (2.4)
def _bets_frame(p_over, y, line=20.5, over=-110, under=-110, fair=0.5):
    n = len(y)
    return pd.DataFrame({"p_over": p_over, "fair_over": fair, "over": over, "under": under, "y": y, "line": line,
                         "game_id": [str(i) for i in range(n)]})


def test_fair_over_removes_vig():
    assert props_eval._fair_over(-110, -110) == 0.5
    assert props_eval._fair_over(-150, 120) > 0.5
    assert math.isclose(props_eval._fair_over(-150, 120) + props_eval._fair_over(120, -150), 1.0)


def test_props_bets_roi_at_minus_110():
    half = props_eval._bets(_bets_frame([0.6] * 4, [25, 25, 10, 10]), 0.0)    # siempre over; acierta 2 de 4
    assert half["n"] == 4 and half["acierto"] == 0.5 and half["over_pct"] == 1.0
    assert math.isclose(half["roi"], -0.0454545, abs_tol=1e-6)                # 50 % a -110 -> -4,55 %
    assert half["lo"] <= half["roi"] <= half["hi"]
    allwin = props_eval._bets(_bets_frame([0.6] * 4, [25] * 4), 0.0)
    assert math.isclose(allwin["roi"], 100 / 110) and allwin["lo"] == allwin["hi"]
    under = props_eval._bets(_bets_frame([0.3] * 3, [10, 10, 10]), 0.0)       # modelo por debajo de la casa -> under
    assert under["over_pct"] == 0.0 and math.isclose(under["roi"], 100 / 110)
    plus = props_eval._bets(_bets_frame([0.6] * 2, [25, 10], over=150), 0.0)  # precio positivo: +1,5 y -1
    assert math.isclose(plus["roi"], 0.25)


def test_props_bets_threshold_and_push():
    t = _bets_frame([0.52, 0.58, 0.70], [25, 25, 25])
    assert [props_eval._bets(t, thr).get("n") for thr in (0.0, 0.03, 0.10, 0.30)] == [3, 2, 1, 0]
    push = props_eval._bets(_bets_frame([0.6, 0.6], [20, 25], line=20.0), 0.0)   # un empate (devuelve) y un acierto
    assert push["n"] == 2 and push["acierto"] == 1.0 and math.isclose(push["roi"], (100 / 110) / 2)


def test_edge_thresholds_are_frozen():
    assert props_eval.EDGE_THRESHOLDS == (0.0, 0.03, 0.06, 0.10)              # pre-fijados: no moverlos mirando resultados


@pytest.fixture(scope="module")
def props_fx():
    g, b = _league(n_games=260, seed=5)
    g["season"] = np.where(np.arange(len(g)) < 130, 2019, 2023)               # un bloque DEV y uno TEST
    f = props.build_features(g, b)
    return f, props.fit(props_eval.dev_rows(f))


def test_block_metrics_and_calibration_on_synthetic(props_fx):
    f, model = props_fx
    bm = props_eval.block_metrics(f, model, n_boot=50)
    assert set(bm) == {"DEV", "TEST"}                                          # los bloques vacíos no aparecen
    assert bm["DEV"]["n"] + bm["TEST"]["n"] == len(f)
    for blk in bm.values():
        for m in props.ALL_MARKETS:
            x = blk[m]
            assert x["modelo"]["rmse"] >= x["modelo"]["mae"] > 0
            d = x["dif_mse_vs_temporada"]
            assert d["lo"] <= d["hi"]
            assert math.isclose(d["media"], x["modelo"]["rmse"] ** 2 - x["temporada"]["rmse"] ** 2, abs_tol=1e-9)
    assert props_eval.block_metrics(f, model, n_boot=50) == bm                 # determinista
    cal = props_eval.calibration(f, model)
    for blk in cal.values():
        for m in props.ALL_MARKETS:
            assert blk[m]["n"] > 0 and 0 <= blk[m]["ece"] <= 1 and blk[m]["log_loss_tasa_base"] <= LN2 + 1e-9


def test_market_test_and_markdown_on_synthetic(props_fx):
    f, model = props_fx
    t = f[f.season == 2023]
    lines = pd.concat([pd.DataFrame({"game_id": t.game_id.values, "pid": t.pid.values, "market": m,
                                     "line": np.floor(props.actual(t, m)) + np.where(np.arange(len(t)) % 2, 1.5, -0.5),
                                     "over": np.where(np.arange(len(t)) % 3, -110, -130),      # precios variados, como los reales
                                     "under": np.where(np.arange(len(t)) % 3, -110, 105), "side_ok": np.arange(len(t)) % 5 != 0})
                       for m in ("pts", "reb")], ignore_index=True)
    mt = props_eval.market_test(f, lines, model)
    assert mt["n"] == 2 * len(t) and set(mt["error"]) == {"pts", "reb"}
    assert math.isclose(mt["error"]["pts"]["over_real"], 0.5, abs_tol=0.01)    # las líneas se pusieron mitad encima y mitad debajo
    assert math.isclose(mt["error"]["pts"]["mae_linea"], 1.0, abs_tol=0.01)
    assert set(mt["apuestas"]) == {"0.00", "0.03", "0.06", "0.10"}
    ns = [mt["apuestas"][k]["n"] for k in ("0.00", "0.03", "0.06", "0.10")]
    assert ns == sorted(ns, reverse=True) and ns[0] <= mt["n"] * 0.81          # umbral más alto = menos apuestas; side_ok=False fuera
    assert mt["blend"]["n"] == ns[0]
    assert props_eval.market_test(f, lines.iloc[:0], model) == {"n": 0}
    md = props_eval.results_markdown({"bloques": props_eval.block_metrics(f, model, n_boot=20),
                                      "calibracion": props_eval.calibration(f, model), "mercado": mt})
    assert "## 3. Contra las líneas de cierre" in md and "| TEST | Puntos |" in md


# -------------------------------------------------------------------------------------------------- tune (2.5)
def test_latin_hypercube_is_bounded_stratified_and_seeded():
    names = tuple(tune.BOUNDS)
    pts = tune.latin_hypercube(50, names, seed=3)
    assert pts.shape == (50, len(names))
    for j, k in enumerate(names):
        lo, hi = tune.BOUNDS[k]
        assert (pts[:, j] >= lo).all() and (pts[:, j] <= hi).all()
        strata = np.floor((pts[:, j] - lo) / (hi - lo) * 50).astype(int)
        assert sorted(strata) == list(range(50))                               # un punto por estrato
    assert np.array_equal(pts, tune.latin_hypercube(50, names, seed=3))
    assert not np.array_equal(pts, tune.latin_hypercube(50, names, seed=4))


def test_average_top_is_mean_of_best_5_percent():
    names = ("k", "carry")
    res = pd.DataFrame({"k": np.linspace(0.02, 0.12, 200), "carry": np.linspace(0.95, 0.40, 200), "ll": np.linspace(0.60, 0.70, 200)})
    p = tune.average_top(res, names=names)
    assert math.isclose(p.k, res.k[:10].mean()) and math.isclose(p.carry, res.carry[:10].mean())   # 5 % de 200 = 10
    assert p.k != res.k[0]                                                     # promedia: no se queda con el mejor
    small = tune.average_top(res.head(20), names=names)                        # mínimo 5 configuraciones
    assert math.isclose(small.k, res.k[:5].mean())
    assert p.hca0 == Params().hca0                                             # lo que no se busca queda por defecto


def test_random_search_is_deterministic_with_seed():
    g = _games(80, seed=2)
    mask = np.arange(len(g)) >= 20
    a = tune.random_search(g, mask, n=12, seed=7, names=("k", "hca0"))
    b = tune.random_search(g, mask, n=12, seed=7, names=("k", "hca0"))
    pd.testing.assert_frame_equal(a, b)
    assert a.ll.is_monotonic_increasing and len(a) == 12
    assert tune.average_top(a, names=("k", "hca0")) == tune.average_top(b, names=("k", "hca0"))
    assert not a.equals(tune.random_search(g, mask, n=12, seed=8, names=("k", "hca0")))
    best = Params(k=float(a.k[0]), hca0=float(a.hca0[0]))
    assert math.isclose(tune.objective(g, best, mask), a.ll[0])
