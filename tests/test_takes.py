"""Página de takes: resumen claro de la jornada (nba_model/takes.py + web/takes_template.html)."""
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from nba_model import takes
from nba_model.daily import BIG_EDGE, side_eval

ROOT = Path(__file__).resolve().parents[1]
COEF_G = {"a": 0.0, "b_mercado": 0.95, "b_modelo": 0.05}
COEF_P = {"coef_casa": 0.75, "coef_modelo": 0.25}
BAD = {"duda", "revisar", "sin_precio", "empezado", "discrepan"}


def _game(gid, home, away, p_model, p_mkt, state="pre", ml=(1.5, 2.6), spread=-4.5):
    inj = [{"player": "Lesionado Uno", "status": "out", "detail": "Rodilla", "comment": ""},
           {"player": "Sano Dos", "status": "available", "detail": "", "comment": ""}]
    return {"game_id": gid, "home": home, "away": away, "home_name": f"{home} City Homers", "away_name": f"{away} Town Visitors",
            "tip_utc": "2026-11-12T00:00Z", "state": state, "detail": "", "home_pts": 0, "away_pts": 0,
            "model": {"margin": 4.0, "prob_home": p_model, "sigma": 13.7, "rating_home": 2.0, "rating_away": -1.0, "hca": 1.7,
                      "avail_pts": 0.4, "p_cover_home": 0.52},
            "market": {"provider": "DraftKings", "spread_home": spread, "total": 228.5, "ml_home": ml[0], "ml_away": ml[1],
                       "prob_home": p_mkt, "prob_kind": "moneyline sin margen"},
            "gap_pts": -0.5, "rest": {"home": 2, "away": 1}, "injuries": {"home": inj, "away": []}}


def _sv(p_over_at_21):
    """Tabla P(X >= k) sencilla: 1 hasta k = 20 y `p_over_at_21` desde 21 (para una línea de 20,5)."""
    return [1.0] * 21 + [p_over_at_21] * 10 + [0.0]


def _player(pid, gid, team, opp, sv, line, prices=(1.9, 1.9), side_ok=True, status="available", home=True):
    last = [10, 12, 30, 8, 25, 22, 9, 11, 27, 14]
    ev = side_eval(sv, line, prices[0] if side_ok else None, prices[1] if side_ok else None)
    return {"pid": pid, "name": f"Nombre Completo {pid}", "pos": "G", "team": team, "opp": opp, "status": status, "min": 31.0,
            "gp": 10, "min_l10": 30.0, "game_id": gid, "home": home,
            "markets": {"pts": {"mu": 20.0, "sv": sv, "l5": 18.0, "l10": 16.8, "season": 17.0, "last": last, "def": 0.01,
                                "line": {"value": line, "over": prices[0], "under": prices[1], "side_ok": side_ok, "src": "DraftKings"},
                                "eval": ev},
                        "reb": {"mu": 5.0, "sv": [1.0, 0.9], "last": last}}}                       # sin línea: no genera take


def _state():
    games = [_game("g1", "AAA", "BBB", 0.70, 0.66), _game("g2", "CCC", "DDD", 0.30, 0.25, ml=(3.8, 1.28), spread=7.5),
             _game("g3", "EEE", "FFF", 0.55, 0.45, ml=(2.1, 1.75), spread=1.5), _game("g4", "GGG", "HHH", 0.60, 0.62, state="in")]
    players = [_player(1, "g1", "AAA", "BBB", _sv(0.70), 20.5, (1.7, 2.15)),                        # over limpio
               _player(2, "g1", "BBB", "AAA", _sv(0.30), 20.5, (2.1, 1.72), home=False),            # under limpio
               _player(3, "g2", "CCC", "DDD", _sv(0.95), 20.5, (1.95, 1.87)),                       # ventaja enorme -> revisar
               _player(4, "g2", "DDD", "CCC", _sv(0.65), 20.5, status="questionable", home=False),  # duda
               _player(5, "g3", "EEE", "FFF", _sv(0.62), 20.5, side_ok=False),                      # precio no fiable
               _player(6, "g4", "GGG", "HHH", _sv(0.66), 20.5),                                     # partido empezado
               _player(7, "g3", "FFF", "EEE", _sv(0.60), 20.0, (1.9, 1.9), home=False)]             # línea entera
    labels = {"pts": "Puntos", "reb": "Rebotes", "ast": "Asistencias", "fg3m": "Triples", "pra": "Pts+Reb+Ast", "pr": "Pts+Reb",
              "pa": "Pts+Ast", "ra": "Reb+Ast", "min": "Minutos"}
    return {"date": "2026-11-11", "generated_utc": "2026-11-11T20:00:00Z", "warnings": ["aviso de prueba"], "labels": labels,
            "games": games, "players": players,
            "evidence": {"games": {"blend": COEF_G, "accuracy": {"v2_elo": 0.66, "mercado": 0.69}},
                         "props": {"blend": COEF_P, "apuestas": {"0.00": {"n": 1000, "acierto": 0.53, "roi": -0.015}}, "desde": "a", "hasta": "b"}},
            "track": {"days": 0}}


def test_tiers_are_fixed():
    assert (takes.TIER_STRONG, takes.TIER_MEDIUM) == (0.65, 0.57)          # de presentación; no se mueven mirando resultados
    probs = (0.50, 0.5699, 0.57, 0.6499, 0.65, 0.9)
    assert [takes.tier(p) for p in probs] == ["ajustada", "ajustada", "media", "media", "fuerte", "fuerte"]


def test_blends_are_symmetric_and_shrink_the_model():
    p, cal = takes.blend_prop(0.85, 0.50, COEF_P)
    assert cal and 0.5 < p < 0.85 and math.isclose(p, 1 / (1 + math.exp(-0.25 * math.log(0.85 / 0.15))))
    assert math.isclose(p + takes.blend_prop(0.15, 0.50, COEF_P)[0], 1.0)   # over + under = 1
    assert takes.blend_prop(0.85, None, COEF_P)[0] == p                     # sin precio la casa cuenta como 50 %
    assert takes.blend_prop(0.85, 0.5, None) == (0.85, False)               # sin evidencia: modelo a secas, marcado
    assert takes.blend_prop(1.0, 0.5, COEF_P)[0] < 1                        # el recorte evita el infinito
    g, cal = takes.blend_game(0.70, 0.60, COEF_G)
    assert cal and 0.60 < g < 0.70 and abs(g - 0.60) < abs(g - 0.70)        # pesa mucho más el mercado
    assert takes.blend_game(0.70, None, COEF_G) == (0.70, False)


def test_game_takes_pick_the_favourite_with_full_names():
    t = takes.build(_state())
    by = {x["game_id"]: x for x in t["games"]}
    assert by["g1"]["title"] == "Gana AAA City Homers" and by["g1"]["team"] == "AAA" and by["g1"]["price"] == 1.5
    away = by["g2"]                                                          # favorito visitante: todo se da la vuelta
    assert away["title"] == "Gana DDD Town Visitors" and away["subtitle"].startswith("fuera contra") and away["price"] == 1.28
    assert away["p"] > 0.5 and math.isclose(away["detail"]["p_model"], 0.70) and math.isclose(away["detail"]["p_market"], 0.75)
    assert away["detail"]["margin_model"] == -4.0 and away["detail"]["spread_pick"] == -7.5 and away["detail"]["rest_pick"] == 1
    assert "discrepan" in by["g3"]["flags"] and "empezado" in by["g4"]["flags"]
    assert by["g1"]["detail"]["injuries_pick"] == [{"player": "Lesionado Uno", "status": "baja", "detail": "Rodilla"}]
    assert [x["p"] for x in t["games"]] == sorted((x["p"] for x in t["games"]), reverse=True)


def test_player_takes_side_title_and_flags():
    t = takes.build(_state())
    by = {x["pid"]: x for x in t["players"]}
    assert len(t["players"]) == 7                                            # un take por mercado con línea; 'reb' no tiene
    assert by[1]["title"] == "Más de 20,5 puntos" and by[1]["side"] == "over" and by[1]["price"] == 1.7 and by[1]["flags"] == []
    assert by[2]["title"] == "Menos de 20,5 puntos" and by[2]["price"] == 1.72
    assert by[2]["subtitle"] == "BBB Town Visitors · fuera contra AAA City Homers" and by[1]["name"] == "Nombre Completo 1"
    assert 0.5 < by[1]["p"] < by[1]["detail"]["p_model"]                     # la combinada es más prudente que el modelo
    assert by[1]["detail"]["hits"] == [4, 10] and by[2]["detail"]["hits"] == [6, 10]
    assert "revisar" in by[3]["flags"] and by[3]["detail"]["edge"] >= BIG_EDGE
    assert by[4]["flags"] == ["duda"] and by[4]["detail"]["status"] == "duda"
    assert by[5]["flags"] == ["sin_precio"] and by[5]["price"] is None and by[5]["detail"]["p_house"] is None
    assert "empezado" in by[6]["flags"]
    assert by[7]["title"] == "Más de 20 puntos"                              # línea entera sin decimales
    for x in t["players"]:
        assert 0.5 <= x["p"] < 1 and x["tier"] == takes.tier(x["p"]) and x["calibrated"]


def test_top_and_parlays_only_use_clean_takes():
    t = takes.build(_state())
    every = {x["id"]: x for x in t["games"] + t["players"]}
    assert t["top"] and all(not set(every[i]["flags"]) & BAD for i in t["top"])
    assert [every[i]["p"] for i in t["top"]] == sorted((every[i]["p"] for i in t["top"]), reverse=True)
    assert len(t["parlays"]) == 1 and t["parlays"][0]["n"] == 2              # solo hay 2 partidos con takes limpios
    par = t["parlays"][0]
    legs = [every[i] for i in par["legs"]]
    assert len({x["game_id"] for x in legs}) == len(legs)                    # una selección por partido
    assert all(not set(x["flags"]) & BAD for x in legs)
    assert math.isclose(par["p"], math.prod(x["p"] for x in legs), abs_tol=1e-4)
    assert math.isclose(par["price"], math.prod(x["price"] for x in legs), abs_tol=0.01)
    assert math.isclose(par["ev"], par["p"] * math.prod(x["price"] for x in legs) - 1, abs_tol=1e-3)


def test_without_evidence_falls_back_to_model():
    s = _state()
    s["evidence"] = {}
    t = takes.build(s)
    assert not any(x["calibrated"] for x in t["games"] + t["players"])
    assert math.isclose({x["game_id"]: x for x in t["games"]}["g1"]["p"], 0.70)


def test_empty_slate():
    s = _state()
    s["games"], s["players"] = [], []
    t = takes.build(s)
    assert t["games"] == t["players"] == t["top"] == t["parlays"] == []


def test_page_renders_and_works(tmp_path):
    """Monta la página con la plantilla real y la recorre con jsdom: sin errores de JS y con los números de Python."""
    node = shutil.which("node")
    if node is None or not (ROOT / "web/tests/node_modules/jsdom").exists():
        pytest.skip("node o jsdom no están instalados (npm ci en web/tests)")
    state = _state()
    out = takes.render(ROOT, state, tmp_path / "takes.html")
    html = out.read_text(encoding="utf-8")
    assert "/*__TAKES__*/null" not in html and "Nombre Completo 1" in html
    r = subprocess.run([node, str(ROOT / "web/tests/takes_smoke.js"), str(out)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    js = json.loads(r.stdout)
    t = takes.build(state)
    assert js["errors"] == [] and js["tabs"][:4] == ["Top del día", "Partidos", "Jugadores", "Combinadas"]
    assert js["games"] == 4 and js["top"] == len(t["top"])
    assert js["first_game"]["call"] == t["games"][0]["title"] and js["first_game"]["pct"] == f"{round(t['games'][0]['p'] * 100)}%"
    assert js["first_game"]["expanded"] == "true" and js["first_game"]["detail_tiles"] == 6
    assert js["players_best"] == 2 and js["first_player"]["bars"] == 10      # por defecto: solo limpios, el mejor de cada jugador
    assert js["players_all_count"] == "7 takes"
    assert js["slip"]["legs"] == 2 and js["badge"] == "2" and js["auto_parlays"] == 1
    addable = [x for x in t["games"] if x["price"] is not None and "empezado" not in x["flags"]][:2]
    assert js["slip"]["tiles"][0] == f"{round(math.prod(x['p'] for x in addable) * 100)} %"
