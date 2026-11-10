"""Datos en vivo de la API pública de ESPN (sin clave): jornada, cuotas de DraftKings, lesiones, cajas y props.

Las funciones `parse_*` son puras (reciben el JSON ya descargado) y tienen tests con respuestas reales
guardadas en `tests/fixtures/`. Las funciones `fetch_*` solo descargan y llaman a las anteriores.

Convenciones del proyecto: equipos con el código canónico (`data.ABBR`), spread del local (< 0 = local
favorito), cuotas americanas, fecha del partido = fecha en la costa este de EE. UU. (la que usa ESPN).
"""
from __future__ import annotations

import json
import math
import re
import time
import urllib.error
import urllib.request

from .data import ABBR

SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
DRAFTKINGS = "100"                                   # id del proveedor de cuotas en ESPN

# Mercado de ESPN -> clave del modelo (solo los over/under que proyectamos)
PROP_TOTALS = {
    "Total Points": "pts", "Total Rebounds": "reb", "Total Assists": "ast", "Total 3-Point Field Goals": "fg3m",
    "Total Points, Rebounds, and Assists": "pra", "Total Points and Rebounds": "pr", "Total Points and Assists": "pa",
    "Total Assists and Rebounds": "ra",
}
PROP_MILESTONES = {
    "Points Milestones": "pts", "Rebounds Milestones": "reb", "Assists Milestones": "ast",
    "3-Point Field Goals Milestones": "fg3m", "Points + Assists + Rebounds Milestones": "pra",
    "Points + Rebounds Milestones": "pr", "Points + Assists Milestones": "pa", "Rebounds + Assists Milestones": "ra",
}
# Estado del parte de lesiones de ESPN -> estado del modelo (ver injuries.PLAY_PROB)
INJURY_STATUS = {"out": "out", "day-to-day": "questionable", "doubtful": "doubtful", "questionable": "questionable",
                 "probable": "probable", "suspension": "out"}


def get_json(url: str, retries: int = 3, timeout: int = 40):
    """GET con reintentos. Devuelve None si el recurso no existe (404)."""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (nba-model)", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except Exception as e:                                       # red caída, tiempo agotado, JSON cortado
            last = e
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"no se pudo descargar {url}: {last}")


def _american(x) -> int | None:
    """'-110', '+670', 'EVEN', -110.0 -> entero; None si no es una cuota americana válida."""
    if x is None:
        return None
    if isinstance(x, str):
        t = x.strip().upper().replace("−", "-")
        if t in ("EVEN", "EV"):
            return 100
        try:
            x = float(t)
        except ValueError:
            return None
    v = int(round(float(x)))
    return v if abs(v) >= 100 else None


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        return float(str(x).replace("−", "-").lstrip("ou+"))
    except ValueError:
        return None


def _side(d: dict, *path):
    for k in path:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def parse_scoreboard_odds(odds: list | None) -> dict | None:
    """Cuotas del marcador (site API). Prioriza los campos explícitos por lado ('close' = precio actual)."""
    if not odds:
        return None
    o = odds[0]
    spread = _num(_side(o, "pointSpread", "home", "close", "line"))
    if spread is None and o.get("spread") is not None:
        spread = float(o["spread"])                              # ya viene desde el punto de vista del local
        hf, af = _side(o, "homeTeamOdds", "favorite"), _side(o, "awayTeamOdds", "favorite")
        if hf and spread > 0 or af and spread < 0:
            return None                                          # incoherente: mejor no usarlo que usarlo al revés
    total = _num(_side(o, "total", "over", "close", "line"))
    if total is None:
        total = _num(o.get("overUnder"))
    return {
        "provider": _side(o, "provider", "name"),
        "spread_home": spread, "total": total,
        "spread_home_open": _num(_side(o, "pointSpread", "home", "open", "line")),
        "total_open": _num(_side(o, "total", "over", "open", "line")),
        "ml_home": _american(_side(o, "moneyline", "home", "close", "odds")),
        "ml_away": _american(_side(o, "moneyline", "away", "close", "odds")),
        "spread_odds_home": _american(_side(o, "pointSpread", "home", "close", "odds")),
        "spread_odds_away": _american(_side(o, "pointSpread", "away", "close", "odds")),
        "over_odds": _american(_side(o, "total", "over", "close", "odds")),
        "under_odds": _american(_side(o, "total", "under", "close", "odds")),
    }


def parse_core_odds(d: dict | None, provider: str = DRAFTKINGS) -> dict | None:
    """Cuotas de un partido (core API, sirve también para partidos ya jugados: línea de cierre)."""
    if not d:
        return None
    items = [x for x in d.get("items", []) if str(_side(x, "provider", "id")) == provider]
    if not items:
        return None
    o = items[0]
    h, a = o.get("homeTeamOdds") or {}, o.get("awayTeamOdds") or {}
    spread = None
    for k in ("close", "current"):
        spread = _num(_side(h, k, "pointSpread", "american"))
        if spread is not None:
            break
    if spread is None and o.get("spread") is not None:
        spread = float(o["spread"])
    if spread is not None and (h.get("favorite") and spread > 0 or a.get("favorite") and spread < 0):
        return None
    return {"provider": _side(o, "provider", "name"), "spread_home": spread, "total": _num(o.get("overUnder")),
            "ml_home": _american(h.get("moneyLine")), "ml_away": _american(a.get("moneyLine")),
            "spread_odds_home": _american(h.get("spreadOdds")), "spread_odds_away": _american(a.get("spreadOdds")),
            "over_odds": _american(o.get("overOdds")), "under_odds": _american(o.get("underOdds"))}


def parse_scoreboard(d: dict) -> list[dict]:
    """Partidos de una jornada: equipos, estado, marcador y cuotas. Ignora partidos que no son de la NBA (All-Star)."""
    out = []
    for e in d.get("events", []):
        c = e["competitions"][0]
        side = {x["homeAway"]: x for x in c["competitors"]}
        h, a = side["home"]["team"].get("abbreviation"), side["away"]["team"].get("abbreviation")
        if h not in ABBR or a not in ABBR:
            continue
        st = e["status"]["type"]
        out.append({
            "game_id": str(e["id"]), "tip_utc": e["date"], "home": ABBR[h], "away": ABBR[a],
            "state": st.get("state"), "completed": bool(st.get("completed")), "status": st.get("name"),
            "detail": st.get("shortDetail"),
            "home_pts": int(side["home"].get("score") or 0), "away_pts": int(side["away"].get("score") or 0),
            "neutral": bool(c.get("neutralSite")),
            "season": int(e["season"]["year"]), "season_type": int(e["season"]["type"]),
            "odds": parse_scoreboard_odds(c.get("odds")),
        })
    return out


def parse_injuries(d: dict) -> list[dict]:
    """Parte de lesiones de toda la liga: una fila por jugador con su id de ESPN y el estado del modelo."""
    out = []
    for t in d.get("injuries", []):
        for x in t.get("injuries", []):
            ath = x.get("athlete") or {}
            team = _side(ath, "team", "abbreviation")
            pid = ath.get("id")
            if pid is None:
                for ln in ath.get("links") or []:
                    m = re.search(r"/id/(\d+)", ln.get("href", ""))
                    if m:
                        pid = m.group(1)
                        break
            raw = (x.get("status") or "").strip()
            det = x.get("details") or {}
            out.append({
                "team": ABBR.get(team), "pid": int(pid) if pid is not None else None, "player": ath.get("displayName"),
                "status": INJURY_STATUS.get(raw.lower(), "questionable"), "status_raw": raw,
                "detail": " ".join(str(det[k]) for k in ("side", "type", "detail") if det.get(k)),
                "comment": x.get("shortComment") or "", "updated": x.get("date"),
            })
    return out


def _made(x: str) -> float:
    """'5-10' -> 5 (canastas anotadas)."""
    try:
        return float(str(x).split("-")[0])
    except ValueError:
        return 0.0


def parse_box(d: dict) -> tuple[dict, list[dict]]:
    """Caja de un partido (summary). Devuelve (cabecera, filas con las columnas de `props.BOX_OUT` + `gs`)."""
    comp = d["header"]["competitions"][0]
    side = {x["homeAway"]: x for x in comp["competitors"]}
    head = {"game_id": str(d["header"]["id"]), "completed": bool(comp["status"]["type"].get("completed")),
            "home": ABBR.get(side["home"]["team"]["abbreviation"]), "away": ABBR.get(side["away"]["team"]["abbreviation"]),
            "home_pts": int(side["home"].get("score") or 0), "away_pts": int(side["away"].get("score") or 0)}
    rows = []
    for t in d.get("boxscore", {}).get("players", []):
        team = ABBR.get(t["team"]["abbreviation"])
        for block in t.get("statistics", []):
            keys = block.get("keys") or []
            ix = {k: i for i, k in enumerate(keys)}
            for a in block.get("athletes", []):
                st = a.get("stats") or []
                dnp = bool(a.get("didNotPlay")) or not st
                g = lambda k: (st[ix[k]] if (not dnp and k in ix and ix[k] < len(st)) else "0")    # noqa: E731
                f = lambda k: (float(g(k)) if str(g(k)).lstrip("+-").replace(".", "", 1).isdigit() else 0.0)   # noqa: E731
                mins = f("minutes")
                fgm, fga = _made(g("fieldGoalsMade-fieldGoalsAttempted")), 0.0
                parts = str(g("fieldGoalsMade-fieldGoalsAttempted")).split("-")
                fga = float(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 0.0
                ftp = str(g("freeThrowsMade-freeThrowsAttempted")).split("-")
                ftm = float(ftp[0]) if ftp[0].isdigit() else 0.0
                fta = float(ftp[1]) if len(ftp) == 2 and ftp[1].isdigit() else 0.0
                pts, reb, ast = f("points"), f("rebounds"), f("assists")
                gs = (pts + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * f("offensiveRebounds")
                      + 0.3 * f("defensiveRebounds") + f("steals") + 0.7 * ast + 0.7 * f("blocks")
                      - 0.4 * f("fouls") - f("turnovers"))                       # Game Score, igual que availability
                rows.append({
                    "game_id": head["game_id"], "team": team, "pid": int(a["athlete"]["id"]),
                    "name": a["athlete"].get("displayName", ""),
                    "pos": _side(a["athlete"], "position", "abbreviation") or "",
                    "minutes": mins, "played": (not dnp) and mins > 0, "starter": bool(a.get("starter")),
                    "pts": pts, "reb": reb, "ast": ast,
                    "fg3m": _made(g("threePointFieldGoalsMade-threePointFieldGoalsAttempted")), "gs": gs,
                })
    return head, rows


def _athlete_id(x: dict) -> int | None:
    m = re.search(r"/athletes/(\d+)", _side(x, "athlete", "$ref") or "")
    return int(m.group(1)) if m else None


def _implied(odds: int) -> float:
    return -odds / (-odds + 100) if odds < 0 else 100 / (odds + 100)


def parse_props(items: list[dict]) -> list[dict]:
    """Líneas over/under de jugador. Devuelve filas {pid, market, line, over, under, side_ok}.

    ESPN no etiqueta qué precio es el over y cuál el under: los da siempre en ese orden (over primero). Se
    comprueba con el mercado de "hitos" (p. ej. '10+ puntos' es lo mismo que más de 9,5): si el hito existe y
    contradice el orden, `side_ok` es False y los precios no deben usarse para valor esperado (la línea sí)."""
    totals: dict[tuple, list] = {}
    miles: dict[tuple, int] = {}
    for x in items:
        name = _side(x, "type", "name")
        pid = _athlete_id(x)
        if pid is None:
            continue
        price = _american(_side(x, "odds", "american", "value"))
        if name in PROP_TOTALS:
            line = _num(_side(x, "odds", "total", "value"))
            if line is not None:
                totals.setdefault((pid, PROP_TOTALS[name]), []).append((line, price))
        elif name in PROP_MILESTONES and price is not None:
            tgt = _side(x, "current", "target", "value")
            if tgt is not None:
                miles[(pid, PROP_MILESTONES[name], float(tgt))] = price
    out = []
    for (pid, market), v in totals.items():
        if len(v) != 2 or v[0][0] != v[1][0]:
            continue                                              # mercado incompleto o con dos líneas distintas
        line, over, under = v[0][0], v[0][1], v[1][1]
        ok = over is not None and under is not None
        ms = miles.get((pid, market, math.floor(line) + 1.0))
        if ok and ms is not None:
            d_over, d_under = abs(_implied(over) - _implied(ms)), abs(_implied(under) - _implied(ms))
            if d_under + 0.02 < d_over:                           # el hito se parece claramente más al 2.º precio
                ok = False
        out.append({"pid": pid, "market": market, "line": line, "over": over, "under": under, "side_ok": ok})
    return out


# ---- descargas ---------------------------------------------------------------------------------
def fetch_scoreboard(date) -> list[dict]:
    """Jornada de una fecha (objeto date o 'AAAA-MM-DD', fecha de la costa este)."""
    d = get_json(f"{SITE}/scoreboard?dates={str(date).replace('-', '')[:8]}&limit=100")
    return parse_scoreboard(d or {})


def fetch_injuries() -> list[dict]:
    return parse_injuries(get_json(f"{SITE}/injuries") or {})


def fetch_box(game_id: str) -> tuple[dict, list[dict]]:
    d = get_json(f"{SITE}/summary?event={game_id}")
    return parse_box(d) if d and d.get("header") else ({"game_id": str(game_id), "completed": False}, [])


def fetch_game_odds(game_id: str) -> dict | None:
    return parse_core_odds(get_json(f"{CORE}/events/{game_id}/competitions/{game_id}/odds"))


def fetch_props(game_id: str) -> list[dict]:
    """Props de DraftKings de un partido (todas las páginas). Lista vacía si ESPN no las tiene."""
    items, page = [], 1
    while True:
        d = get_json(f"{CORE}/events/{game_id}/competitions/{game_id}/odds/{DRAFTKINGS}/propBets?limit=1000&page={page}")
        if not d:
            break
        items += d.get("items", [])
        if page >= int(d.get("pageCount") or 1):
            break
        page += 1
    return parse_props(items)
