"""Tests del portal diario: matemática de las apuestas, paridad con la página, flujo completo sin red e historial."""
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from nba_model import daily, espn, props, props_eval

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures"
load = lambda name: json.load(open(FIX / name, encoding="utf-8"))      # noqa: E731


def test_side_eval_basics():
    sv = [1.0, 0.9, 0.7, 0.4, 0.2, 0.05]                                 # P(X >= k)
    e = daily.side_eval(sv, 2.5, 1.9, 1.9)
    assert e["p_over"] == 0.4 and e["p_push"] == 0.0 and math.isclose(e["p_under"], 0.6)
    assert e["side"] == "under" and math.isclose(e["fair_over"], 0.5) and math.isclose(e["edge"], 0.1)
    assert math.isclose(e["ev"], 0.6 * 0.9 - 0.4)
    p = daily.side_eval(sv, 3.0, 2.0, 1.8)                               # línea entera: P(X = 3) es empate
    assert math.isclose(p["p_push"], 0.2) and math.isclose(p["p_over"], 0.2) and math.isclose(p["p_under"], 0.6)
    assert math.isclose(p["p_over"] + p["p_under"] + p["p_push"], 1.0)
    assert daily.side_eval(sv, 20.5, None, None) == {"p_over": 0.0, "p_under": 1.0, "p_push": 0.0}    # fuera de la tabla
    assert "edge" not in daily.side_eval(sv, 2.5, 1.9, None)             # sin las dos cuotas no hay ventaja
    assert daily.fair_over(-110, -110) == pytest.approx(0.5) and daily.fair_over(None, -110) is None


def test_edge_bucket_uses_prespecified_thresholds():
    assert [daily.edge_bucket(x) for x in (0.0, 0.029, 0.03, 0.07, 0.5)] == ["0.00", "0.00", "0.03", "0.06", "0.10"]
    assert props_eval.EDGE_THRESHOLDS == (0.0, 0.03, 0.06, 0.10)


def test_page_math_matches_python(tmp_path):
    """La página (JS) y Python deben dar lo mismo para cualquier línea y cuota."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node no está instalado")
    model = props.load_model(ROOT / "models/props_v1.json")
    rng = np.random.default_rng(7)
    cases = []
    for _ in range(300):
        market = str(rng.choice(props.ALL_MARKETS))
        mu = float(rng.uniform(0.3, 45))
        sv = daily._survival(model, market, mu)
        line = float(rng.integers(0, int(mu * 2) + 3)) + float(rng.choice([0.0, 0.5]))
        over, under = (round(float(rng.uniform(1.3, 3.2)), 3), round(float(rng.uniform(1.3, 3.2)), 3)) if rng.random() > 0.2 else (None, None)
        cases.append({"sv": sv, "line": line, "over": over, "under": under})
    thr = [f"{t:.2f}" for t in props_eval.EDGE_THRESHOLDS]
    f = tmp_path / "cases.json"
    f.write_text(json.dumps({"cases": cases, "thresholds": thr}))
    out = json.loads(subprocess.run([node, str(ROOT / "web/tests/portal_parity.js"), str(f)], capture_output=True, text=True, check=True).stdout)
    assert len(out) == len(cases)
    for c, js in zip(cases, out):
        py = daily.side_eval(c["sv"], c["line"], c["over"], c["under"])
        assert set(py) == set(js) - {"bucket"}
        for k, v in py.items():
            assert (js[k] == v) if isinstance(v, str) else math.isclose(js[k], v, abs_tol=1e-12), (k, c["line"])
        if "edge" in py:
            assert js["bucket"] == daily.edge_bucket(py["edge"])


@pytest.fixture(scope="module")
def offline_root(tmp_path_factory):
    """Copia ligera del proyecto (enlaces a datos, modelos y plantilla) con data/live y data/predictions vacíos."""
    root = tmp_path_factory.mktemp("portal")
    (root / "data").mkdir()
    for rel in ("data/raw", "models", "docs", "web"):
        (root / rel).symlink_to(ROOT / rel, target_is_directory=True)
    return root


@pytest.fixture(scope="module")
def state(offline_root):
    mp = pytest.MonkeyPatch()
    mp.setattr(espn, "fetch_scoreboard", lambda date: espn.parse_scoreboard(load("scoreboard_2026-11-10.json")))
    mp.setattr(espn, "fetch_injuries", lambda: espn.parse_injuries(load("injuries.json")))
    mp.setattr(espn, "fetch_props", lambda gid: espn.parse_props(load("props_401909960.json")["items"]) if gid == "401909960" else [])
    try:
        return daily.build_state(offline_root, "2026-11-10", fetch=False, log=lambda *a: None)
    finally:
        mp.undo()


def test_build_state_offline(state, offline_root):
    assert state["date"] == "2026-11-10" and len(state["games"]) == 6 and state["season"] == 2027
    nyk = state["games"][0]
    assert (nyk["away"], nyk["home"]) == ("MIL", "NYK") and 0.7 < nyk["model"]["prob_home"] < 0.95
    assert nyk["market"]["spread_home"] == -15.5 and nyk["market"]["ml_away"] == 7.7 and 0.8 < nyk["market"]["prob_home"] < 0.95
    assert math.isclose(nyk["gap_pts"], nyk["model"]["margin"] - 15.5, abs_tol=0.011)
    assert [i["player"] for i in nyk["injuries"]["home"]] == ["Josh Hart"]
    teams = {p["team"] for p in state["players"]}
    assert teams == {"MIL", "NYK", "BOS", "PHI", "LAC", "PHX", "MIA", "UTA", "ORL", "SAC", "OKC", "POR"}
    names = {p["name"]: p for p in state["players"]}
    assert "Adem Bona" not in names                                       # baja confirmada: no se proyecta
    hart = names["Josh Hart"]
    assert hart["status"] == "questionable" and hart["markets"]["pts"]["line"]["value"] == 9.5
    for p in state["players"]:
        assert 1 <= p["min"] <= 44 and set(p["markets"]) == set(props.ALL_MARKETS)
        mk = p["markets"]
        assert math.isclose(mk["pra"]["mu"], mk["pts"]["mu"] + mk["reb"]["mu"] + mk["ast"]["mu"], abs_tol=0.02)
        for m in mk.values():
            assert m["sv"][0] == 1.0 and all(a >= b for a, b in zip(m["sv"], m["sv"][1:])) and len(m["last"]) <= props.RECENT_N
            if "eval" in m:
                k = int(math.floor(m["line"]["value"])) + 1
                assert math.isclose(m["eval"]["p_over"], m["sv"][k] if k < len(m["sv"]) else 0.0, abs_tol=1e-4)
    assert 200 < sum(p["min"] for p in state["players"] if p["team"] == "NYK") < 300
    picks = state["picks"]
    assert picks and all(a["edge"] >= b["edge"] for a, b in zip(picks, picks[1:]))
    assert all(x["game_id"] == "401909960" and x["price"] > 1 and 0 < x["p"] < 1 for x in picks)
    assert any("duda" in x["flags"] for x in picks if x["name"] == "Josh Hart")
    assert (offline_root / "data/live/props.csv").exists()               # las líneas previas al partido se archivan
    json.dumps(state)                                                     # todo serializable


def test_render_and_save(state, offline_root):
    st = dict(state, track={"days": 0})
    out = daily.render(offline_root, st, offline_root / "viz/portal.html")
    html = out.read_text(encoding="utf-8")
    assert "/*__STATE__*/null" not in html and '"date":"2026-11-10"' in html and "Josh Hart" in html
    path = daily.save_predictions(offline_root, st)
    saved = json.load(open(path, encoding="utf-8"))
    assert len(saved["games"]) == 6 and len(saved["players"]) == len(state["players"])
    assert "sv" not in saved["players"][0]["markets"]["pts"]
    # segunda ejecución con un partido ya empezado: se conserva lo predicho antes del salto
    later = json.loads(json.dumps(st))
    later["games"][0]["state"] = "in"
    later["games"][0]["model"]["prob_home"] = 0.01
    again = json.load(open(daily.save_predictions(offline_root, later), encoding="utf-8"))
    g0 = next(x for x in again["games"] if x["game_id"] == later["games"][0]["game_id"])
    assert g0["model"]["prob_home"] == state["games"][0]["model"]["prob_home"] and len(again["games"]) == 6


def test_grade_history_against_real_box(offline_root):
    """PHI 127 - CHI 121 (8-nov-2026, partido 401909945): LeBron James hizo 22 puntos y 5 rebotes."""
    d = offline_root / "data/predictions"
    d.mkdir(parents=True, exist_ok=True)
    mk = lambda line, side, edge: {"mu": 20.0, "line": {"value": line, "over": 1.9, "under": 1.9},     # noqa: E731
                                   "eval": {"p_over": 0.6, "fair_over": 0.5, "side": side, "edge": edge}}
    pred = {"date": "2026-11-08", "games": [{"game_id": "401909945", "home": "CHI", "away": "PHI",
                                             "model": {"prob_home": 0.3}, "market": {"prob_home": 0.6}}],
            "players": [{"game_id": "401909945", "pid": 1966, "markets": {"pts": mk(17.5, "over", 0.08), "reb": mk(6.5, "over", 0.04)}},
                        {"game_id": "401909945", "pid": 999999999, "markets": {"pts": mk(10.5, "over", 0.2)}}]}
    json.dump(pred, open(d / "2026-11-08.json", "w"))
    t = daily.grade_history(offline_root, before="2026-11-10")
    assert t["days"] == 1 and t["n_lines"] == 2                           # el jugador que no jugó no cuenta
    assert t["picks"]["0.00"]["n"] == 2 and math.isclose(t["picks"]["0.00"]["roi"], (0.9 - 1.0) / 2)
    assert t["picks"]["0.06"] == {"n": 1, "acierto": 1.0, "roi": pytest.approx(0.9), "unidades": pytest.approx(0.9)}
    assert t["picks"]["0.10"]["n"] == 0
    assert t["error"]["pts"]["mae_modelo"] == 2.0 and t["error"]["pts"]["mae_linea"] == 4.5
    assert t["games"]["acierto_modelo"] == 1.0 and t["games"]["acierto_mercado"] == 0.0     # ganó el visitante
    assert daily.grade_history(offline_root, before="2026-11-08") == {"days": 0}
