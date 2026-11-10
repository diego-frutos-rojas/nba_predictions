"""Evaluación del modelo de jugadores: bloques DEV / VAL / TEST, calibración y contraste con líneas reales.

Tres preguntas, por orden de exigencia:
  1. ¿Proyecta mejor que las medias que usaría cualquiera (últimos 10, temporada)?  -> `block_metrics`
  2. ¿Sus probabilidades de over/under son fiables?                                 -> `calibration`
  3. ¿Sabe algo que la casa no sepa? (líneas de DraftKings de la temporada en curso) -> `market_test`
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import live, props
from .elo import run_elo
from .evaluate import BLOCKS, load_params
from .metrics import calibration_error, log_loss, logit, sigmoid
from .odds import american_to_decimal, american_to_implied

EDGE_THRESHOLDS = (0.0, 0.03, 0.06, 0.10)       # fijados antes de mirar resultados
BASELINES = {"ult10": "l10_", "temporada": "savg_"}


def build(root: str | Path, use_live: bool = True) -> tuple[pd.DataFrame, dict]:
    """Filas jugador-partido con variables previas (walk-forward) y el dataset de partidos."""
    root = Path(root)
    ds = live.build_dataset(root / "data/raw", root / "data/live" if use_live else None)
    g = ds["games"]
    g["margin_model"] = run_elo(g, load_params(root / "models/params_v2.json"))["margin_pred"]
    return props.build_features(g, ds["boxes"]), ds


def dev_rows(f: pd.DataFrame) -> pd.DataFrame:
    a, b = BLOCKS["DEV"]
    return f[(f.season >= a) & (f.season <= b)]


def _baseline(f: pd.DataFrame, prefix: str, market: str) -> np.ndarray:
    parts = props.COMBOS.get(market, (market,))
    return sum(f[prefix + s].values for s in parts)


def block_metrics(f: pd.DataFrame, model: dict, n_boot: int = 500, seed: int = 0) -> dict:
    """RMSE y MAE del modelo y de los baselines por bloque y mercado, con IC95 % bootstrap (por partido) de la
    diferencia de error cuadrático modelo - 'temporada' (negativo = el modelo es mejor)."""
    out = {}
    blocks = dict(BLOCKS)
    blocks["ACTUAL"] = (max(b for _, b in BLOCKS.values()) + 1, 9999)
    for name, (a, b) in blocks.items():
        t = f[(f.season >= a) & (f.season <= b)]
        if t.empty:
            continue
        mu = props.predict(model, t)
        res = {"n": int(len(t)), "partidos": int(t.game_id.nunique()),
               "minutos": {"mae_modelo": float(np.abs(t.minutes.values - mu["min"]).mean()),
                           "mae_media_rapida": float(np.abs(t.minutes.values - t.min_fast.values).mean())}}
        gcode = pd.factorize(t.game_id)[0]
        rng = np.random.default_rng(seed)
        for m in props.ALL_MARKETS:
            y = props.actual(t, m)
            row = {"modelo": {"rmse": float(np.sqrt(((y - mu[m]) ** 2).mean())), "mae": float(np.abs(y - mu[m]).mean()),
                              "sesgo": float((mu[m] - y).mean())}}
            for lab, pre in BASELINES.items():
                bl = _baseline(t, pre, m)
                row[lab] = {"rmse": float(np.sqrt(((y - bl) ** 2).mean())), "mae": float(np.abs(y - bl).mean())}
            d = (y - mu[m]) ** 2 - (y - _baseline(t, "savg_", m)) ** 2
            sums = np.bincount(gcode, weights=d)
            idx = rng.integers(0, len(sums), size=(n_boot, len(sums)))
            boot = sums[idx].sum(axis=1) / len(d)
            row["dif_mse_vs_temporada"] = {"media": float(d.mean()), "lo": float(np.percentile(boot, 2.5)),
                                           "hi": float(np.percentile(boot, 97.5))}
            res[m] = row
        out[name] = res
    return out


def calibration(f: pd.DataFrame, model: dict) -> dict:
    """Fiabilidad de P(over) frente a una línea ficticia: la media de los últimos 10 partidos redondeada a x,5
    (parecida a las líneas reales, que no existen en histórico). Compara con decir siempre 50 %."""
    out = {}
    blocks = dict(BLOCKS)
    blocks["ACTUAL"] = (max(b for _, b in BLOCKS.values()) + 1, 9999)
    for name, (a, b) in blocks.items():
        t = f[(f.season >= a) & (f.season <= b)]
        if t.empty:
            continue
        mu = props.predict(model, t)
        res = {}
        for m in props.ALL_MARKETS:
            line = np.floor(_baseline(t, "l10_", m)) + 0.5
            p = props.prob_over_vec(model, m, mu[m], line)
            y = (props.actual(t, m) > line).astype(float)
            bins = np.clip((p * 10).astype(int), 0, 9)
            table = [{"tramo": f"{k/10:.1f}-{(k+1)/10:.1f}", "n": int((bins == k).sum()),
                      "predicho": float(p[bins == k].mean()), "real": float(y[bins == k].mean())}
                     for k in range(10) if (bins == k).sum() >= 50]
            res[m] = {"n": int(len(y)), "log_loss": log_loss(p, y), "log_loss_tasa_base": log_loss(np.full(len(y), y.mean()), y),
                      "ece": calibration_error(p, y), "tabla": table}
        out[name] = res
    return out


def join_market(f: pd.DataFrame, prop_lines: pd.DataFrame, model: dict) -> pd.DataFrame:
    """Une las líneas reales con las proyecciones (solo jugadores que jugaron y eran proyectables)."""
    mu = props.predict(model, f)
    base = f[["game_id", "pid", "name", "team", "date", "season"]].copy()
    parts = []
    for m in props.ALL_MARKETS:
        ln = prop_lines[prop_lines.market == m]
        t = base.assign(mu=mu[m], y=props.actual(f, m), base_l10=_baseline(f, "l10_", m)).merge(
            ln[["game_id", "pid", "line", "over", "under", "side_ok"]], on=["game_id", "pid"])
        t["market"] = m
        if len(t):
            t["p_over"] = props.prob_over_vec(model, m, t.mu.values, t.line.values)
        parts.append(t)
    return pd.concat(parts, ignore_index=True)


def _fair_over(over, under) -> float:
    a, b = american_to_implied(over), american_to_implied(under)
    return a / (a + b)


def _bets(t: pd.DataFrame, thr: float) -> dict:
    """Apuesta 1 unidad al lado que prefiere el modelo cuando su ventaja estimada sobre la probabilidad sin
    margen de la casa es >= thr. Precios reales; el empate devuelve la apuesta."""
    edge_over = t.p_over - t.fair_over
    side_over = edge_over > 0
    edge = np.where(side_over, edge_over, -edge_over)
    sel = edge >= thr
    if not sel.any():
        return {"n": 0}
    s = t[sel]
    so = side_over[sel].values
    dec = np.where(so, s.over.map(american_to_decimal), s.under.map(american_to_decimal))
    win = np.where(so, s.y > s.line, s.y < s.line)
    push = (s.y == s.line).values
    pnl = np.where(push, 0.0, np.where(win, dec - 1, -1.0))
    gsum = pd.Series(pnl).groupby(s.game_id.values).sum().values           # IC por partido (las props de un
    rng = np.random.default_rng(0)                                           # mismo partido están correlacionadas)
    boot = gsum[rng.integers(0, len(gsum), size=(2000, len(gsum)))].sum(axis=1) / len(pnl)
    return {"n": int(len(pnl)), "acierto": float(win[~push].mean()), "roi": float(pnl.mean()),
            "lo": float(np.percentile(boot, 2.5)), "hi": float(np.percentile(boot, 97.5)),
            "over_pct": float(so.mean())}


def market_test(f: pd.DataFrame, prop_lines: pd.DataFrame, model: dict) -> dict:
    """Contraste con las líneas de cierre de DraftKings (temporada en curso; el modelo no las ha visto)."""
    t = join_market(f, prop_lines, model)
    if t.empty:
        return {"n": 0}
    out = {"n": int(len(t)), "partidos": int(t.game_id.nunique()),
           "desde": str(pd.Timestamp(t.date.min()).date()), "hasta": str(pd.Timestamp(t.date.max()).date()),
           "error": {}, "apuestas": {}, "apuestas_por_mercado": {}}
    for m, s in t.groupby("market"):
        out["error"][m] = {"n": int(len(s)), "mae_linea": float((s.y - s.line).abs().mean()),
                           "mae_modelo": float((s.y - s.mu).abs().mean()),
                           "mae_ult10": float((s.y - s.base_l10).abs().mean()),
                           "over_real": float((s.y > s.line).mean()),
                           "dif_media_modelo_linea": float((s.mu - s.line).mean())}
    ok = t[t.side_ok.astype(bool) & t.over.notna() & t.under.notna()].copy()
    ok["fair_over"] = [_fair_over(o, u) for o, u in zip(ok.over, ok.under)]
    for thr in EDGE_THRESHOLDS:
        out["apuestas"][f"{thr:.2f}"] = _bets(ok, thr)
    for m, s in ok.groupby("market"):
        out["apuestas_por_mercado"][m] = {f"{thr:.2f}": _bets(s, thr) for thr in (0.0, 0.06)}
    # ¿Añade algo el modelo a la probabilidad de la casa? regresión logística de 'over' sobre ambas
    y = (ok.y > ok.line).astype(float).values
    keep = (ok.y != ok.line).values
    X = np.column_stack([logit(ok.fair_over.values), logit(np.clip(ok.p_over.values, 0.01, 0.99))])[keep]
    yk = y[keep]
    w = np.zeros(2)
    for _ in range(50):
        p = sigmoid(X @ w)
        H = X.T @ (X * (p * (1 - p))[:, None]) + 1e-9 * np.eye(2)
        w += np.linalg.solve(H, X.T @ (yk - p))
    p = sigmoid(X @ w)
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))))
    out["blend"] = {"coef_casa": float(w[0]), "coef_modelo": float(w[1]), "se_casa": float(se[0]), "se_modelo": float(se[1]),
                    "log_loss_casa": log_loss(ok.fair_over.values[keep], yk),
                    "log_loss_modelo": log_loss(np.clip(ok.p_over.values[keep], 0.01, 0.99), yk), "n": int(keep.sum())}
    return out


def results_markdown(res: dict) -> str:
    L = props.LABELS
    md = ["# Resultados del modelo de jugadores (props v1)", "",
          "Generado por `python scripts/run_props.py`. Coeficientes ajustados solo con DEV (2014-2019).", ""]
    md += ["## 1. Error de proyección (RMSE; menor es mejor)", "",
           "| Bloque | Mercado | n | Modelo | Últimos 10 | Media temporada | Dif. MSE vs temporada (IC95 %) |", "|---|---|---|---|---|---|---|"]
    for blk, r in res["bloques"].items():
        for m in props.ALL_MARKETS:
            x = r[m]
            d = x["dif_mse_vs_temporada"]
            md.append(f"| {blk} | {L[m]} | {r['n']} | **{x['modelo']['rmse']:.3f}** | {x['ult10']['rmse']:.3f} | "
                      f"{x['temporada']['rmse']:.3f} | {d['media']:+.3f} [{d['lo']:+.3f}; {d['hi']:+.3f}] |")
    md += ["", "## 2. Calibración de P(over) frente a una línea ficticia (media de los últimos 10)", "",
           "| Bloque | Mercado | Log loss modelo | Log loss tasa base | ECE |", "|---|---|---|---|---|"]
    for blk, r in res["calibracion"].items():
        for m in props.ALL_MARKETS:
            x = r[m]
            md.append(f"| {blk} | {L[m]} | {x['log_loss']:.4f} | {x['log_loss_tasa_base']:.4f} | {x['ece']:.3f} |")
    mk = res.get("mercado") or {}
    if mk.get("n"):
        md += ["", f"## 3. Contra las líneas de cierre de DraftKings ({mk['desde']} a {mk['hasta']}, {mk['partidos']} partidos)", "",
               "| Mercado | n | MAE línea | MAE modelo | MAE últimos 10 |", "|---|---|---|---|---|"]
        for m in props.ALL_MARKETS:
            if m in mk["error"]:
                x = mk["error"][m]
                md.append(f"| {L[m]} | {x['n']} | {x['mae_linea']:.3f} | {x['mae_modelo']:.3f} | {x['mae_ult10']:.3f} |")
        md += ["", "Apuestas simuladas a los precios reales siguiendo al modelo (ventaja = P modelo − P de la casa sin margen):", "",
               "| Ventaja mínima | n | Acierto | ROI | IC95 % |", "|---|---|---|---|---|"]
        for thr, x in mk["apuestas"].items():
            if x.get("n"):
                md.append(f"| {float(thr)*100:.0f} pp | {x['n']} | {x['acierto']*100:.1f} % | {x['roi']*100:+.1f} % | "
                          f"[{x['lo']*100:+.1f}; {x['hi']*100:+.1f}] |")
        b = mk["blend"]
        md += ["", f"Regresión logística de «over» sobre casa y modelo (n = {b['n']}): peso de la casa {b['coef_casa']:.2f} ± "
               f"{b['se_casa']:.2f}, peso del modelo {b['coef_modelo']:.2f} ± {b['se_modelo']:.2f}. Log loss: casa "
               f"{b['log_loss_casa']:.4f}, modelo {b['log_loss_modelo']:.4f}."]
    return "\n".join(md) + "\n"
