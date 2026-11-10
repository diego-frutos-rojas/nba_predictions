"""Evaluación completa y reproducible (bloques DEV / VAL / TEST, mercado, blend, apuestas simuladas)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import numpy.linalg as la
import pandas as pd

from .availability import compute_availability, load_boxes
from .baselines import market_prob, ridge_v0_walk_forward
from .data import add_rest, build_games
from .elo import Params, run_elo
from .metrics import (accuracy, brier, calibration_error, calibration_table, log_loss, logit,
                      paired_bootstrap_diff, per_game_logloss, sigmoid)

BLOCKS = {"DEV": (2014, 2019), "VAL": (2020, 2021), "TEST": (2022, 2026)}


def load_params(path: str | Path) -> Params:
    return Params(**json.load(open(path))["params"])


def prepare_dataset(raw_dir: str | Path, return_tracker: bool = False, extra_results: pd.DataFrame | None = None, with_names: bool = False):
    """Resultados + líneas de cierre + descanso + disponibilidad (todo sin fuga de información).

    `extra_results`: partidos recientes aún no publicados en ESPN (columnas date, home, away, home_pts, away_pts)."""
    g = build_games(raw_dir)
    if extra_results is not None and len(extra_results):
        ex = extra_results.copy()
        keep = []
        cur = g[g.season == g.season.max()]
        for h, a in zip(ex.home, ex.away):
            keep.append(not ((cur.home == h) & (cur.away == a)).any())      # evita duplicar partidos ya presentes
        ex = ex[np.array(keep)]
        if len(ex):
            ex["game_id"] = ["extra_%d" % i for i in range(len(ex))]
            ex["season"] = int(g.season.max()); ex["neutral"] = False; ex["source"] = "manual"
            for c in ("close_spread_home", "close_ml_home", "close_ml_away", "close_total"):
                ex[c] = np.nan
            ex["home_margin"] = ex.home_pts - ex.away_pts
            g = pd.concat([g, ex[g.columns.intersection(ex.columns)]], ignore_index=True)
    g = add_rest(g)
    boxes = load_boxes(raw_dir, with_names=with_names)
    out = compute_availability(g, boxes, return_tracker=return_tracker)
    return (out[0], out[1], boxes) if return_tracker else out


def _logit_fit(X, y, iters=40):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        mu = sigmoid(X @ w)
        W = mu * (1 - mu)
        w += la.solve(X.T @ (X * W[:, None]) + 1e-9 * np.eye(X.shape[1]), X.T @ (y - mu))
    return w


def _roi(g, m, thr):
    mm = -g.close_spread_home.values[m]
    gap = g.m_v2.values[m] - mm
    mar, sp = g.home_margin.values[m], g.close_spread_home.values[m]
    side = np.where(gap > thr, 1, np.where(gap < -thr, -1, 0))
    cover = np.sign(mar + sp)
    sel = side != 0
    res = np.where(cover[sel] == 0, 0.0, np.where(cover[sel] == side[sel], 100 / 110, -1.0))
    n = int(sel.sum())
    r = float(res.mean())
    se = float(res.std() / np.sqrt(n))
    return {"n": n, "roi": r, "lo": r - 1.96 * se, "hi": r + 1.96 * se}


def run_full_evaluation(g: pd.DataFrame, params: Params) -> dict:
    g = g[g.season <= 2026].reset_index(drop=True).copy()
    out = run_elo(g, params)
    g["p_v2"], g["m_v2"] = out["prob_home"], out["margin_pred"]
    g["p_mkt"] = market_prob(g.close_spread_home.values)
    g["p_v0"] = ridge_v0_walk_forward(g[["season", "date", "home", "away", "home_pts", "away_pts", "neutral"]].copy())
    y = (g.home_margin > 0).astype(int).values
    g["y"] = y
    S = g.season.values
    has_mkt = g.p_mkt.notna().values
    home_rate = y[(S >= 2012) & (S <= 2019)].mean()
    mask = {k: (S >= a) & (S <= b) for k, (a, b) in BLOCKS.items()}
    res: dict = {"params": params.as_dict(), "blocks": {}, "n_games": int(len(g))}
    for k, m in mask.items():
        row = {}
        for lab, p, mm, mk in (("siempre_local", np.full(len(g), home_rate), None, m), ("v0_ridge", g.p_v0.values, None, m),
                               ("v2_elo", g.p_v2.values, g.m_v2.values, m), ("mercado", g.p_mkt.values, -g.close_spread_home.values, m & has_mkt)):
            row[lab] = {"n": int(mk.sum()), "log_loss": log_loss(p[mk], y[mk]), "brier": brier(p[mk], y[mk]),
                        "accuracy": accuracy(p[mk], y[mk]), "ece": calibration_error(p[mk], y[mk]),
                        "mae_margin": float(np.abs(mm[mk] - g.home_margin.values[mk]).mean()) if mm is not None else None}
        res["blocks"][k] = row
    T, D = mask["TEST"] & has_mkt, mask["DEV"] & has_mkt
    l2, l0, lk = (per_game_logloss(g[c][T], y[T]) for c in ("p_v2", "p_v0", "p_mkt"))
    res["test_bootstrap"] = {}
    for lab, a, b in (("v2_menos_v0", l2, l0), ("v2_menos_mercado", l2, lk)):
        d, lo, hi = paired_bootstrap_diff(a, b)
        res["test_bootstrap"][lab] = {"diff": d, "lo": lo, "hi": hi}
    res["calibration_test_v2"] = calibration_table(g.p_v2[T], y[T])
    res["per_season_test"] = {int(s): {c: log_loss(g[c][(S == s) & has_mkt], y[(S == s) & has_mkt]) for c in ("p_v0", "p_v2", "p_mkt")}
                              for s in range(2022, 2027)}
    # blend con el mercado (ajustado solo en DEV)
    def feats(m): return np.c_[np.ones(m.sum()), logit(g.p_mkt[m]), logit(g.p_v2[m])]
    w = _logit_fit(feats(D), y[D])
    pb = sigmoid(feats(T) @ w)
    d, lo, hi = paired_bootstrap_diff(per_game_logloss(pb, y[T]), lk)
    res["blend"] = {"coef_dev": {"a": w[0], "b_mercado": w[1], "b_modelo": w[2]}, "test_ll_blend": float(per_game_logloss(pb, y[T]).mean()),
                    "test_ll_mercado": float(lk.mean()), "diff_vs_mercado": {"diff": d, "lo": lo, "hi": hi}}
    # fracción real de la discrepancia
    res["gap_info"] = {}
    for lab, m in (("DEV", D), ("TEST", T)):
        mm = -g.close_spread_home.values[m]
        gap = g.m_v2.values[m] - mm
        yy = g.home_margin.values[m]
        X = np.c_[np.ones(m.sum()), mm, gap]
        b = la.lstsq(X, yy, rcond=None)[0]
        r = yy - X @ b
        se = np.sqrt(np.diag(la.inv(X.T @ X)) * r.var())
        res["gap_info"][lab] = {"n": int(m.sum()), "c1_mercado": float(b[1]), "c2_gap": float(b[2]), "c2_ci95": float(1.96 * se[2]),
                                "t_c2": float(b[2] / se[2]), "sd_gap_pts": float(gap.std())}
    res["roi_spread_-110"] = {str(t): {"DEV": _roi(g, D, t), "TEST": _roi(g, T, t)} for t in (1, 2, 3, 4, 5)}
    # contrastes pre-especificados sobre el residuo del mercado
    pre = {}
    for lab, m in (("DEV", D), ("TEST", T)):
        r = g.home_margin.values[m] + g.close_spread_home.values[m]
        b2b = (g.rest_home.values[m] <= 1).astype(int) - (g.rest_away.values[m] <= 1).astype(int)
        av = np.clip(g.avail_home.values[m] - g.avail_away.values[m], -60, 60) / 10.0
        X = np.c_[np.ones(m.sum()), b2b, av]
        b = la.lstsq(X, r, rcond=None)[0]
        e = r - X @ b
        se = np.sqrt(np.diag(la.inv(X.T @ X)) * e.var())
        pre[lab] = {"back_to_back": {"coef": float(b[1]), "t": float(b[1] / se[1])}, "disponibilidad": {"coef": float(b[2]), "t": float(b[2] / se[2])}}
    res["contrastes_mercado"] = pre
    return res


def results_markdown(res: dict) -> str:
    """Tabla legible de docs/RESULTADOS.json."""
    f = lambda x: f"{x:.4f}"                                           # noqa: E731
    L = ["# Resultados (generado por scripts/run_pipeline.py)", "",
         "Bloques: DEV 2014-2019 (afinado), VAL 2020-2021 (no usado), TEST 2022-2026 (no usado).", "",
         "| Bloque | Modelo | Log loss | Brier | Acierto | ECE | n |", "|---|---|---|---|---|---|---|"]
    names = {"siempre_local": "Siempre local", "v0_ridge": "v0 (ridge, walk-forward)", "v2_elo": "v2 (Elo + contexto)", "mercado": "Mercado (spread de cierre)"}
    for b, rows in res["blocks"].items():
        for k, v in rows.items():
            L.append(f"| {b} | {names[k]} | {f(v['log_loss'])} | {f(v['brier'])} | {v['accuracy']*100:.1f} % | {f(v['ece'])} | {v['n']} |")
    L += ["", "## TEST: diferencias de log loss (IC95 % bootstrap por partido; negativo = el primero es mejor)", ""]
    for k, v in res["test_bootstrap"].items():
        L.append(f"- {k}: {v['diff']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}]")
    bl = res["blend"]
    L += ["", "## ¿Aporta el modelo algo además del mercado?", "",
          f"- Blend logístico ajustado en DEV: peso del mercado {bl['coef_dev']['b_mercado']:.3f}, peso del modelo {bl['coef_dev']['b_modelo']:.3f}.",
          f"- TEST log loss: mercado {bl['test_ll_mercado']:.4f}, blend {bl['test_ll_blend']:.4f} (dif {bl['diff_vs_mercado']['diff']:+.4f}).", ""]
    for k, v in res["gap_info"].items():
        L.append(f"- {k}: fracción real de la discrepancia modelo-mercado c2 = {v['c2_gap']:+.3f} ± {v['c2_ci95']:.3f} (t = {v['t_c2']:+.1f}); sd de la discrepancia {v['sd_gap_pts']:.2f} pts.")
    L += ["", "## Apuestas simuladas al spread a -110 siguiendo al modelo (umbral en puntos de discrepancia)", "",
          "| Umbral | DEV n | DEV ROI | TEST n | TEST ROI | TEST IC95 |", "|---|---|---|---|---|---|"]
    for t, v in res["roi_spread_-110"].items():
        d, te = v["DEV"], v["TEST"]
        L.append(f"| {t} | {d['n']} | {d['roi']*100:+.1f} % | {te['n']} | {te['roi']*100:+.1f} % | [{te['lo']*100:+.1f}, {te['hi']*100:+.1f}] |")
    L += ["", "Referencia: apostar sin información a -110 pierde ≈ 4,5 % (comisión).", ""]
    return "\n".join(L)
