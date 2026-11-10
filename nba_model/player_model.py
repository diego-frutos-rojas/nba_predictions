"""Impacto de jugador (tipo "plus-minus ajustado", RAPM-lite) con olvido exponencial. Sin fuga.

Para cada partido: margen_local = ventaja + sum_p(+min_p/48 * beta_p) [local] - sum_q(min_q/48 * beta_q) [visitante].
Se ajusta por ridge (shrinkage hacia 0) con pesos que decaen en el tiempo (los jugadores cambian), y se
re-estima cada REFIT_DAYS días usando SOLO partidos ya jugados.

La fuerza esperada de un equipo en un partido es S = sum_p (m'_p/48) * beta_p, donde m'_p son los minutos
esperados (media móvil previa) de los jugadores que están disponibles, reescalados a 240. Así:
  * una estrella lesionada baja S sin esperar a que el rating tarde partidos en notarlo,
  * un traspaso o un fichaje se refleja desde el primer partido,
  * el rating Elo restante solo tiene que aprender lo que los jugadores no explican.
En producción "disponibles" sale del parte de lesiones (ver `expected_strength`).
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd

M_ALPHA = 0.25          # media móvil de minutos
M_DEFAULT = 10.0        # minutos esperados de un jugador sin historial
REFIT_DAYS = 7
ACTIVE_MIN_WEIGHT = 0.03


class PlayerAPM:
    def __init__(self, pids, lam: float = 25.0, gamma: float = 0.0006):
        self.idx = {int(p): i for i, p in enumerate(sorted(set(int(x) for x in pids)))}
        n = len(self.idx) + 1                       # última columna = intercepto (ventaja de campo)
        self.A = np.zeros((n, n))
        self.b = np.zeros(n)
        self.beta = np.zeros(len(self.idx))
        self.lam, self.gamma = lam, gamma
        self.g = 0
        self.m: dict[int, float] = {}               # minutos esperados (media móvil)

    # --- estimación ---
    def add_game(self, home: list[tuple[int, float]], away: list[tuple[int, float]], margin: float):
        w = math.exp(self.gamma * self.g)
        ids, vals = [], []
        for pid, mins in home:
            ids.append(self.idx[pid]); vals.append(mins / 48.0)
        for pid, mins in away:
            ids.append(self.idx[pid]); vals.append(-mins / 48.0)
        ids.append(len(self.idx)); vals.append(1.0)                     # intercepto
        ids, vals = np.array(ids), np.array(vals)
        self.A[np.ix_(ids, ids)] += w * np.outer(vals, vals)
        self.b[ids] += w * margin * vals
        self.g += 1

    def refit(self):
        if self.g == 0:
            return
        wnow = math.exp(self.gamma * self.g)
        n = len(self.idx)
        diag = np.diag(self.A)[:n] / wnow
        act = np.where(diag > ACTIVE_MIN_WEIGHT)[0]
        if len(act) == 0:
            return
        cols = np.append(act, n)
        M = self.A[np.ix_(cols, cols)] / wnow
        M[np.arange(len(act)), np.arange(len(act))] += self.lam / 1000.0 * 1.0   # ridge (en unidades de "partido")
        beta = np.linalg.solve(M + 1e-9 * np.eye(len(cols)), self.b[cols] / wnow)
        self.beta = np.zeros(n)
        self.beta[act] = beta[:-1]

    # --- minutos esperados y fuerza ---
    def expected_minutes(self, pid: int) -> float:
        return self.m.get(pid, M_DEFAULT)

    def strength(self, players: list[int], weights: dict[int, float] | None = None) -> float:
        """S del equipo con los jugadores dados (pesos = prob. de jugar), minutos reescalados a 240."""
        if not players:
            return 0.0
        mins = np.array([self.expected_minutes(p) * (1.0 if weights is None else weights.get(p, 1.0)) for p in players])
        tot = mins.sum()
        if tot <= 0:
            return 0.0
        mins = mins * 240.0 / tot
        b = np.array([self.beta[self.idx[p]] if p in self.idx else 0.0 for p in players])
        return float((mins / 48.0 * b).sum())

    def update_minutes(self, entries: list[tuple[int, float]]):
        for pid, mins in entries:
            self.m[pid] = mins if pid not in self.m else (1 - M_ALPHA) * self.m[pid] + M_ALPHA * mins


def compute_strength(games: pd.DataFrame, boxes: pd.DataFrame, lam: float = 25.0, gamma: float = 0.0006,
                     return_model: bool = False):
    """Añade S_home y S_away a `games` (ordenado por fecha). Re-estima cada REFIT_DAYS días."""
    played = boxes[boxes.played]
    by_game: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for gid, team, pid, mins in zip(played.game_id, played.team, played.pid, played.minutes):
        by_game[gid][team].append((int(pid), float(mins)))
    model = PlayerAPM(played.pid.unique(), lam, gamma)
    sh, sa = [], []
    last_refit = None
    for gid, h, a, d, marg in zip(games.game_id, games.home, games.away, games.date, games.home_margin):
        if last_refit is None or (d - last_refit).days >= REFIT_DAYS:
            model.refit()
            last_refit = d
        ent = by_game.get(gid, {})
        eh, ea = ent.get(h, []), ent.get(a, [])
        sh.append(model.strength([p for p, _ in eh]))
        sa.append(model.strength([p for p, _ in ea]))
        if eh and ea:
            model.add_game(eh, ea, float(marg))
        model.update_minutes(eh)
        model.update_minutes(ea)
    out = games.copy()
    out["S_home"], out["S_away"] = sh, sa
    return (out, model) if return_model else out
