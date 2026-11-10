"""Descarga de ESPN las cuotas de cierre y las props de DraftKings de los partidos YA JUGADOS de la temporada en
curso (ESPN solo las conserva para la temporada actual) y las guarda en data/live/. Sirve para evaluar el modelo
de jugadores contra líneas reales (scripts/run_props.py).

Uso:  python scripts/fetch_market_history.py [--force]
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nba_model import espn, live
from nba_model.data import build_games


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="vuelve a pedir también los partidos que ya están en la caché")
    a = ap.parse_args()
    raw, lv = ROOT / "data/raw", ROOT / "data/live"
    g = build_games(raw)
    cache = live.read_cache(lv)
    ids = sorted(set(g[g.season == g.season.max()].game_id) | set(cache["results"].game_id))
    if not a.force:
        ids = [i for i in ids if i not in set(cache["props"].game_id)]
    print(f"{len(ids)} partidos por pedir")

    def one(gid):
        return gid, espn.fetch_game_odds(gid), espn.fetch_props(gid)

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, ids))
    n_props = 0
    for gid, odds, pr in res:
        live.save_market(lv, gid, odds, pr)
        n_props += len(pr)
    print(f"guardadas {n_props} líneas de props de {sum(bool(r[2]) for r in res)} partidos y cuotas de {sum(bool(r[1]) for r in res)}")


if __name__ == "__main__":
    main()
