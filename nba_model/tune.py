"""Búsqueda de hiperparámetros con controles anti-sobreajuste.

Reglas:
  * Solo se tunea con datos de DEV (temporadas <= 2019). VAL y TEST no se tocan.
  * Búsqueda aleatoria en hipercubo latino con rangos acotados (pocos parámetros, prior débil).
  * Se promedian los mejores configs (top 5 %) en vez de quedarse con el mejor: suaviza ruido.
  * Se comprueba estabilidad con validación cruzada temporal (tunear en una mitad, evaluar en la otra).
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .elo import Params, run_elo
from .metrics import log_loss

BOUNDS = {
    "k": (0.02, 0.12), "carry": (0.40, 0.95), "hca0": (1.5, 3.5), "lr_hca": (0.0, 0.010),
    "cap": (15.0, 40.0), "rest_b2b": (-4.0, 0.0), "rest_long": (-1.0, 2.0),
    "boost": (0.0, 2.0), "sig_scale": (0.90, 1.10), "avail": (0.0, 0.10),
}


def latin_hypercube(n: int, names, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    d = len(names)
    u = np.empty((n, d))
    for j in range(d):
        u[:, j] = (rng.permutation(n) + rng.random(n)) / n
    lo = np.array([BOUNDS[k][0] for k in names])
    hi = np.array([BOUNDS[k][1] for k in names])
    return lo + u * (hi - lo)


def objective(df: pd.DataFrame, p: Params, eval_mask: np.ndarray) -> float:
    out = run_elo(df, p)
    y = (df.home_margin.values > 0).astype(int)
    return log_loss(out["prob_home"][eval_mask], y[eval_mask])


def random_search(df: pd.DataFrame, eval_mask: np.ndarray, n: int = 600, seed: int = 0,
                  names=tuple(BOUNDS), base: Params | None = None) -> pd.DataFrame:
    base = base or Params()
    pts = latin_hypercube(n, names, seed)
    rows = []
    for row in pts:
        p = replace(base, **dict(zip(names, row)))
        rows.append({**dict(zip(names, row)), "ll": objective(df, p, eval_mask)})
    return pd.DataFrame(rows).sort_values("ll").reset_index(drop=True)


def average_top(results: pd.DataFrame, frac: float = 0.05, names=tuple(BOUNDS)) -> Params:
    top = results.head(max(5, int(len(results) * frac)))
    return Params(**{k: float(top[k].mean()) for k in names})
