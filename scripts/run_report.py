"""Informe del día con el modelo v2: modelo vs mercado, bajas convertidas en disponibilidad y lectura calibrada.

Uso:  python scripts/run_report.py [--market data/snapshot_2026-11-10/market_2026-11-10.json]
"""
import argparse
import difflib
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nba_model.baselines import SIGMA_MARKET
from nba_model.data import rest_days_before
from nba_model.elo import AVAIL_CLIP, predict_game, run_elo
from nba_model.evaluate import load_params, prepare_dataset
from nba_model.injuries import PLAY_PROB
from nba_model.market import load_market, reference_prob
from nba_model.odds import expected_value, normal_cdf

SD_GAP = 3.3   # desviación típica histórica (TEST 2022-26) de margen_modelo - margen_mercado


def match_pid(name, team, names_by_team):
    pool = names_by_team.get(team, {})
    if name in pool:
        return pool[name]
    close = difflib.get_close_matches(name, list(pool), n=1, cutoff=0.8)
    return pool[close[0]] if close else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default=str(ROOT / "data/snapshot_2026-11-10/market_2026-11-10.json"))
    ap.add_argument("--recent", default=str(ROOT / "data/snapshot_2026-11-10/games.csv"))
    a = ap.parse_args()
    params = load_params(ROOT / "models/params_v2.json")
    rec = pd.read_csv(a.recent, parse_dates=["date_et"]).rename(columns={"date_et": "date"})
    g, tracker, boxes = prepare_dataset(ROOT / "data/raw", return_tracker=True, extra_results=rec[["date", "home", "away", "home_pts", "away_pts"]], with_names=True)
    out = run_elo(g, params)
    st = out["state"]
    last = boxes[boxes.game_id.isin(set(g[g.season == g.season.max()].game_id))]
    names_by_team = {}
    for team, nm, pid in zip(last.team, last.name, last.pid):
        names_by_team.setdefault(team, {})[nm] = int(pid)
    print(f"Ventaja de campo actual (adaptativa): {st.hca:+.2f} pts | sigma del margen estimada: {math.sqrt(st.var):.1f} pts\n")
    print(f"{'Partido':<9}{'Margen':>7}{'P(local)':>9}{'Mercado':>9}{'Tipo':>14}{'Gap pts':>8}{'z':>6}{'Bajas(avail)':>14}  Lectura")
    mk = load_market(a.market)
    for gm in mk["games"]:
        h, aw = gm["home"], gm["away"]
        probs = {}
        for side, team in (("home", h), ("away", aw)):
            for it in gm["injuries"][side]:
                pid = match_pid(it["player"], team, names_by_team)
                if pid is not None:
                    probs[pid] = PLAY_PROB.get(it["status"], 0.5) if it["status"] != "listed" else 0.5
            probs_team = {pid: pr for pid, pr in probs.items()}
            gm.setdefault("_dl", {})[side] = tracker.expected_delta(team, g.season.max(), probs_team)
        dh, da = gm["_dl"]["home"], gm["_dl"]["away"]
        clip = lambda x: max(-AVAIL_CLIP, min(AVAIL_CLIP, x))      # noqa: E731
        adj = params.avail * (clip(dh) - clip(da))
        gdate = (pd.Timestamp(gm["tip_utc"]).tz_localize(None) - pd.Timedelta(hours=5)).normalize()   # fecha en ET
        rh, ra = rest_days_before(g, h, gdate), rest_days_before(g, aw, gdate)                     # 1 = jugó ayer
        pr = predict_game(st, h, aw, rh, ra, params, adj=adj)
        ref = reference_prob(gm, SIGMA_MARKET)
        if gm.get("spread_home_margin") is not None:
            gap = pr["margin"] - gm["spread_home_margin"]      # margen esperado del local: modelo - mercado
        else:
            gap = float("nan")
        z = gap / SD_GAP if gap == gap else float("nan")
        lect = "sin línea: solo referencia del proveedor" if gap != gap else ("alineado" if abs(z) < 1 else ("discrepancia moderada" if abs(z) < 1.5 else "discrepancia grande: mirar bajas/alineación"))
        print(f"{aw+'@'+h:<9}{pr['margin']:>+7.1f}{pr['prob_home']*100:>8.1f}%{ref['p']*100:>8.1f}%{ref['kind'][:13]:>14}{gap:>+8.1f}{z:>+6.1f}{dh-da:>+14.1f}  {lect}")
        o = gm.get("odds") or {}
        for side, prob in (("home", pr["prob_home"]), ("away", 1 - pr["prob_home"])):
            if o.get(side) is not None:
                print(f"{'':<9}  {side:<5} cuota {o[side]:+d}: EV con este modelo {expected_value(prob, o[side]):+.2f} por 1 (el EV del modelo NO es fiable: ver docs/AUDITORIA.md)")


if __name__ == "__main__":
    main()
