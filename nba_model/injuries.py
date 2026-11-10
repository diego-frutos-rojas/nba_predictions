"""Gancho para ajustar el modelo por lesiones (HOY devuelve 0 si no hay tabla de impacto).

TODO (prioridad alta): rellenar data/player_impact.csv con el impacto de cada jugador
en puntos de margen por 100 posesiones (EPM, RAPM, BPM o on/off). Sin esto el modelo
no ve lesiones, que es la mayor causa de discrepancia con el mercado.
"""
from __future__ import annotations

import csv
from pathlib import Path

PLAY_PROB = {"out": 0.0, "questionable": 0.5, "doubtful": 0.2, "probable": 0.85, "available": 1.0}


def load_impact(path: str | Path) -> dict[str, float]:
    """CSV: player,team,impact_pts"""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {r["player"]: float(r["impact_pts"]) for r in csv.DictReader(f) if r.get("impact_pts")}


def team_adjustment(injuries: list[dict], impact: dict[str, float]) -> float:
    """Puntos perdidos por un equipo (valor <= 0): suma de impacto * P(no juega)."""
    lost = 0.0
    for it in injuries:
        play = PLAY_PROB.get(it.get("status", "listed"), 0.5)
        lost -= impact.get(it["player"], 0.0) * (1 - play)
    return lost


def game_adjustment(game: dict, impact: dict[str, float]) -> float:
    """Ajuste en puntos a favor del local (+ ayuda al local).

    Lo que pierde el local (valor negativo) le resta; lo que pierde el visitante le suma.
    """
    inj = game.get("injuries", {})
    return team_adjustment(inj.get("home", []), impact) - team_adjustment(inj.get("away", []), impact)
