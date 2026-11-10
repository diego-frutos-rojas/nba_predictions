"""Disponibilidad de plantilla ("talento disponible hoy frente al habitual").

Idea: el rating de un equipo ya refleja la plantilla que ha jugado últimamente. Lo que el rating NO sabe es
si hoy falta (o vuelve) un jugador importante. Se mide como:

    delta = T_hoy - T_habitual
    T_hoy      = suma del valor v_p de los jugadores de la plantilla de rotación que HOY juegan
    T_habitual = media, sobre los últimos 10 partidos del equipo, de la suma del valor v_p de ESOS MISMOS
                 jugadores que jugaron en cada partido (misma plantilla y mismo valor en ambos términos)

  * v_p = m_p * z_p: minutos medios (media móvil exponencial) por un multiplicador de calidad z_p =
    clip(q_p / Q_MEAN, 0.3, 2.0), con q_p = media móvil del Game Score de Hollinger por minuto. Así una
    estrella de 36 min pesa más que un suplente de 36 min. Solo usa información previa.
  * Rotación = jugadores con m_p >= 12 min, cuyo último equipo es este, que han jugado en esta
    temporada y en los últimos 25 partidos del equipo (así los traspasados no cuentan como "ausentes").
  * Los 5 primeros partidos de cada temporada tienen delta = 0 (sin información suficiente).

Sin fuga de información: m_p y T_habitual solo usan partidos anteriores; "quién juega hoy" equivale a
la lista de inactivos que se publica antes del salto inicial (en producción se sustituye por el parte de
lesiones con probabilidades de jugar, ver `expected_delta`).
"""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd

from .data import ABBR, FIRST_SEASON, LAST_SEASON

M_ALPHA = 0.25      # peso del último partido en la media móvil de minutos
Q_ALPHA = 0.15      # peso del último partido en la media móvil de Game Score por minuto
Q_MEAN = 0.45       # Game Score por minuto medio de un jugador de rotación (constante de normalización)
Q_MIN_MINUTES = 8   # minutos mínimos en un partido para actualizar la calidad
MIN_ROT = 12.0      # minutos medios mínimos para considerar al jugador de rotación
WINDOW = 25         # partidos del equipo sin jugar tras los que deja de contarse en la plantilla
WARMUP = 5          # partidos iniciales de cada temporada con delta = 0
BASE_N = 10         # partidos para el T habitual


def load_boxes(raw_dir: str | Path, seasons=range(FIRST_SEASON, LAST_SEASON + 1), with_names: bool = False) -> pd.DataFrame:
    parts = []
    for y in seasons:
        f = Path(raw_dir) / f"pbox_{y}.parquet"
        if not f.exists():
            continue
        b = pd.read_parquet(f, columns=["game_id", "season_type", "athlete_id", "team_abbreviation", "minutes", "did_not_play",
                                        "points", "field_goals_made", "field_goals_attempted", "free_throws_made",
                                        "free_throws_attempted", "offensive_rebounds", "defensive_rebounds", "assists",
                                        "steals", "blocks", "turnovers", "fouls"] + (["athlete_display_name"] if with_names else []))
        b = b[(b.season_type == 2) & b.team_abbreviation.isin(ABBR) & b.athlete_id.notna()]
        mins = pd.to_numeric(b.minutes, errors="coerce")
        n = lambda c: pd.to_numeric(b[c], errors="coerce").fillna(0)      # noqa: E731
        gs = (n("points") + 0.4 * n("field_goals_made") - 0.7 * n("field_goals_attempted")
              - 0.4 * (n("free_throws_attempted") - n("free_throws_made")) + 0.7 * n("offensive_rebounds")
              + 0.3 * n("defensive_rebounds") + n("steals") + 0.7 * n("assists") + 0.7 * n("blocks")
              - 0.4 * n("fouls") - n("turnovers"))                                  # Game Score de Hollinger
        parts.append(pd.DataFrame({
            **({"name": b.athlete_display_name.values} if with_names else {}),
            "gs": gs.values,
            "game_id": b.game_id.astype("int64").astype(str).values,
            "team": b.team_abbreviation.map(ABBR).values,
            "pid": b.athlete_id.astype("int64").values,
            "minutes": mins.fillna(0).values,
            "played": ((~b.did_not_play.fillna(False).astype(bool)) & (mins.fillna(0) > 0)).values,
        }))
    return pd.concat(parts, ignore_index=True)


class AvailabilityTracker:
    """Estado incremental (para el histórico y para predecir partidos futuros)."""

    def __init__(self):
        self.m: dict[int, float] = {}
        self.q: dict[int, float] = {}
        self.cur_team: dict[int, str] = {}
        self.ts: dict[str, dict[int, int]] = defaultdict(dict)    # equipo -> {pid: índice de partido de su última aparición}
        self.tg: dict[str, int] = defaultdict(int)                # partidos jugados por el equipo en la temporada
        self.season: dict[str, int] = {}
        self.hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=BASE_N))   # conjuntos de jugadores que jugaron

    def _roll(self, team: str, season: int):
        if self.season.get(team) != season:
            self.season[team] = season
            self.tg[team] = 0
            self.ts[team] = {}
            self.hist[team] = deque(maxlen=BASE_N)

    def value(self, pid: int) -> float:
        z = min(2.0, max(0.3, self.q.get(pid, Q_MEAN) / Q_MEAN))
        return self.m.get(pid, 0.0) * z

    def roster(self, team: str) -> list[int]:
        idx = self.tg[team]
        return [p for p, last in self.ts[team].items()
                if idx - last <= WINDOW and self.cur_team.get(p) == team and self.m.get(p, 0.0) >= MIN_ROT]

    def baseline(self, team: str, roster: list[int] | None = None):
        """T habitual: valor de la plantilla actual que jugó en cada uno de los últimos partidos."""
        h = self.hist[team]
        if len(h) < WARMUP:
            return None
        roster = self.roster(team) if roster is None else roster
        vals = {p: self.value(p) for p in roster}
        return float(np.mean([sum(v for p, v in vals.items() if p in played) for played in h]))

    def roster_detail(self, team: str) -> dict:
        """Plantilla de rotación con su valor y la fracción de los últimos partidos que jugó (para la web).
        T_habitual = sum(valor * fraccion); delta = sum(valor * P(juega)) - T_habitual (0 si hay < WARMUP partidos)."""
        h = self.hist[team]
        n = len(h)
        return {"n_hist": n, "players": [{"pid": p, "value": self.value(p), "frac": (sum(p in x for x in h) / n if n else 1.0)}
                                          for p in self.roster(team)]}

    def delta_for(self, team: str, season: int, played_ids: set[int]) -> tuple[float, float]:
        """(delta, T_hoy) antes de actualizar con el partido."""
        self._roll(team, season)
        R = self.roster(team)
        T = float(sum(self.value(p) for p in R if p in played_ids))
        base = self.baseline(team, R)
        return (0.0 if base is None else T - base), T

    def expected_delta(self, team: str, season: int, play_prob: dict[int, float]) -> float:
        """Delta esperado con probabilidades de jugar (parte de lesiones). play_prob: {athlete_id: P(juega)};
        los jugadores de rotación que no aparecen en el diccionario se asumen disponibles."""
        self._roll(team, season)
        R = self.roster(team)
        T = float(sum(self.value(p) * play_prob.get(p, 1.0) for p in R))
        base = self.baseline(team, R)
        return 0.0 if base is None else T - base

    def update(self, team: str, season: int, entries: list[tuple], T: float):
        self._roll(team, season)
        for ent in entries:
            pid, mins, played = ent[0], ent[1], ent[2]
            gs = ent[3] if len(ent) > 3 else None
            if played:
                self.m[pid] = mins if pid not in self.m else (1 - M_ALPHA) * self.m[pid] + M_ALPHA * mins
                if gs is not None and mins >= Q_MIN_MINUTES:
                    qq = gs / mins
                    self.q[pid] = qq if pid not in self.q else (1 - Q_ALPHA) * self.q[pid] + Q_ALPHA * qq
                self.cur_team[pid] = team
                self.ts[team][pid] = self.tg[team]
        self.hist[team].append({e[0] for e in entries if e[2]})
        self.tg[team] += 1


def compute_availability(games: pd.DataFrame, boxes: pd.DataFrame, return_tracker: bool = False):
    """Añade delta_home/delta_away (en minutos) a `games` (ordenado por fecha)."""
    by_game: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    gs_col = boxes.gs if "gs" in boxes else [None] * len(boxes)
    for gid, team, pid, mins, played, gs in zip(boxes.game_id, boxes.team, boxes.pid, boxes.minutes, boxes.played, gs_col):
        by_game[gid][team].append((pid, mins, played, gs))
    tr = AvailabilityTracker()
    dh, da, th, ta = [], [], [], []
    for gid, h, a, s in zip(games.game_id, games.home, games.away, games.season):
        ent = by_game.get(gid, {})
        res = {}
        for t in (h, a):
            played_ids = {e[0] for e in ent.get(t, []) if e[2]}
            res[t] = tr.delta_for(t, s, played_ids)
        for t in (h, a):
            tr.update(t, s, ent.get(t, []), res[t][1])
        dh.append(res[h][0]); da.append(res[a][0]); th.append(res[h][1]); ta.append(res[a][1])
    out = games.copy()
    out["avail_home"], out["avail_away"], out["T_home"], out["T_away"] = dh, da, th, ta
    return (out, tr) if return_tracker else out
