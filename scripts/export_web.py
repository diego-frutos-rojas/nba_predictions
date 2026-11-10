"""Genera el analizador web autocontenido con el estado actual del modelo.

Uso:  python scripts/export_web.py [--asof 2026-11-10] [--market ...json] [--recent ...csv] [--out viz/analizador-nba.html]
Antes de usarlo otro día: python scripts/run_pipeline.py --fetch  y actualiza el JSON de mercado/lesiones.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nba_model.webstate import build_web_state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default="2026-11-10")
    ap.add_argument("--market", default=str(ROOT / "data/snapshot_2026-11-10/market_2026-11-10.json"))
    ap.add_argument("--recent", default=str(ROOT / "data/snapshot_2026-11-10/games.csv"))
    ap.add_argument("--template", default=str(ROOT / "web/analizador_template.html"))
    ap.add_argument("--out", default=str(ROOT / "viz/analizador-nba.html"))
    a = ap.parse_args()
    state = build_web_state(ROOT, a.market, a.recent, a.asof)
    parity = state.pop("parity")
    json.dump(parity, open(ROOT / "web/parity.json", "w"), indent=1)
    html = Path(a.template).read_text(encoding="utf-8").replace("/*__STATE__*/null", json.dumps(state, ensure_ascii=False, separators=(",", ":")))
    Path(a.out).write_text(html, encoding="utf-8")
    json.dump(state, open(ROOT / "web/state.json", "w"), ensure_ascii=False, indent=1)
    print(f"escrito {a.out} ({len(html)//1024} KB) con {len(state['teams'])} equipos y {len(state['slate'])} partidos en la jornada")


if __name__ == "__main__":
    main()
