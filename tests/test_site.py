"""Tests del sitio web (webapp/): resúmenes del histórico, días anteriores con su resultado y generación de la carpeta."""
import copy
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from nba_model import props, site

ROOT = Path(__file__).resolve().parents[1]


def games_df():
    """Cuatro partidos inventados: BOS gana dos en casa, pierde uno fuera; el cuarto es de otra temporada."""
    rows = [
        ("g1", "2026-10-20", 2027, "BOS", "NYK", 110, 100, -4.5, 220.5),
        ("g2", "2026-10-22", 2027, "PHI", "BOS", 105, 99, -1.5, 215.0),
        ("g3", "2026-10-24", 2027, "BOS", "PHI", 120, 118, -6.0, float("nan")),
        ("g0", "2026-03-01", 2026, "NYK", "BOS", 90, 95, 2.0, 210.0),
    ]
    g = pd.DataFrame(rows, columns=["game_id", "date", "season", "home", "away", "home_pts", "away_pts", "close_spread_home", "close_total"])
    g["date"] = pd.to_datetime(g.date)
    return g.sort_values("date").reset_index(drop=True)


def boxes_df():
    rows = [   # game_id, team, pid, name, pos, minutes, played, starter, pts, reb, ast, fg3m
        ("g1", "BOS", 1, "Ana", "G", 30.0, True, True, 20.0, 5.0, 7.0, 3.0),
        ("g2", "BOS", 1, "Ana", "G", 28.0, True, True, 10.0, 4.0, 9.0, 1.0),
        ("g3", "BOS", 1, "Ana", "G", 0.0, False, False, 0.0, 0.0, 0.0, 0.0),
        ("g0", "NYK", 1, "Ana", "G", 25.0, True, False, 8.0, 2.0, 3.0, 0.0),
        ("g1", "NYK", 2, "Luis", "C", 33.0, True, True, 15.0, 12.0, 2.0, 0.0),
    ]
    return pd.DataFrame(rows, columns=["game_id", "team", "pid", "name", "pos", "minutes", "played", "starter", "pts", "reb", "ast", "fg3m"])


def test_team_frame_is_seen_from_the_team_side():
    f = site.team_frame(games_df(), "BOS")
    assert list(f.opp) == ["NYK", "NYK", "PHI", "PHI"] and list(f.home) == [False, True, False, True]
    assert list(f.pf) == [95, 110, 99, 120] and list(f.pa) == [90, 100, 105, 118]
    assert list(f.spread[:3]) == [-2.0, -4.5, 1.5]                        # fuera de casa el hándicap cambia de signo
    assert math.isnan(f.total.iloc[3])


def test_league_table_counts_only_the_season():
    t = site.league_table(games_df(), {"BOS": 5.0, "NYK": -1.0}, 2027)
    assert len(t) == 30 and set(t["BOS"]) >= {"name", "conf", "rating", "rank", "w", "l", "home", "away", "pf", "pa", "form"}
    bos = t["BOS"]
    assert (bos["w"], bos["l"], bos["home"], bos["away"]) == (2, 1, [2, 0], [0, 1])
    assert bos["rank"] == 1 and bos["conf"] == "Este" and t["LAL"]["conf"] == "Oeste" and t["LAL"]["form"] == []
    assert bos["pf"] == round((110 + 99 + 120) / 3, 1)
    assert [r[0] for r in bos["form"]] == ["2026-10-20", "2026-10-22", "2026-10-24"]        # antiguo -> reciente, sin la temporada anterior
    assert bos["form"][1] == ["2026-10-22", "PHI", 0, 99, 105, 1.5, 215.0] and bos["form"][2][6] is None
    assert sum(x["w"] for x in t.values()) == sum(x["l"] for x in t.values()) == 3
    assert sum(1 for x in t.values() if x["conf"] == "Este") == 15


def test_player_logs_season_players_and_head_to_head():
    g, b = games_df(), boxes_df()
    logs = site.player_logs(g, b, [1, 2])
    assert set(logs) == {"1", "2"}
    assert logs["1"] == [["2026-03-01", "NYK", "BOS", 1, 0, 25.0, 8, 2, 3, 0],              # con su equipo anterior
                         ["2026-10-20", "BOS", "NYK", 1, 1, 30.0, 20, 5, 7, 3],
                         ["2026-10-22", "BOS", "PHI", 0, 1, 28.0, 10, 4, 9, 1]]             # el partido que no jugó no cuenta
    assert site.player_logs(g, b, [1], n=1)["1"][0][0] == "2026-10-22"
    sp = {p["pid"]: p for p in site.season_players(g, b, 2027)}
    assert sp[1] == {"pid": 1, "name": "Ana", "team": "BOS", "pos": "G", "gp": 2, "gs": 2, "min": 29.0, "pts": 15.0, "reb": 4.5, "ast": 8.0, "fg3m": 2.0}
    assert sp[2]["gp"] == 1 and site.season_players(g, b, 2030) == []
    h = site.head_to_head(g, "BOS", "NYK")
    assert h == [["2026-03-01", "NYK", "BOS", 90, 95], ["2026-10-20", "BOS", "NYK", 110, 100]] and site.head_to_head(g, "LAL", "BOS") == []


def test_team_markets_probabilities():
    game = {"model": {"prob_home": 0.6, "p_cover_home": 0.45},
            "market": {"ml_home": 1.5, "ml_away": 2.7, "prob_home": 0.6429, "spread_home": -4.5, "spread_odds_home": 1.9, "spread_odds_away": 1.9,
                       "total": 220.5, "over_odds": 1.8, "under_odds": 2.0}}
    rows = {(r["kind"], r["side"]): r for r in site.team_markets(game)}
    assert len(rows) == 6
    assert rows["ganador", "home"]["p_market"] == 0.6429 and math.isclose(rows["ganador", "away"]["p_model"], 0.4)
    assert rows["handicap", "home"]["line"] == -4.5 and rows["handicap", "away"]["line"] == 4.5
    assert rows["handicap", "home"]["p_market"] == 0.5 and math.isclose(rows["handicap", "away"]["p_model"], 0.55)
    assert rows["total", "over"]["p_model"] is None                       # no hay modelo de totales
    assert math.isclose(rows["total", "over"]["p_market"] + rows["total", "under"]["p_market"], 1.0, abs_tol=1e-4)
    assert rows["total", "over"]["p_market"] > 0.5
    assert site.team_markets({"model": {"prob_home": 0.6, "p_cover_home": None}, "market": {}}) == []


def test_past_day_joins_predictions_with_what_happened():
    line = {"value": 30.5, "over": 1.9, "under": 1.9, "side_ok": True}
    pred = {"date": "2026-10-20", "games": [
        {"game_id": "g1", "home": "BOS", "away": "NYK", "tip_utc": "2026-10-20T23:00Z", "model": {"prob_home": 0.7}, "market": {"prob_home": 0.6}, "gap_pts": 1.0},
        {"game_id": "zz", "home": "LAL", "away": "DEN", "tip_utc": "2026-10-21T02:00Z", "model": {"prob_home": 0.5}, "market": {}, "gap_pts": None}],
        "players": [
            {"pid": 1, "name": "Ana", "team": "BOS", "opp": "NYK", "game_id": "g1", "status": "available", "min": 30.0,
             "markets": {"pra": {"mu": 33.0, "line": line, "eval": {"side": "over", "edge": 0.08}}, "pts": {"mu": 20.0}}},
            {"pid": 9, "name": "No Jugó", "team": "NYK", "opp": "BOS", "game_id": "g1", "status": "questionable", "min": 20.0,
             "markets": {"pts": {"mu": 10.0, "line": {"value": 9.5, "over": 1.9, "under": 1.9, "side_ok": True}, "eval": {"side": "under", "edge": 0.02}}}},
            {"pid": 2, "name": "Luis", "team": "NYK", "opp": "BOS", "game_id": "g1", "status": "available", "min": 30.0, "markets": {"pts": {"mu": 14.0}}}]}
    d = site.past_day(pred, games_df(), boxes_df())
    assert d["kind"] == "pasado" and d["date"] == "2026-10-20"
    g1, zz = d["games"]
    assert (g1["state"], g1["home_pts"], g1["away_pts"], g1["home_name"]) == ("post", 110, 100, "Boston Celtics")
    assert zz["state"] == "sin_resultado" and "home_pts" not in zz
    assert [p["name"] for p in d["players"]] == ["Ana", "No Jugó"]         # sin línea de la casa no hay nada que puntuar
    ana, out = d["players"]
    assert ana["played"] and ana["markets"] == {"pra": {"mu": 33.0, "line": line, "eval": {"side": "over", "edge": 0.08}, "y": 32.0}}
    assert not out["played"] and out["markets"]["pts"]["y"] is None        # no jugó: la línea se anula
    json.dumps(d, allow_nan=False)


def test_upcoming_days_stops_when_the_calendar_fails():
    g = games_df()
    slate = lambda d: [{"game_id": "f1", "home": "BOS", "away": "NYK", "tip_utc": f"{d}T23:00Z", "state": "pre", "season_type": 2},
                       {"game_id": "f2", "home": "LAL", "away": "DEN", "tip_utc": f"{d}T23:00Z", "state": "pre", "season_type": 1}]
    days = site.upcoming_days("2026-10-25", 2, g, fetch=slate, log=lambda *a: None)
    assert [d["date"] for d in days] == ["2026-10-26", "2026-10-27"] and all(d["kind"] == "futuro" for d in days)
    assert [x["game_id"] for x in days[0]["games"]] == ["f1"]              # la pretemporada no entra
    assert days[0]["games"][0]["h2h"][-1][0] == "2026-10-20" and days[0]["games"][0]["away_name"] == "New York Knicks"

    def broken(d):
        raise RuntimeError("sin red")
    msgs = []
    assert site.upcoming_days("2026-10-25", 3, g, fetch=broken, log=msgs.append) == [] and len(msgs) == 1


@pytest.fixture(scope="module")
def site_root(make_root):
    return make_root("sitio", ("data/raw", "models", "web", "webapp"))


@pytest.fixture(scope="module")
def data(site_root, state):
    slate = lambda d: [{"game_id": "f1", "home": "BOS", "away": "NYK", "tip_utc": f"{d}T23:00Z", "state": "pre", "season_type": 2}]
    return site.site_data(site_root, copy.deepcopy(state), upcoming=2, fetch_scoreboard=slate, log=lambda *a: None)


def test_site_data_is_consistent_with_the_state(data, state):
    idx, today = data["index"], data["days"][state["date"]]
    assert idx["today"] == "2026-11-10" and [(d["date"], d["kind"]) for d in idx["days"]] == [
        ("2026-11-10", "hoy"), ("2026-11-11", "futuro"), ("2026-11-12", "futuro")]
    assert idx["combos"] == {k: list(v) for k, v in props.COMBOS.items()} and idx["thresholds"] == state["thresholds"]
    assert today["kind"] == "hoy" and len(today["games"]) == len(state["games"]) and today["players"] == state["players"]
    for g in today["games"]:
        assert {(b["kind"], b["side"]) for b in g["bets"]} <= {("ganador", "home"), ("ganador", "away"), ("handicap", "home"),
                                                               ("handicap", "away"), ("total", "over"), ("total", "under")}
        assert all(r[0] < state["date"] for r in g["h2h"])                # nada del día ni posterior
    # el registro de partidos coincide con la serie reciente que usa el modelo de jugadores
    checked = 0
    for p in state["players"]:
        rows = today["logs"].get(str(p["pid"]), [])
        assert all(r[0] < state["date"] for r in rows) and len(rows) <= site.LOG_N
        last = p["markets"]["pts"]["last"]
        if len(rows) >= len(last) > 0:
            assert [r[6] for r in rows[-len(last):]] == last, p["name"]
            pra = [r[6] + r[7] + r[8] for r in rows[-len(last):]]
            assert pra == p["markets"]["pra"]["last"]
            checked += 1
    assert checked > 50
    teams = data["league"]["teams"]
    assert len(teams) == 30 and sum(t["w"] for t in teams.values()) == sum(t["l"] for t in teams.values()) > 0
    assert sorted(t["rank"] for t in teams.values()) == list(range(1, 31))
    assert all(r[0] < state["date"] for t in teams.values() for r in t["form"])
    nyk = next(g for g in state["games"] if g["home"] == "NYK")["model"]
    assert math.isclose(teams["NYK"]["rating"], nyk["rating_home"], abs_tol=0.011)          # mismo nivel que usa la predicción
    assert len(data["league"]["players"]) > 300 and all(p["gp"] >= 1 for p in data["league"]["players"])
    json.dumps(data)


def test_build_site_writes_a_static_folder(site_root, state, tmp_path):
    out = tmp_path / "dist"
    (out / "data").mkdir(parents=True)
    (out / "data/day-1999-01-01.js").write_text("viejo")                  # restos de una generación anterior
    (out / "notas.txt").write_text("mío")                                 # algo que no es del generador
    bundle = tmp_path / "uno/sitio.html"
    res = site.build_site(site_root, copy.deepcopy(state), out, upcoming=0, bundle=bundle, log=lambda *a: None)
    assert res == out and (out / "notas.txt").read_text() == "mío" and not (out / "data/day-1999-01-01.js").exists()
    assert sorted(p.name for p in (out / "data").iterdir()) == ["day-2026-11-10.js", "index.js", "league.js"]
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "<!--DAYS-->" not in html
    for src in re.findall(r'(?:src|href)="([^"]+)"', html):               # todo lo que pide la página existe y es local
        assert not src.startswith(("http", "//")) and (out / src).is_file(), src
    # la matemática del navegador es exactamente el bloque CALC de la plantilla del portal (no hay tercera copia)
    tpl = (ROOT / "web/portal_template.html").read_text(encoding="utf-8")
    calc = (out / "assets/js/calc.js").read_text(encoding="utf-8")
    assert calc.strip() in tpl and "function sideEval" in calc and "function edgeBucket" in calc
    sources = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "webapp/src/assets/js").glob("*.js"))
    assert "function sideEval" not in sources and "function edgeBucket" not in sources
    for name, prefix in (("index.js", "NBA.index="), ("league.js", "NBA.league="), ("day-2026-11-10.js", 'NBA.days["2026-11-10"]=')):
        text = (out / "data" / name).read_text(encoding="utf-8")
        assert text.startswith(prefix) and text.endswith(";\n")
        json.loads(text[len(prefix):-2])
    one = bundle.read_text(encoding="utf-8")
    assert 'src="' not in one and 'rel="stylesheet"' not in one and "NBA.index=" in one and 'NBA.days["2026-11-10"]=' in one and "NBA.league=" in one
    node = shutil.which("node")
    if node is None:
        pytest.skip("node no está instalado")
    for f in sorted((out / "assets/js").glob("*.js")):
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
