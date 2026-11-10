"""Caché local de datos en vivo (data/live/) y dataset completo hasta ayer.

Los ficheros crudos de GitHub (data/raw) suelen ir 1-2 días por detrás. Este módulo completa lo que falta con
ESPN y lo guarda en CSV para no volver a pedirlo:
  results.csv  partidos terminados que aún no están en data/raw
  boxes.csv    cajas de jugador de esos partidos
  odds.csv     última cuota de DraftKings vista de cada partido (para los jugados es la de cierre)
  props.csv    última línea de props vista de cada jugador y mercado
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import espn, props
from .availability import compute_availability, load_boxes
from .data import add_rest, build_games

RESULT_COLS = ["game_id", "date", "season", "home", "away", "home_pts", "away_pts", "neutral"]
BOX_COLS = props.BOX_OUT + ["gs"]
ODDS_COLS = ["game_id", "provider", "spread_home", "total", "ml_home", "ml_away", "spread_odds_home",
             "spread_odds_away", "over_odds", "under_odds"]
PROP_COLS = ["game_id", "pid", "market", "line", "over", "under", "side_ok"]


def _read(path: Path, cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype={"game_id": str})
    if "date" in df:
        df["date"] = pd.to_datetime(df["date"])
    return df


def read_cache(live_dir: str | Path) -> dict[str, pd.DataFrame]:
    d = Path(live_dir)
    return {"results": _read(d / "results.csv", RESULT_COLS), "boxes": _read(d / "boxes.csv", BOX_COLS),
            "odds": _read(d / "odds.csv", ODDS_COLS), "props": _read(d / "props.csv", PROP_COLS)}


def upsert(path: Path, new: pd.DataFrame, keys: list[str], cols: list[str]) -> pd.DataFrame:
    """Añade filas a un CSV sustituyendo las que tengan la misma clave (la última vista gana)."""
    old = _read(path, cols)
    new = new[cols].copy()
    new["game_id"] = new["game_id"].astype(str)
    df = new if old.empty else pd.concat([old, new], ignore_index=True)
    df = df.drop_duplicates(keys, keep="last").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def sync_results(raw_dir: str | Path, live_dir: str | Path, until, log=print) -> None:
    """Descarga de ESPN los partidos terminados (resultado + caja) posteriores a lo que hay en data/raw, hasta
    la fecha `until` incluida. Solo temporada regular."""
    live_dir = Path(live_dir)
    g = build_games(raw_dir)
    have = set(g.game_id) | set(read_cache(live_dir)["results"].game_id)
    day = g.date.max().normalize()                               # se repasa el último día por si quedó a medias
    until = pd.Timestamp(until).normalize()
    while day <= until:
        for ev in espn.fetch_scoreboard(day.date()):
            if ev["game_id"] in have or not ev["completed"] or ev["season_type"] != 2:
                continue
            head, rows = espn.fetch_box(ev["game_id"])
            if not rows or not any(r["played"] for r in rows):
                log(f"  aviso: {ev['away']}@{ev['home']} ({day.date()}) terminado pero sin caja todavía; se omite")
                continue
            res = pd.DataFrame([{**{k: ev[k] for k in ("game_id", "season", "home", "away", "home_pts", "away_pts", "neutral")},
                                 "date": day}])
            upsert(live_dir / "boxes.csv", pd.DataFrame(rows), ["game_id", "pid"], BOX_COLS)
            upsert(live_dir / "results.csv", res, ["game_id"], RESULT_COLS)
            have.add(ev["game_id"])
            log(f"  + {ev['away']}@{ev['home']} {ev['away_pts']}-{ev['home_pts']} ({day.date()})")
        day += pd.Timedelta(days=1)


def save_market(live_dir: str | Path, game_id: str, odds: dict | None, prop_rows: list[dict]) -> None:
    live_dir = Path(live_dir)
    if odds:
        upsert(live_dir / "odds.csv", pd.DataFrame([{"game_id": game_id, **odds}]), ["game_id"], ODDS_COLS)
    if prop_rows:
        upsert(live_dir / "props.csv", pd.DataFrame([{"game_id": game_id, **r} for r in prop_rows]),
               ["game_id", "pid", "market"], PROP_COLS)


def build_dataset(raw_dir: str | Path, live_dir: str | Path | None = None, until=None) -> dict:
    """Partidos (con descanso, disponibilidad y líneas) y cajas hasta `until` (excluida), uniendo data/raw y la caché.

    Devuelve dict con games, av_tracker (disponibilidad), boxes (para el modelo de jugadores) y names."""
    g = build_games(raw_dir)
    ab = load_boxes(raw_dir, with_names=True)
    cache = read_cache(live_dir) if live_dir is not None else None
    extra_boxes = None
    if cache is not None:
        res = cache["results"][~cache["results"].game_id.isin(set(g.game_id))].copy()
        if len(res):
            res["neutral"] = res.neutral.astype(bool)
            res["source"] = "espn_live"
            res["home_margin"] = res.home_pts - res.away_pts
            for c in ("close_spread_home", "close_ml_home", "close_ml_away", "close_total"):
                res[c] = np.nan
            g = pd.concat([g, res[g.columns]], ignore_index=True)
        od = cache["odds"].drop_duplicates("game_id").set_index("game_id")
        if len(od):                                             # líneas de DraftKings donde no hay otra fuente
            for src, dst in (("spread_home", "close_spread_home"), ("total", "close_total"),
                             ("ml_home", "close_ml_home"), ("ml_away", "close_ml_away")):
                fill = g.game_id.map(od[src])
                g[dst] = g[dst].where(g[dst].notna(), fill)
        extra_boxes = cache["boxes"]
        if len(extra_boxes):
            eb = extra_boxes[~extra_boxes.game_id.isin(set(ab.game_id))]
            ab = pd.concat([ab, eb[["name", "gs", "game_id", "team", "pid", "minutes", "played"]]], ignore_index=True)
    if until is not None:
        g = g[g.date < pd.Timestamp(until).normalize()]
    g = add_rest(g)
    g, av = compute_availability(g, ab, return_tracker=True)
    pb = props.load_player_boxes(raw_dir, extra=extra_boxes)
    return {"games": g, "av_tracker": av, "boxes": pb, "names": dict(zip(ab.pid.astype(int), ab.name))}
