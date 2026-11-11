"""Ratings de fuerza en puntos por equipo (regresión de crestas sobre el margen).

margen_local = rating_local - rating_visitante + ventaja_de_campo
Cada rating tiene un prior (por defecto, derivado del récord) con peso `lam`.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .odds import normal_cdf


@dataclass
class Ratings:
    team: dict[str, float]
    hca_estimated: float


def load_games(path: str | Path) -> list[dict]:
    """CSV: date_et,home,away,home_pts,away_pts"""
    with open(path, newline="", encoding="utf-8") as f:
        return [
            {
                "date_et": r["date_et"],
                "home": r["home"],
                "away": r["away"],
                "home_pts": int(r["home_pts"]),
                "away_pts": int(r["away_pts"]),
            }
            for r in csv.DictReader(f)
        ]


def load_standings(path: str | Path) -> dict[str, tuple[int, int]]:
    """CSV: team,wins,losses"""
    with open(path, newline="", encoding="utf-8") as f:
        return {r["team"]: (int(r["wins"]), int(r["losses"])) for r in csv.DictReader(f)}


def prior_from_record(wins: int, losses: int, scale: float = 14.0) -> float:
    """Prior en puntos: 100 % de victorias = +scale/2, 0 % = -scale/2."""
    n = wins + losses
    return 0.0 if n == 0 else (wins / n - 0.5) * scale


def record_from_games(games: list[dict]) -> dict[str, tuple[int, int]]:
    """Récord calculado SOLO con los partidos dados (sin fuga de información)."""
    rec: dict[str, list[int]] = {}
    for g in games:
        h, a = g["home"], g["away"]
        rec.setdefault(h, [0, 0])
        rec.setdefault(a, [0, 0])
        if g["home_pts"] > g["away_pts"]:
            rec[h][0] += 1
            rec[a][1] += 1
        else:
            rec[a][0] += 1
            rec[h][1] += 1
    return {t: (w, l) for t, (w, l) in rec.items()}


def fit_ratings(games: list[dict], prior: dict[str, float], lam: float = 6.0) -> Ratings:
    """Ridge: minimiza error de margen + lam * (rating - prior)^2.

    La ventaja de campo se estima con regularización casi nula, pero para
    predecir se usa un valor fijo (ver `predict_margin`), porque con pocos
    partidos la estimada es muy ruidosa.
    """
    teams = sorted(set(prior) | {g["home"] for g in games} | {g["away"] for g in games})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    X = np.zeros((len(games), n + 1))
    y = np.zeros(len(games))
    for k, g in enumerate(games):
        X[k, idx[g["home"]]] = 1
        X[k, idx[g["away"]]] = -1
        X[k, n] = 1
        y[k] = g["home_pts"] - g["away_pts"]
    P = np.array([prior.get(t, 0.0) for t in teams] + [0.0])
    reg = lam * np.eye(n + 1)
    reg[n, n] = 0.01
    beta = np.linalg.solve(X.T @ X + reg, X.T @ y + reg @ P)
    return Ratings(team={t: float(beta[idx[t]]) for t in teams}, hca_estimated=float(beta[n]))


def predict_margin(r: Ratings, home: str, away: str, hca: float = 3.0, adj: float = 0.0) -> float:
    """Margen esperado del local. `adj` = ajuste de contexto en puntos (+ ayuda al local)."""
    return r.team.get(home, 0.0) - r.team.get(away, 0.0) + hca + adj


SIGMA_V0 = 12.0   # sigma fija del modelo v0 (baseline histórico). NO es la del mercado: esa es baselines.SIGMA_MARKET


def win_prob(margin: float, sigma: float = SIGMA_V0) -> float:
    """Probabilidad de victoria del local con margen ~ Normal(margen, sigma)."""
    return normal_cdf(margin / sigma)
