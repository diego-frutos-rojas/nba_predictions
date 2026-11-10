"""Baselines con los que comparar: (1) mercado, (2) mi modelo v0 en walk-forward, (3) siempre-local."""
from __future__ import annotations

import numpy as np
import pandas as pd
from statistics import NormalDist

from .ratings import fit_ratings, prior_from_record, record_from_games

_N = NormalDist()

SIGMA_MARKET = 11.25   # sigma spread->prob estimada por máxima verosimilitud en DEV (SBR 2012-2019)


def market_prob(spread_home, sigma: float = SIGMA_MARKET):
    """Probabilidad de victoria local implícita en el spread de cierre (spread<0 => local favorito)."""
    s = np.asarray(spread_home, float)
    return np.array([_N.cdf(-x / sigma) if np.isfinite(x) else np.nan for x in s])


def ridge_v0_walk_forward(df: pd.DataFrame, lam: float = 6.0, hca: float = 3.0, sigma: float = 12.0) -> np.ndarray:
    """Mi modelo v0 escalado a historia: ridge con prior de récord, SOLO con partidos previos de la
    misma temporada, HCA fijo 3,0 y sigma fija 12. Devuelve la probabilidad local de cada partido."""
    out = np.full(len(df), np.nan)
    for season, g in df.groupby("season", sort=True):
        idxs = g.index.values
        dates = g.date.values
        rows = g.to_dict("records")
        for d in sorted(set(dates)):
            todays = [i for i, dd in enumerate(dates) if dd == d]
            prior_games = [rows[i] for i in range(len(rows)) if dates[i] < d]
            if prior_games:
                gm = [{"home": x["home"], "away": x["away"], "home_pts": x["home_pts"], "away_pts": x["away_pts"]} for x in prior_games]
                rec = record_from_games(gm)
                prior = {t: prior_from_record(w, l) for t, (w, l) in rec.items()}
                r = fit_ratings(gm, prior, lam).team
            else:
                r = {}
            for i in todays:
                x = rows[i]
                m = r.get(x["home"], 0.0) - r.get(x["away"], 0.0) + (0.0 if x["neutral"] else hca)
                out[idxs[i]] = _N.cdf(m / sigma)
    return out
