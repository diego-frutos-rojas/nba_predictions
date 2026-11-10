"""Tests de los lectores de ESPN con respuestas reales recortadas (tests/fixtures/, 10-nov-2026)."""
import json
from pathlib import Path

import pytest

from nba_model import espn

FIX = Path(__file__).parent / "fixtures"
load = lambda name: json.load(open(FIX / name, encoding="utf-8"))      # noqa: E731


def test_scoreboard_teams_and_odds():
    sb = espn.parse_scoreboard(load("scoreboard_2026-11-10.json"))
    assert [(x["away"], x["home"]) for x in sb] == [("MIL", "NYK"), ("BOS", "PHI"), ("LAC", "PHX"), ("MIA", "UTA"),
                                                    ("ORL", "SAC"), ("OKC", "POR")]
    nyk, uta = sb[0], sb[3]
    assert nyk["state"] == "pre" and not nyk["completed"] and nyk["season"] == 2027 and nyk["season_type"] == 2
    o = nyk["odds"]
    assert o["spread_home"] == -15.5 and o["total"] == 220.5 and o["ml_home"] == -1040 and o["ml_away"] == 670
    assert o["over_odds"] == -115 and o["under_odds"] == -105 and o["total_open"] == 219.5
    assert uta["odds"]["spread_home"] == 8.5 and uta["odds"]["ml_home"] > 0 > uta["odds"]["ml_away"]   # local no favorito


def test_scoreboard_odds_reject_incoherent_spread():
    bad = [{"spread": 4.5, "homeTeamOdds": {"favorite": True}, "awayTeamOdds": {"favorite": False}}]
    assert espn.parse_scoreboard_odds(bad) is None                       # local favorito con spread positivo
    ok = [{"spread": -4.5, "overUnder": 221.0, "homeTeamOdds": {"favorite": True}, "awayTeamOdds": {"favorite": False}}]
    assert espn.parse_scoreboard_odds(ok)["spread_home"] == -4.5
    assert espn.parse_scoreboard_odds(None) is None and espn.parse_scoreboard_odds([]) is None


def test_core_odds_closing_line():
    o = espn.parse_core_odds(load("core_odds_401909950.json"))
    assert o["spread_home"] == 1.5 and o["total"] == 226.5 and o["ml_home"] == 109 and o["ml_away"] == -129
    assert espn.parse_core_odds({"items": []}) is None and espn.parse_core_odds(None) is None


def test_injuries_ids_and_status():
    inj = {i["player"]: i for i in espn.parse_injuries(load("injuries.json"))}
    assert inj["Josh Hart"]["pid"] == 3062679 and inj["Josh Hart"]["team"] == "NYK" and inj["Josh Hart"]["status"] == "questionable"
    assert inj["Tyler Herro"]["team"] == "MIL" and inj["Adem Bona"]["status"] == "out"
    assert all(i["pid"] is not None and i["team"] is not None for i in inj.values())


def test_box_matches_final_score():
    head, rows = espn.parse_box(load("summary_401909952.json"))
    assert head == {"game_id": "401909952", "completed": True, "home": "ATL", "away": "LAL", "home_pts": 114, "away_pts": 124}
    for team, pts in (("ATL", 114), ("LAL", 124)):
        mine = [r for r in rows if r["team"] == team]
        assert sum(r["pts"] for r in mine) == pts
        assert sum(r["minutes"] for r in mine if r["played"]) == pytest.approx(240, abs=3)   # minutos enteros redondeados
        assert sum(r["starter"] for r in mine) == 5
    dnp = [r for r in rows if not r["played"]]
    assert dnp and all(r["minutes"] == 0 and r["pts"] == 0 for r in dnp)
    z = next(r for r in rows if r["name"] == "Ziaire Williams")
    assert (z["minutes"], z["pts"], z["reb"], z["ast"], z["fg3m"]) == (28.0, 12.0, 2.0, 2.0, 2.0)


def test_props_lines_and_sides():
    pr = {(p["pid"], p["market"]): p for p in espn.parse_props(load("props_401909960.json")["items"])}
    hart = pr[(3062679, "pts")]
    assert hart == {"pid": 3062679, "market": "pts", "line": 9.5, "over": -106, "under": -121, "side_ok": True}
    assert pr[(3062679, "reb")]["line"] == 7.5 and pr[(3062679, "fg3m")]["line"] == 1.5
    assert {m for _, m in pr} == {"pts", "reb", "ast", "fg3m", "pra"}                  # hitos y otros mercados no entran
    assert all(p["line"] % 1 == 0.5 for p in pr.values())


def _item(pid, name, price, total=None, target=None):
    x = {"athlete": {"$ref": f"http://x/athletes/{pid}?lang=en"}, "type": {"name": name},
         "odds": {"american": {"value": price}, "total": {"value": total} if total else {}}}
    if target is not None:
        x["current"] = {"target": {"value": target}}
    return x


def test_props_side_check_with_milestones():
    # orden normal: el hito '10+' (-105) se parece al primer precio (over)
    ok = espn.parse_props([_item(1, "Total Points", "-110", "9.5"), _item(1, "Total Points", "-120", "9.5"),
                           _item(1, "Points Milestones", "-105", target=10.0)])
    assert ok[0]["side_ok"] and ok[0]["over"] == -110 and ok[0]["under"] == -120
    # el hito contradice el orden: no se usan los precios para valor esperado
    bad = espn.parse_props([_item(2, "Total Points", "+150", "9.5"), _item(2, "Total Points", "-190", "9.5"),
                            _item(2, "Points Milestones", "-185", target=10.0)])
    assert not bad[0]["side_ok"] and bad[0]["line"] == 9.5
    # mercado con un solo lado o con líneas distintas: se descarta
    assert espn.parse_props([_item(3, "Total Points", "-110", "9.5")]) == []
    assert espn.parse_props([_item(4, "Total Points", "-110", "9.5"), _item(4, "Total Points", "-110", "10.5")]) == []


def test_american_parsing():
    assert espn._american("EVEN") == 100 and espn._american("+670") == 670 and espn._american(-115.0) == -115
    assert espn._american(None) is None and espn._american("abc") is None and espn._american("50") is None
