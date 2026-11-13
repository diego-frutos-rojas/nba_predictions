"""Datos del sitio web (`webapp/`): reparte lo que ya calcula el portal diario en ficheros por día y de liga.

No cambia ningún modelo ni parámetro. Parte del estado de `daily.build_state` y le añade resúmenes descriptivos del
histórico (clasificación, forma de los equipos, cara a cara, registro de partidos de cada jugador), las predicciones
guardadas de días anteriores con su resultado real y el calendario de los próximos días.

`build_site` escribe una carpeta estática (HTML + CSS + JS + datos) que se abre con doble clic o se sube a cualquier
alojamiento estático. La única matemática que usa la página es el bloque CALC de `web/portal_template.html`, que se
extrae al generar el sitio para no tener una tercera copia.
"""
from __future__ import annotations

import json
import math
import re
import shutil
from pathlib import Path

import pandas as pd

from . import daily, espn, live, props
from .odds import remove_vig
from .webstate import TEAM_NAMES

EAST = ("ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET", "IND", "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS")
CONFERENCE = {t: ("Este" if t in EAST else "Oeste") for t in TEAM_NAMES}
FORM_N = 20                # partidos de la temporada en curso que se guardan por equipo
LOG_N = 20                 # partidos jugados que se guardan por jugador (pueden ser de la temporada anterior)
H2H_N = 10                 # enfrentamientos directos que se enseñan
BUNDLE_PAST_DAYS = 7       # días anteriores que caben en la versión de un solo archivo
SITE_PARTS = ("index.html", "assets", "data")


def _num(x, nd: int = 1):
    """Número listo para JSON: None si falta (NaN), redondeado si no."""
    if x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x):
        return None
    return round(float(x), nd)


# ---- resúmenes del histórico ------------------------------------------------------------------------
def team_frame(g: pd.DataFrame, team: str) -> pd.DataFrame:
    """Partidos de un equipo vistos desde su lado, de más antiguo a más reciente.

    `spread` es su hándicap de cierre (negativo = favorito) y `total` la línea de puntos totales."""
    h, a = g[g.home == team], g[g.away == team]
    out = pd.concat([
        pd.DataFrame({"date": h.date, "opp": h.away, "home": True, "pf": h.home_pts, "pa": h.away_pts,
                      "spread": h.close_spread_home, "total": h.close_total}),
        pd.DataFrame({"date": a.date, "opp": a.home, "home": False, "pf": a.away_pts, "pa": a.home_pts,
                      "spread": -a.close_spread_home, "total": a.close_total}),
    ])
    return out.sort_values("date", kind="stable").reset_index(drop=True)


def league_table(g: pd.DataFrame, ratings: dict, season: int) -> dict:
    """Balance de la temporada, nivel del modelo y forma reciente de los 30 equipos."""
    cur = g[g.season == season]
    rank = {t: i + 1 for i, t in enumerate(sorted(TEAM_NAMES, key=lambda t: -float(ratings.get(t, 0.0))))}
    out = {}
    for t, name in TEAM_NAMES.items():
        f = team_frame(cur, t)
        win, home = (f.pf > f.pa), f.home.astype(bool)
        out[t] = {
            "name": name, "conf": CONFERENCE[t], "rating": round(float(ratings.get(t, 0.0)), 2), "rank": rank[t],
            "w": int(win.sum()), "l": int((~win).sum()),
            "home": [int((win & home).sum()), int((~win & home).sum())],
            "away": [int((win & ~home).sum()), int((~win & ~home).sum())],
            "pf": _num(f.pf.mean()) if len(f) else None, "pa": _num(f.pa.mean()) if len(f) else None,
            # [fecha, rival, en casa, puntos a favor, en contra, hándicap de cierre propio, total de cierre]
            "form": [[str(r.date.date()), r.opp, int(r.home), int(r.pf), int(r.pa), _num(r.spread), _num(r.total)]
                     for r in f.tail(FORM_N).itertuples()],
        }
    return out


def season_players(g: pd.DataFrame, boxes: pd.DataFrame, season: int) -> list[dict]:
    """Medias por partido de cada jugador en la temporada (solo partidos jugados)."""
    b = boxes[boxes.played].merge(g.loc[g.season == season, ["game_id", "date"]], on="game_id")
    if b.empty:
        return []
    b = b.sort_values("date", kind="stable")
    a = b.groupby("pid", sort=False).agg(
        name=("name", "last"), team=("team", "last"), pos=("pos", "last"), gp=("game_id", "size"), gs=("starter", "sum"),
        min=("minutes", "mean"), pts=("pts", "mean"), reb=("reb", "mean"), ast=("ast", "mean"), fg3m=("fg3m", "mean"))
    return [{"pid": int(pid), "name": r.name, "team": r.team, "pos": r.pos, "gp": int(r.gp), "gs": int(r.gs),
             "min": _num(r.min), "pts": _num(r.pts), "reb": _num(r.reb), "ast": _num(r.ast), "fg3m": _num(r.fg3m)}
            for pid, r in zip(a.index, a.itertuples(index=False))]


def player_logs(g: pd.DataFrame, boxes: pd.DataFrame, pids, n: int = LOG_N) -> dict[str, list]:
    """Últimos `n` partidos jugados de cada jugador, de más antiguo a más reciente.

    Cada fila: [fecha, equipo, rival, en casa, titular, minutos, puntos, rebotes, asistencias, triples]."""
    b = boxes[boxes.pid.isin(set(pids)) & boxes.played].merge(g[["game_id", "date", "home", "away"]], on="game_id")
    b = b.sort_values("date", kind="stable")
    out = {}
    for pid, s in b.groupby("pid", sort=False):
        out[str(int(pid))] = [[str(r.date.date()), r.team, r.away if r.team == r.home else r.home, int(r.team == r.home),
                               int(bool(r.starter)), _num(r.minutes, 0), int(r.pts), int(r.reb), int(r.ast), int(r.fg3m)]
                              for r in s.tail(n).itertuples()]
    return out


def head_to_head(g: pd.DataFrame, a: str, b: str, n: int = H2H_N) -> list:
    """Últimos enfrentamientos entre dos equipos: [fecha, local, visitante, puntos local, puntos visitante]."""
    m = g[((g.home == a) & (g.away == b)) | ((g.home == b) & (g.away == a))].sort_values("date", kind="stable").tail(n)
    return [[str(r.date.date()), r.home, r.away, int(r.home_pts), int(r.away_pts)] for r in m.itertuples()]


def team_markets(game: dict) -> list[dict]:
    """Mercados de equipo de un partido (ganador, hándicap y total) con la probabilidad del modelo y la de la casa
    sin margen. No hay modelo de totales: ahí `p_model` es None."""
    m, k = game["model"], game["market"]

    def fair(a, b):
        if a and b and a > 1 and b > 1:
            pa, pb, _ = remove_vig(1 / a, 1 / b)
            return round(pa, 4), round(pb, 4)
        return None, None

    rows = []
    if k.get("ml_home") and k.get("ml_away") and k.get("prob_home") is not None:
        rows += [{"kind": "ganador", "side": "home", "line": None, "price": k["ml_home"],
                  "p_model": m["prob_home"], "p_market": k["prob_home"]},
                 {"kind": "ganador", "side": "away", "line": None, "price": k["ml_away"],
                  "p_model": round(1 - m["prob_home"], 4), "p_market": round(1 - k["prob_home"], 4)}]
    if k.get("spread_home") is not None and m.get("p_cover_home") is not None:
        fh, fa = fair(k.get("spread_odds_home"), k.get("spread_odds_away"))
        rows += [{"kind": "handicap", "side": "home", "line": k["spread_home"], "price": k.get("spread_odds_home"),
                  "p_model": m["p_cover_home"], "p_market": fh},
                 {"kind": "handicap", "side": "away", "line": -k["spread_home"], "price": k.get("spread_odds_away"),
                  "p_model": round(1 - m["p_cover_home"], 4), "p_market": fa}]
    if k.get("total") is not None:
        fo, fu = fair(k.get("over_odds"), k.get("under_odds"))
        rows += [{"kind": "total", "side": "over", "line": k["total"], "price": k.get("over_odds"), "p_model": None, "p_market": fo},
                 {"kind": "total", "side": "under", "line": k["total"], "price": k.get("under_odds"), "p_model": None, "p_market": fu}]
    return rows


# ---- días ---------------------------------------------------------------------------------------------
def today_day(state: dict, g: pd.DataFrame, boxes: pd.DataFrame) -> dict:
    """La jornada del estado: partidos (con mercados de equipo y cara a cara), jugadores y sus registros."""
    games = [{**x, "bets": team_markets(x), "h2h": head_to_head(g, x["home"], x["away"])} for x in state["games"]]
    return {"date": state["date"], "kind": "hoy", "games": games, "players": state["players"],
            "logs": player_logs(g, boxes, {p["pid"] for p in state["players"]})}


def past_day(pred: dict, g: pd.DataFrame, boxes: pd.DataFrame) -> dict:
    """Predicciones guardadas de un día anterior con lo que pasó de verdad (marcador y estadística real de cada línea)."""
    gi = g.drop_duplicates("game_id").set_index("game_id")
    bi = boxes[boxes.played].drop_duplicates(["game_id", "pid"]).set_index(["game_id", "pid"])
    games = []
    for x in pred["games"]:
        row = {**x, "home_name": TEAM_NAMES.get(x["home"], x["home"]), "away_name": TEAM_NAMES.get(x["away"], x["away"]), "state": "sin_resultado"}
        if x["game_id"] in gi.index:
            r = gi.loc[x["game_id"]]
            row.update(state="post", home_pts=int(r.home_pts), away_pts=int(r.away_pts))
        games.append(row)
    players = []
    for pl in pred["players"]:
        key = (pl["game_id"], pl["pid"])
        box = bi.loc[key] if key in bi.index else None
        markets = {}
        for m, mk in pl["markets"].items():
            if not mk.get("line"):
                continue                                         # solo se puntúan las líneas que tenían precio de la casa
            y = None if box is None else float(sum(box[s] for s in props.COMBOS.get(m, (m,))))
            markets[m] = {"mu": mk["mu"], "line": mk["line"], "eval": mk.get("eval"), "y": y}
        if markets:
            players.append({**{k: pl[k] for k in ("pid", "name", "team", "opp", "game_id", "status", "min")},
                            "played": box is not None, "markets": markets})
    return {"date": pred["date"], "kind": "pasado", "games": games, "players": players}


def upcoming_days(date, n: int, g: pd.DataFrame, fetch=None, log=print) -> list[dict]:
    """Calendario de los `n` días siguientes (solo horarios y cara a cara; las predicciones salen el día del partido)."""
    fetch = fetch or espn.fetch_scoreboard
    out = []
    for i in range(1, n + 1):
        d = (pd.Timestamp(date) + pd.Timedelta(days=i)).date()
        try:
            slate = [x for x in fetch(d) if x["season_type"] in (2, 3)]
        except Exception as e:                                   # sin calendario no se inventa nada: se deja de pedir
            log(f"  AVISO: no se pudo leer el calendario del {d} ({e}); el sitio se genera sin los días siguientes.")
            break
        if slate:
            out.append({"date": str(d), "kind": "futuro", "games": [
                {"game_id": x["game_id"], "home": x["home"], "away": x["away"], "home_name": TEAM_NAMES[x["home"]],
                 "away_name": TEAM_NAMES[x["away"]], "tip_utc": x["tip_utc"], "state": x["state"],
                 "h2h": head_to_head(g, x["home"], x["away"])} for x in slate]})
    return out


# ---- escritura del sitio --------------------------------------------------------------------------------
def calc_block(root: Path) -> str:
    """Bloque CALC de la plantilla del portal: la única matemática que repite el navegador."""
    tpl = (Path(root) / "web/portal_template.html").read_text(encoding="utf-8")
    m = re.search(r"/\*CALC-START\*/.*?/\*CALC-END\*/", tpl, re.S)
    assert m, "la plantilla del portal no tiene el bloque CALC"
    return m.group(0) + "\n"


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def site_data(root: str | Path, state: dict, upcoming: int = 6, fetch_scoreboard=None, log=print) -> dict:
    """Todo lo que enseña el sitio: índice, liga y un bloque por día (anteriores, hoy y próximos)."""
    root = Path(root)
    date = pd.Timestamp(state["date"])
    ds = live.build_dataset(root / "data/raw", root / "data/live", until=date)
    g, boxes = ds["games"], ds["boxes"]
    ratings = daily.run_elo(g, daily.load_params(root / "models/params_v2.json"))["state"].ratings
    days = {}
    for f in sorted((root / "data/predictions").glob("*.json")):
        if f.stem < state["date"]:
            with open(f, encoding="utf-8") as fh:
                days[f.stem] = past_day(json.load(fh), g, boxes)
    days[state["date"]] = today_day(state, g, boxes)
    for d in (upcoming_days(date, upcoming, g, fetch_scoreboard, log) if upcoming else []):
        days[d["date"]] = d
    index = {
        "today": state["date"], "generated_utc": state["generated_utc"], "season": state["season"],
        "data_through": state["data_through"], "warnings": state["warnings"], "labels": state["labels"],
        "markets": state["markets"], "combos": {k: list(v) for k, v in props.COMBOS.items()},
        "thresholds": state["thresholds"], "big_edge": state["big_edge"], "evidence": state["evidence"],
        "track": state.get("track") or {"days": 0},
        "days": [{"date": d, "kind": x["kind"], "n": len(x["games"])} for d, x in sorted(days.items())],
    }
    league = {"season": state["season"], "teams": league_table(g, ratings, state["season"]),
              "players": season_players(g, boxes, state["season"])}
    return {"index": index, "league": league, "days": days}


def _bundle(html: str, out: Path, extra: str) -> str:
    """Página de un solo archivo: mete dentro las hojas de estilo, los scripts y los datos."""
    def css(m):
        return "<style>\n" + (out / m.group(1)).read_text(encoding="utf-8") + "</style>"

    def script(m):
        return "<script>\n" + (out / m.group(1)).read_text(encoding="utf-8") + "</script>"

    html = re.sub(r'<link rel="stylesheet" href="([^"]+)">', css, html)
    html = html.replace("<!--DAYS-->", extra)
    return re.sub(r'<script src="([^"]+)"></script>', script, html)


def build_site(root: str | Path, state: dict, out: str | Path | None = None, upcoming: int = 6, fetch_scoreboard=None,
               bundle: str | Path | None = None, log=print) -> Path:
    """Genera el sitio estático en `out` (por defecto `webapp/dist`). Con `bundle`, además escribe una versión de un
    solo archivo (hoy, los próximos días y los últimos días anteriores) para compartir o abrir sin carpeta."""
    root = Path(root)
    src = root / "webapp/src"
    out = Path(out) if out else root / "webapp/dist"
    data = site_data(root, state, upcoming, fetch_scoreboard, log)
    out.mkdir(parents=True, exist_ok=True)
    for part in SITE_PARTS:                                      # solo se borra lo que este generador escribe
        p = out / part
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    shutil.copytree(src / "assets", out / "assets")
    (out / "assets/js/calc.js").write_text(calc_block(root), encoding="utf-8")
    (out / "data").mkdir()
    (out / "data/index.js").write_text(f"NBA.index={_js(data['index'])};\n", encoding="utf-8")
    (out / "data/league.js").write_text(f"NBA.league={_js(data['league'])};\n", encoding="utf-8")
    day_js = {d: f"NBA.days[{json.dumps(d)}]={_js(x)};\n" for d, x in data["days"].items()}
    for d, text in day_js.items():
        (out / f"data/day-{d}.js").write_text(text, encoding="utf-8")
    html = (src / "index.html").read_text(encoding="utf-8")
    assert "<!--DAYS-->" in html, "webapp/src/index.html no tiene el marcador de días"
    (out / "index.html").write_text(html.replace("<!--DAYS-->", ""), encoding="utf-8")
    if bundle:
        past = [d for d, x in data["days"].items() if x["kind"] == "pasado"][-BUNDLE_PAST_DAYS:]
        keep = [d for d, x in data["days"].items() if x["kind"] != "pasado" or d in past]
        index = {**data["index"], "days": [x for x in data["index"]["days"] if x["date"] in keep]}
        inline = f"<script>\nNBA.index={_js(index)};\n" + "".join(day_js[d] for d in keep) + "</script>"
        text = _bundle(html.replace('<script src="data/index.js"></script>', ""), out, inline)
        Path(bundle).parent.mkdir(parents=True, exist_ok=True)
        Path(bundle).write_text(text, encoding="utf-8")
    return out
