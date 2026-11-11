"""Modelo v2: ratings secuenciales tipo Elo en puntos de margen (walk-forward por construcción).

Para cada partido, en orden cronológico:
  margen_pred = r_local - r_visit + HCA (0 si pista neutral) + efecto_descanso(local) - efecto_descanso(visit)
  error       = clip(margen_real, ±cap) - margen_pred
  r_local += K*error ; r_visit -= K*error            (suma cero)
  HCA     += lr_hca*error                              (ventaja de campo adaptativa)
Al cambiar de temporada: r = carry * r  (regresión a la media).
La dispersión sigma se estima online (EWMA del error cuadrático): el margen de la NBA es más
variable hoy (~16 pts) que en 2012 (~13), así que un sigma fijo calibra mal.
Ningún valor usa información posterior al partido que se predice.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd

_N = NormalDist()


@dataclass(frozen=True)
class Params:
    k: float = 0.06            # tasa de aprendizaje de ratings (puntos por punto de error)
    carry: float = 0.75        # fracción del rating que se conserva entre temporadas
    hca0: float = 2.5          # ventaja de campo inicial (puntos)
    lr_hca: float = 0.003      # adaptación online de la ventaja de campo
    cap: float = 25.0          # recorte del margen real (diminishing returns)
    rest_b2b: float = -1.5     # efecto (puntos) de jugar sin descanso (jugó ayer)
    rest_long: float = 0.0     # efecto (puntos) de llegar con >= 3 días de descanso
    boost: float = 0.5         # K extra al inicio de temporada (decae con los partidos jugados)
    sig_scale: float = 1.0     # factor sobre la sigma estimada online
    avail: float = 0.0         # (opcional) puntos por minuto-equivalente de disponibilidad (ver availability.py)
    w_s: float = 0.0           # peso de la fuerza basada en jugadores (S_home - S_away), ver player_model.py

    def as_dict(self):
        return asdict(self)


AVAIL_CLIP = 60.0      # recorte del delta de disponibilidad (minutos-equivalentes)
SIGMA_MEMORY = 1500.0   # partidos de memoria de la sigma online (fijo, no se ajusta)
SIGMA_INIT = 13.0


@dataclass
class EloState:
    ratings: dict
    hca: float
    var: float
    games_in_season: dict
    season: int | None


def _clip_avail(x: float) -> float:
    """Recorta el delta de disponibilidad a ±AVAIL_CLIP. (Antes estaba escrito en línea con un condicional
    que, si el local superaba +AVAIL_CLIP, descartaba el término del visitante: 81 partidos de 2012-2026.)"""
    return AVAIL_CLIP if x > AVAIL_CLIP else (-AVAIL_CLIP if x < -AVAIL_CLIP else x)


def _rest_effect(rest: int, p: Params) -> float:
    if rest <= 1:
        return p.rest_b2b
    if rest >= 3:
        return p.rest_long
    return 0.0


def run_elo(df: pd.DataFrame, p: Params, state: EloState | None = None):
    """Recorre `df` (ordenado por fecha) y devuelve arrays de predicción previos a cada partido.

    Devuelve dict con: margin_pred, sigma, prob_home (todos alineados con df) y el estado final.
    """
    teams = sorted(set(df.home) | set(df.away) | (set(state.ratings) if state else set()))
    r = {t: 0.0 for t in teams}
    gis = {t: 0 for t in teams}
    hca, var, season = p.hca0, SIGMA_INIT ** 2, None
    if state is not None:
        r.update(state.ratings)
        gis.update(state.games_in_season)
        hca, var, season = state.hca, state.var, state.season

    n = len(df)
    mp = np.empty(n)
    sg = np.empty(n)
    H, A = df.home.values, df.away.values
    M, S, NEU = df.home_margin.values.astype(float), df.season.values, df.neutral.values
    RH, RA = df.rest_home.values, df.rest_away.values
    SD = (df.S_home.values - df.S_away.values) if "S_home" in df else np.zeros(n)
    AH = df.avail_home.values if "avail_home" in df else np.zeros(n)
    AA = df.avail_away.values if "avail_away" in df else np.zeros(n)
    cap = p.cap
    for i in range(n):
        s = S[i]
        if s != season:
            if season is not None:
                for t in r:
                    r[t] *= p.carry
                    gis[t] = 0
            season = s
        h, a = H[i], A[i]
        pred = (r[h] - r[a] + (0.0 if NEU[i] else hca) + _rest_effect(RH[i], p) - _rest_effect(RA[i], p)
                + p.avail * (_clip_avail(AH[i]) - _clip_avail(AA[i])))
        pred += p.w_s * SD[i]
        mp[i] = pred
        sg[i] = math.sqrt(var) * p.sig_scale
        m = M[i]
        m = cap if m > cap else (-cap if m < -cap else m)
        err = m - pred
        k = p.k * (1.0 + p.boost * math.exp(-(gis[h] + gis[a]) / 30.0))
        r[h] += k * err
        r[a] -= k * err
        if not NEU[i]:
            hca += p.lr_hca * err
        var += (M[i] - pred) ** 2 / SIGMA_MEMORY - var / SIGMA_MEMORY
        gis[h] += 1
        gis[a] += 1
    prob = np.array([_N.cdf(x / y) for x, y in zip(mp, sg)])
    return {"margin_pred": mp, "sigma": sg, "prob_home": prob,
            "state": EloState(r, hca, var, gis, season)}


def predict_game(state: EloState, home: str, away: str, rest_home: int, rest_away: int,
                 p: Params, neutral: bool = False, adj: float = 0.0) -> dict:
    """Predicción para un partido futuro con el estado actual (adj = ajuste de contexto, + ayuda al local)."""
    pred = (state.ratings.get(home, 0.0) - state.ratings.get(away, 0.0) + (0.0 if neutral else state.hca)
            + _rest_effect(rest_home, p) - _rest_effect(rest_away, p) + adj)
    sigma = math.sqrt(state.var) * p.sig_scale
    return {"margin": pred, "sigma": sigma, "prob_home": _N.cdf(pred / sigma)}
