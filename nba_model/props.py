"""Proyección de estadísticas de jugador (puntos, rebotes, asistencias, triples y combinadas).

Todo es walk-forward: las variables de un partido solo usan partidos anteriores (hay test de fuga).

Para cada jugador que juega un partido se construyen, ANTES del partido:
  * minutos recientes: medias móviles exponenciales rápida y lenta (`MIN_ALPHA_FAST`, `MIN_ALPHA_SLOW`);
  * ritmo por minuto de cada estadística: sumas con olvido exponencial rápida y lenta, encogidas hacia la media
    de la liga con `PRIOR_MINUTES` minutos ficticios (un jugador con pocos minutos se parece a la media);
  * rival: lo que concede el rival de esa estadística frente a la media de la liga (`def_*`);
  * bajas de compañeros: minutos y producción de la rotación que hoy no juega, frente a lo que venía faltando
    (`miss_*`: si ya faltaba, la forma reciente del jugador ya lo incluye);
  * profundidad: minutos habituales que suman los que hoy juegan frente a los 240 que hay para repartir
    (`depth`), e inicio de temporada del jugador (`early`): al empezar el curso los papeles aún no están fijados;
  * contexto: local/visitante, back-to-back, tamaño del spread (palizas = menos minutos) y total de puntos del
    mercado frente a lo que anota el equipo (`env`).

Modelo (pocos coeficientes, ajustados por mínimos cuadrados SOLO con DEV 2014-2019):
  minutos = combinación lineal de las medias de minutos + bajas + back-to-back + spread
  estadística = minutos * ritmo * (1 + efectos de rival, bajas, casa y contexto)
La distribución alrededor de la media es binomial negativa con varianza = a*mu^p (a, p por estadística,
ajustados en DEV; como mínimo la de una Poisson), que da P(más de la línea) para cualquier línea.

Las constantes de este módulo se fijaron a priori (no se buscaron): la combinación de la versión rápida y la
lenta la decide la regresión, que es la forma de "promediar, no elegir" de este módulo.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd

from .data import ABBR, FIRST_SEASON, LAST_SEASON

STATS = ("pts", "reb", "ast", "fg3m")
COMBOS = {"pra": ("pts", "reb", "ast"), "pr": ("pts", "reb"), "pa": ("pts", "ast"), "ra": ("reb", "ast")}
ALL_MARKETS = STATS + tuple(COMBOS)
LABELS = {"pts": "Puntos", "reb": "Rebotes", "ast": "Asistencias", "fg3m": "Triples", "pra": "Pts+Reb+Ast",
          "pr": "Pts+Reb", "pa": "Pts+Ast", "ra": "Reb+Ast", "min": "Minutos"}

MIN_ALPHA_FAST = 0.30     # peso del último partido en la media rápida de minutos
MIN_ALPHA_SLOW = 0.08     # ídem, media lenta
RATE_DECAY_FAST = 0.80    # olvido por partido de las sumas rápidas (vida media ~3 partidos)
RATE_DECAY_SLOW = 0.96    # olvido por partido de las sumas lentas (vida media ~17 partidos)
PRIOR_MINUTES = 100.0     # minutos ficticios a ritmo de liga (encogimiento)
TEAM_DECAY = 0.93         # olvido de las medias de equipo (lo que concede, lo que produce)
LEAGUE_DECAY = 0.999      # olvido de las medias de liga (por fila de equipo-partido)
ROSTER_WINDOW = 25        # partidos del equipo sin jugar tras los que un jugador sale de la rotación
ROSTER_MIN_MINUTES = 10.0 # minutos lentos mínimos para contar como rotación
MISS_ALPHA = 0.30         # media móvil de lo que viene faltando en el equipo
EARLY_GAMES = 5.0         # escala (partidos del jugador en la temporada) del efecto de inicio de temporada
VAR_BUCKETS = 20          # tramos de la media proyectada para ajustar la varianza
ELIGIBLE_GAMES = 5        # partidos previos mínimos para proyectar a un jugador
ELIGIBLE_MINUTES = 8.0    # minutos rápidos mínimos para proyectar a un jugador
RECENT_N = 10             # partidos que se guardan por jugador para mostrar la forma reciente
LEAGUE_INIT = {"pts": 0.42, "reb": 0.18, "ast": 0.095, "fg3m": 0.04}   # ritmos por minuto iniciales (2012)
TEAM_INIT = {"pts": 100.0, "reb": 43.0, "ast": 22.0, "fg3m": 8.0}      # totales de equipo iniciales (2012)

_BOX_COLS = ["game_id", "season_type", "athlete_id", "athlete_display_name", "team_abbreviation", "minutes",
             "did_not_play", "starter", "points", "rebounds", "assists", "three_point_field_goals_made",
             "athlete_position_abbreviation"]
BOX_OUT = ["game_id", "team", "pid", "name", "pos", "minutes", "played", "starter", "pts", "reb", "ast", "fg3m"]


def load_player_boxes(raw_dir: str | Path, seasons=range(FIRST_SEASON, LAST_SEASON + 1), extra: pd.DataFrame | None = None) -> pd.DataFrame:
    """Cajas de jugador de temporada regular con las columnas `BOX_OUT`. `extra`: filas ya normalizadas
    (por ejemplo de `espn.box_rows`) de partidos que todavía no están en los ficheros crudos."""
    parts = []
    for y in seasons:
        f = Path(raw_dir) / f"pbox_{y}.parquet"
        if not f.exists():
            continue
        b = pd.read_parquet(f, columns=_BOX_COLS)
        b = b[(b.season_type == 2) & b.team_abbreviation.isin(ABBR) & b.athlete_id.notna()]
        num = lambda c: pd.to_numeric(b[c], errors="coerce").fillna(0.0).values      # noqa: E731
        mins = num("minutes")
        parts.append(pd.DataFrame({
            "game_id": b.game_id.astype("int64").astype(str).values,
            "team": b.team_abbreviation.map(ABBR).values,
            "pid": b.athlete_id.astype("int64").values,
            "name": b.athlete_display_name.values,
            "pos": b.athlete_position_abbreviation.fillna("").values,
            "minutes": mins,
            "played": (~b.did_not_play.fillna(False).astype(bool)).values & (mins > 0),
            "starter": b.starter.fillna(False).astype(bool).values,
            "pts": num("points"), "reb": num("rebounds"), "ast": num("assists"),
            "fg3m": num("three_point_field_goals_made"),
        }))
    if extra is not None and len(extra):
        have = set().union(*[set(p.game_id) for p in parts]) if parts else set()
        ex = extra[~extra.game_id.astype(str).isin(have)]
        if len(ex):
            parts.append(ex[BOX_OUT].copy())
    out = pd.concat(parts, ignore_index=True)
    return out.drop_duplicates(["game_id", "pid"], keep="last").reset_index(drop=True)


class _Player:
    __slots__ = ("n", "min_fast", "min_slow", "last_min", "sf", "mf", "ss", "ms", "team", "name", "pos", "recent",
                 "start_rate", "season", "g_season", "sum_season", "career", "career_min")

    def __init__(self):
        self.n = 0
        self.min_fast = self.min_slow = self.last_min = 0.0
        self.sf = {s: 0.0 for s in STATS}     # sumas rápidas de cada estadística
        self.ss = {s: 0.0 for s in STATS}     # sumas lentas
        self.mf = self.ms = 0.0               # minutos acumulados (rápido / lento)
        self.career = {s: 0.0 for s in STATS}  # totales de carrera (sin olvido)
        self.career_min = 0.0
        self.team = None
        self.name = ""
        self.pos = ""
        self.start_rate = 0.0
        self.season = None
        self.g_season = 0
        self.sum_season = {s: 0.0 for s in ("min",) + STATS}
        self.recent = deque(maxlen=RECENT_N)


class PropsTracker:
    """Estado incremental del modelo de jugadores (sirve para el histórico y para los partidos de hoy)."""

    def __init__(self):
        self.players: dict[int, _Player] = {}
        self.league = dict(LEAGUE_INIT)                     # ritmo por minuto de la liga
        self.league_team = dict(TEAM_INIT)                  # total medio de un equipo por partido
        self.allowed = defaultdict(lambda: dict(self.league_team))   # lo que concede cada equipo por partido
        self.made = defaultdict(lambda: dict(self.league_team))      # lo que produce cada equipo por partido
        self.team_season: dict[str, int] = {}
        self.team_games: dict[str, int] = defaultdict(int)
        self.last_seen: dict[str, dict[int, int]] = defaultdict(dict)
        self.miss_avg = defaultdict(lambda: {k: 0.0 for k in ("min",) + STATS})
        self.hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=RECENT_N))   # quién jugó en los últimos partidos

    # ---- consultas previas al partido -------------------------------------------------------
    def roll(self, team: str, season: int):
        if self.team_season.get(team) != season:
            self.team_season[team] = season
            self.team_games[team] = 0
            self.last_seen[team] = {}
            self.miss_avg[team] = {k: 0.0 for k in ("min",) + STATS}
            self.hist[team] = deque(maxlen=RECENT_N)

    def candidates(self, team: str, season: int) -> list[int]:
        """Jugadores que pueden jugar hoy con el equipo: los que han jugado con él en sus últimos partidos de la
        temporada (al empezar el curso, también los que acabaron con él la temporada anterior)."""
        self.roll(team, season)
        idx = self.team_games[team]
        out = [pid for pid, last in self.last_seen[team].items()
               if idx - last <= ROSTER_WINDOW and self.players[pid].team == team]
        if idx < ELIGIBLE_GAMES:
            seen = set(out)
            out += [pid for pid, p in self.players.items()
                    if p.team == team and pid not in seen and p.season is not None and p.season >= season - 1]
        return out

    def appear_frac(self, team: str, pid: int) -> float:
        """Fracción de los últimos partidos del equipo en los que el jugador saltó a la pista (1 si no hay historial)."""
        h = self.hist[team]
        return sum(pid in x for x in h) / len(h) if h else 1.0

    def play_weight(self, team: str, pid: int) -> float:
        """Peso de un jugador SANO en los minutos esperados de la alineación de hoy: 1 si ha jugado al menos la mitad
        de los últimos partidos del equipo; si no, su fracción de apariciones (fondo de banquillo). Comprobado con
        DEV 2018-19: esta regla reproduce sin sesgo la suma que el modelo vio al entrenar (232 frente a 235 minutos;
        contar a todos da 248 y ponderar a todos por su fracción da 215)."""
        fr = self.appear_frac(team, pid)
        return 1.0 if fr >= 0.5 else fr

    def rate(self, p: _Player, s: str, fast: bool) -> float:
        """Ritmo por minuto con encogimiento jerárquico: la forma reciente se encoge hacia el ritmo de carrera
        del jugador y este hacia la liga (un pívot que nunca tira triples no hereda los triples de la liga)."""
        career = (p.career[s] + PRIOR_MINUTES * self.league[s]) / (p.career_min + PRIOR_MINUTES)
        num, den = (p.sf[s], p.mf) if fast else (p.ss[s], p.ms)
        return (num + PRIOR_MINUTES * career) / (den + PRIOR_MINUTES)

    def roster(self, team: str) -> list[int]:
        idx = self.team_games[team]
        out = []
        for pid, last in self.last_seen[team].items():
            p = self.players[pid]
            if idx - last <= ROSTER_WINDOW and p.team == team and p.min_slow >= ROSTER_MIN_MINUTES:
                out.append(pid)
        return out

    def missing(self, team: str, play_prob: dict[int, float]) -> dict[str, float]:
        """Minutos y producción de la rotación que hoy NO juega (ponderado por 1 - P(juega))."""
        out = {k: 0.0 for k in ("min",) + STATS}
        for pid in self.roster(team):
            q = 1.0 - play_prob.get(pid, 1.0)
            if q <= 0:
                continue
            p = self.players[pid]
            out["min"] += q * p.min_slow
            for s in STATS:
                out[s] += q * p.min_slow * self.rate(p, s, fast=False)
        return out

    def lineup_minutes(self, play_prob: dict[int, float]) -> float:
        """Minutos habituales (media lenta) que suman los jugadores de rotación que hoy juegan. Si pasan de 240
        (plantilla más profunda de lo normal, típico al empezar la temporada o tras un traspaso) no caben todos."""
        tot = 0.0
        for pid, q in play_prob.items():
            p = self.players.get(pid)
            if p is not None and q > 0 and p.min_slow >= ROSTER_MIN_MINUTES:
                tot += q * p.min_slow
        return tot

    def eligible(self, pid: int) -> bool:
        p = self.players.get(pid)
        return p is not None and p.n >= ELIGIBLE_GAMES and p.min_fast >= ELIGIBLE_MINUTES

    def features(self, pid: int, team: str, opp: str, season: int, ctx: dict, miss: dict[str, float]) -> dict:
        """Variables previas al partido de un jugador. `ctx`: is_home, b2b, abs_spread, team_total (o None).
        `miss`: salida de `missing(team, ...)` para este partido, más la clave 'lineup' (`lineup_minutes`)."""
        self.roll(team, season)
        p = self.players[pid]
        f = {"n_prev": p.n, "min_fast": p.min_fast, "min_slow": p.min_slow, "last_min": p.last_min,
             "start_rate": p.start_rate, "is_home": float(ctx["is_home"]), "b2b": float(ctx["b2b"]),
             "abs_spread": float(ctx["abs_spread"])}
        avg = self.miss_avg[team]
        f["miss_min"] = (miss["min"] - avg["min"]) / 240.0
        f["depth"] = (miss["lineup"] - 240.0) / 240.0
        f["early"] = math.exp(-(p.g_season if p.season == season else 0) / EARLY_GAMES)
        made = self.made[team]
        tt = ctx.get("team_total")
        f["env"] = 0.0 if tt is None or not np.isfinite(tt) else tt / made["pts"] - 1.0
        rec = np.array(p.recent, float)
        same = p.season == season and p.g_season >= ELIGIBLE_GAMES
        f["g_season"] = p.g_season if p.season == season else 0
        for i, s in enumerate(STATS):
            f[f"l10_{s}"] = float(rec[:, i + 1].mean())                       # baseline: media de los últimos 10
            f[f"savg_{s}"] = p.sum_season[s] / p.g_season if same else f[f"l10_{s}"]   # baseline: media de la temporada
        for s in STATS:
            f[f"rf_{s}"] = self.rate(p, s, fast=True)
            f[f"rs_{s}"] = self.rate(p, s, fast=False)
            f[f"def_{s}"] = self.allowed[opp][s] / self.league_team[s] - 1.0
            f[f"miss_{s}"] = (miss[s] - avg[s]) / made[s]
        return f

    # ---- actualización con el partido ya jugado ---------------------------------------------
    def update_team_game(self, team: str, opp: str, season: int, rows: list[tuple], miss: dict[str, float]):
        """rows: (pid, name, pos, minutes, played, starter, pts, reb, ast, fg3m) de TODOS los del equipo."""
        self.roll(team, season)
        tot = {s: 0.0 for s in STATS}
        any_played = False
        for pid, name, pos, mins, played, starter, pts, reb, ast, fg3m in rows:
            if not played:
                continue
            any_played = True
            p = self.players.get(pid)
            if p is None:
                p = self.players[pid] = _Player()
            vals = {"pts": pts, "reb": reb, "ast": ast, "fg3m": fg3m}
            if p.n == 0:
                p.min_fast = p.min_slow = mins
                p.start_rate = float(starter)
            else:
                p.min_fast += MIN_ALPHA_FAST * (mins - p.min_fast)
                p.min_slow += MIN_ALPHA_SLOW * (mins - p.min_slow)
                p.start_rate += MIN_ALPHA_FAST * (float(starter) - p.start_rate)
            p.career_min += mins
            p.mf = p.mf * RATE_DECAY_FAST + mins
            p.ms = p.ms * RATE_DECAY_SLOW + mins
            for s in STATS:
                p.sf[s] = p.sf[s] * RATE_DECAY_FAST + vals[s]
                p.ss[s] = p.ss[s] * RATE_DECAY_SLOW + vals[s]
                p.career[s] += vals[s]
                tot[s] += vals[s]
            if p.season != season:
                p.season, p.g_season = season, 0
                p.sum_season = {k: 0.0 for k in ("min",) + STATS}
            p.g_season += 1
            p.sum_season["min"] += mins
            for s in STATS:
                p.sum_season[s] += vals[s]
            p.n += 1
            p.last_min = mins
            p.team, p.name, p.pos = team, name, pos
            p.recent.append((mins, pts, reb, ast, fg3m))
            self.last_seen[team][pid] = self.team_games[team]
        if not any_played:
            return                                           # partido sin caja: no hay nada que aprender
        self.hist[team].append({r[0] for r in rows if r[4]})
        mins_total = sum(r[3] for r in rows if r[4])
        for s in STATS:
            self.made[team][s] = TEAM_DECAY * self.made[team][s] + (1 - TEAM_DECAY) * tot[s]
            self.allowed[opp][s] = TEAM_DECAY * self.allowed[opp][s] + (1 - TEAM_DECAY) * tot[s]
            self.league_team[s] = LEAGUE_DECAY * self.league_team[s] + (1 - LEAGUE_DECAY) * tot[s]
            if mins_total > 0:
                self.league[s] = LEAGUE_DECAY * self.league[s] + (1 - LEAGUE_DECAY) * tot[s] / mins_total
        avg = self.miss_avg[team]
        for k in avg:
            avg[k] += MISS_ALPHA * (miss[k] - avg[k])
        self.team_games[team] += 1


def game_context(g_row: dict, home: bool) -> dict:
    """Contexto de un equipo en un partido a partir de la fila de `games` (descanso, spread, total)."""
    sp = g_row.get("close_spread_home")
    tot = g_row.get("close_total")
    has_sp = sp is not None and np.isfinite(sp)
    margin_home = -sp if has_sp else g_row.get("margin_model", 0.0)        # margen esperado del local
    team_total = None
    if tot is not None and np.isfinite(tot):
        team_total = tot / 2 + (margin_home if home else -margin_home) / 2
    rest = g_row["rest_home"] if home else g_row["rest_away"]
    return {"is_home": home, "b2b": rest <= 1, "abs_spread": abs(margin_home), "team_total": team_total}


def build_features(games: pd.DataFrame, boxes: pd.DataFrame, return_tracker: bool = False):
    """Recorre los partidos en orden y devuelve una fila por jugador que jugó (variables previas + resultado).

    `games` necesita: game_id, date, season, home, away, rest_home, rest_away, close_spread_home, close_total y
    (opcional) margin_model, el margen del modelo de equipos, que suple al spread cuando no hay línea."""
    by_game: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in boxes[BOX_OUT].itertuples(index=False):
        by_game[r.game_id][r.team].append((int(r.pid), r.name, r.pos, float(r.minutes), bool(r.played), bool(r.starter),
                                           float(r.pts), float(r.reb), float(r.ast), float(r.fg3m)))
    tr = PropsTracker()
    rows = []
    has_mm = "margin_model" in games
    for g in games.itertuples(index=False):
        ent = by_game.get(g.game_id)
        if not ent:
            continue
        grow = {"close_spread_home": g.close_spread_home, "close_total": g.close_total, "rest_home": g.rest_home,
                "rest_away": g.rest_away, "margin_model": g.margin_model if has_mm else 0.0}
        pending = []
        for team, opp, home in ((g.home, g.away, True), (g.away, g.home, False)):
            trows = ent.get(team, [])
            tr.roll(team, g.season)
            played = {r[0] for r in trows if r[4]}
            miss = tr.missing(team, {pid: (1.0 if pid in played else 0.0) for pid in tr.roster(team)})
            miss["lineup"] = tr.lineup_minutes({pid: 1.0 for pid in played})
            ctx = game_context(grow, home)
            for r in trows:
                pid = r[0]
                if r[4] and tr.eligible(pid):
                    f = tr.features(pid, team, opp, g.season, ctx, miss)
                    f.update({"game_id": g.game_id, "date": g.date, "season": g.season, "team": team, "opp": opp,
                              "pid": pid, "name": r[1], "minutes": r[3], "pts": r[6], "reb": r[7], "ast": r[8],
                              "fg3m": r[9]})
                    rows.append(f)
            pending.append((team, opp, trows, miss))
        for team, opp, trows, miss in pending:               # se actualiza DESPUÉS de sacar las variables de ambos
            tr.update_team_game(team, opp, g.season, trows, miss)
    df = pd.DataFrame(rows)
    return (df, tr) if return_tracker else df


# ---- modelo ---------------------------------------------------------------------------------
MIN_FEATURES = ("const", "min_fast", "min_slow", "last_min", "start_rate", "miss_x", "b2b_x", "spread_x", "depth_x",
                "early_x")
STAT_FEATURES = ("const", "base_fast", "base_slow", "def_x", "miss_x", "home_x", "env_x")


def _min_matrix(f) -> np.ndarray:
    ms = np.asarray(f["min_slow"], float)
    return np.column_stack([np.ones(len(ms)), f["min_fast"], ms, f["last_min"], f["start_rate"],
                            np.asarray(f["miss_min"], float) * ms, np.asarray(f["b2b"], float) * ms,
                            np.asarray(f["abs_spread"], float) * ms, np.asarray(f["depth"], float) * ms,
                            np.asarray(f["early"], float) * ms])


def _stat_matrix(f, s: str, min_hat: np.ndarray) -> np.ndarray:
    bf = min_hat * np.asarray(f[f"rf_{s}"], float)
    bs = min_hat * np.asarray(f[f"rs_{s}"], float)
    return np.column_stack([np.ones(len(bs)), bf, bs, bs * np.asarray(f[f"def_{s}"], float), bs * np.asarray(f[f"miss_{s}"], float),
                            bs * np.asarray(f["is_home"], float), bs * np.asarray(f["env"], float)])


def _ols(X: np.ndarray, y: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    A = X.T @ X
    A += ridge * np.trace(A) / len(A) * np.eye(len(A))
    return np.linalg.solve(A, X.T @ y)


def predict_minutes(model: dict, f) -> np.ndarray:
    return np.clip(_min_matrix(f) @ np.asarray(model["minutes"]), 1.0, 44.0)


def predict(model: dict, f) -> dict[str, np.ndarray]:
    """Medias proyectadas: {'min', 'pts', 'reb', 'ast', 'fg3m', 'pra', 'pr', 'pa', 'ra'} (arrays alineados con f)."""
    mh = predict_minutes(model, f)
    out = {"min": mh}
    for s in STATS:
        out[s] = np.clip(_stat_matrix(f, s, mh) @ np.asarray(model["stats"][s]), 0.02, None)
    for c, parts in COMBOS.items():
        out[c] = sum(out[s] for s in parts)
    return out


def actual(f, market: str) -> np.ndarray:
    if market in COMBOS:
        return sum(np.asarray(f[s], float) for s in COMBOS[market])
    return np.asarray(f[market], float)


def fit(dev: pd.DataFrame) -> dict:
    """Ajusta coeficientes y funciones de varianza con las filas que se le pasen (deben ser SOLO de DEV)."""
    model = {"minutes": _ols(_min_matrix(dev), dev.minutes.values).tolist(), "stats": {}, "var": {}}
    mh = predict_minutes(model, dev)
    for s in STATS:
        model["stats"][s] = _ols(_stat_matrix(dev, s, mh), dev[s].values).tolist()
    mu = predict(model, dev)
    for m in ALL_MARKETS:                                    # varianza = a * mu^p, ajustada por tramos de mu
        t = pd.DataFrame({"mu": mu[m], "r2": (actual(dev, m) - mu[m]) ** 2})
        t = t.groupby(pd.qcut(t.mu, VAR_BUCKETS, duplicates="drop"), observed=True).mean()
        p, loga = np.polyfit(np.log(t.mu.values), np.log(t.r2.values), 1)
        model["var"][m] = [float(math.exp(loga)), float(p)]
    return model


def save_model(model: dict, path: str | Path, meta: dict | None = None):
    json.dump({"model": "props_v1", "tuned_on": "DEV 2014-2019", **(meta or {}), "minutes_features": MIN_FEATURES,
               "stat_features": STAT_FEATURES, "coef": model}, open(path, "w"), indent=2)


def load_model(path: str | Path) -> dict:
    return json.load(open(path))["coef"]


# ---- distribución ---------------------------------------------------------------------------
def variance(model: dict, market: str, mu: float) -> float:
    a, p = model["var"][market]
    return max(a * mu ** p, mu)                            # nunca menos dispersión que una Poisson


def survival(model: dict, market: str, mu: float, kmax: int | None = None) -> list[float]:
    """P(X >= k) para k = 0..kmax con una binomial negativa de media mu y la varianza del modelo
    (Poisson si la varianza no supera a la media). Con una línea L: P(más) = P(X >= floor(L) + 1)."""
    var = variance(model, market, mu)
    if kmax is None:
        kmax = int(math.ceil(mu + 6 * math.sqrt(var) + 5))
    pmf = np.empty(kmax + 1)
    if var <= mu * (1 + 1e-9):
        pmf[0] = math.exp(-mu)
        for k in range(1, kmax + 1):
            pmf[k] = pmf[k - 1] * mu / k
    else:
        r = mu * mu / (var - mu)
        q = mu / var                                       # prob. de "éxito" de la binomial negativa
        pmf[0] = q ** r
        for k in range(1, kmax + 1):
            pmf[k] = pmf[k - 1] * (k - 1 + r) / k * (1 - q)
    sv = 1.0 - np.concatenate([[0.0], np.cumsum(pmf)[:-1]])
    return np.clip(sv, 0.0, 1.0).tolist()


def prob_over_vec(model: dict, market: str, mu, line) -> np.ndarray:
    """Versión vectorial de `prob_over` (misma distribución) para evaluar muchos casos a la vez."""
    mu = np.asarray(mu, float)
    k_need = np.floor(np.asarray(line, float)).astype(int) + 1          # over <=> X >= k_need
    a, p = model["var"][market]
    var = np.maximum(a * mu ** p, mu)
    nb = var > mu * (1 + 1e-9)
    safe = np.where(nb, var - mu, 1.0)
    r = np.where(nb, mu * mu / safe, 1.0)
    q = np.where(nb, mu / np.where(nb, var, 1.0), 0.0)
    pmf = np.where(nb, q ** r, np.exp(-mu))
    cdf_below = np.zeros_like(mu)                                        # P(X <= k_need - 1)
    for k in range(0, int(k_need.max())):
        if k > 0:
            pmf = pmf * np.where(nb, (k - 1 + r) / k * (1 - q), mu / k)
        cdf_below = cdf_below + np.where(k < k_need, pmf, 0.0)
    return np.clip(1.0 - cdf_below, 0.0, 1.0)


def prob_over(model: dict, market: str, mu: float, line: float) -> float:
    """P(X > línea). Con línea entera, el empate (push) no cuenta como over."""
    k = int(math.floor(line)) + 1
    sv = survival(model, market, mu, kmax=max(k, 1))
    return float(sv[k])


def prob_push(model: dict, market: str, mu: float, line: float) -> float:
    if line != math.floor(line):
        return 0.0
    k = int(line)
    sv = survival(model, market, mu, kmax=k + 1)
    return float(sv[k] - sv[k + 1])
