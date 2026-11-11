"""Exporta el estado del modelo v2 a JSON para el analizador web (viz/analizador-nba.html)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from .baselines import SIGMA_MARKET
from .data import rest_days_before
from .elo import AVAIL_CLIP, predict_game, run_elo
from .evaluate import load_params, prepare_dataset
from .injuries import PLAY_PROB
from .market import load_market

TEAM_NAMES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets", "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers", "LAC": "LA Clippers", "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies", "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves", "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs", "TOR": "Toronto Raptors", "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}


def build_web_state(root: str | Path, market_path: str | Path, recent_csv: str | Path, asof: str) -> dict:
    root = Path(root)
    params = load_params(root / "models/params_v2.json")
    rec = pd.read_csv(recent_csv, parse_dates=["date_et"]).rename(columns={"date_et": "date"})
    g, tr, boxes = prepare_dataset(root / "data/raw", return_tracker=True, with_names=True,
                                   extra_results=rec[["date", "home", "away", "home_pts", "away_pts"]])
    st = run_elo(g, params)["state"]
    season = int(g.season.max())
    names = dict(zip(boxes.pid.astype(int), boxes.name))
    cur = g[g.season == season]
    teams = {}
    for t, nm in TEAM_NAMES.items():
        games = g[(g.home == t) | (g.away == t)]
        mine = cur[(cur.home == t) | (cur.away == t)]
        w = int(((mine.home == t) & (mine.home_margin > 0)).sum() + ((mine.away == t) & (mine.home_margin < 0)).sum())
        det = tr.roster_detail(t)
        teams[t] = {
            "name": nm, "rating": round(float(st.ratings.get(t, 0.0)), 4), "last_game": str(games.date.max().date()),
            "record": [w, int(len(mine) - w)], "n_hist": det["n_hist"],
            "roster": sorted([{"name": names.get(p["pid"], str(p["pid"])), "value": round(p["value"], 2), "frac": round(p["frac"], 3)}
                              for p in det["players"]], key=lambda x: -x["value"]),
        }
    mk = load_market(market_path)
    slate = [{"home": x["home"], "away": x["away"], "tip_utc": x["tip_utc"], "provider_home_prob": x["provider_home_prob"],
              "spread_home_margin": x.get("spread_home_margin"), "odds": x.get("odds") or {},
              "injuries": x["injuries"]} for x in mk["games"]]
    # referencia calculada por la ruta Python (la usa web/tests/web_parity.js para verificar la página)
    parity = []
    clip = lambda x: max(-AVAIL_CLIP, min(AVAIL_CLIP, x))                 # noqa: E731
    for x in mk["games"]:
        deltas = {}
        for side, team in (("home", x["home"]), ("away", x["away"])):
            by_name = {names.get(int(p), ""): int(p) for p in tr.roster(team)}
            pr = {by_name[i["player"]]: (0.5 if i["status"] == "listed" else PLAY_PROB.get(i["status"], 0.5))
                  for i in x["injuries"][side] if i["player"] in by_name and i["status"] != "available"}
            deltas[side] = tr.expected_delta(team, season, pr)
        gd = (pd.Timestamp(x["tip_utc"]).tz_localize(None) - pd.Timedelta(hours=5)).normalize()
        out = predict_game(st, x["home"], x["away"], rest_days_before(g, x["home"], gd), rest_days_before(g, x["away"], gd), params,
                           adj=params.avail * (clip(deltas["home"]) - clip(deltas["away"])))
        parity.append({"home": x["home"], "away": x["away"], "margin": round(out["margin"], 4), "prob_home": round(out["prob_home"], 4)})
    res = json.load(open(root / "docs/RESULTADOS.json"))
    t = res["blocks"]["TEST"]
    evidence = {
        "blend": res["blend"]["coef_dev"], "sigma_market": SIGMA_MARKET, "gap_sd": res["gap_info"]["TEST"]["sd_gap_pts"],
        "gap_c2": res["gap_info"]["TEST"]["c2_gap"], "gap_c2_ci": res["gap_info"]["TEST"]["c2_ci95"],
        "roi_test": {k: {"roi": v["TEST"]["roi"], "n": v["TEST"]["n"], "lo": v["TEST"]["lo"], "hi": v["TEST"]["hi"]} for k, v in res["roi_spread_-110"].items()},
        "test_ll": {k: t[k]["log_loss"] for k in ("v0_ridge", "v2_elo", "mercado")},
        "test_acc": {k: t[k]["accuracy"] for k in ("v0_ridge", "v2_elo", "mercado")},
    }
    return {
        "asof": asof, "season": season,
        "model": {"hca": round(float(st.hca), 4), "sigma": round(math.sqrt(st.var) * params.sig_scale, 4), "rest_b2b": params.rest_b2b,
                  "rest_long": params.rest_long, "avail": params.avail, "avail_clip": 60.0, "warmup": 5},
        "teams": teams, "slate": slate, "evidence": evidence, "parity": parity,
    }
