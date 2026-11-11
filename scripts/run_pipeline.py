"""Reproduce toda la evaluación: descarga (opcional) -> dataset -> (afinado opcional) -> evaluación -> docs/RESULTADOS.json.

Uso:
  python scripts/run_pipeline.py                 # usa models/params_v2.json (congelado)
  python scripts/run_pipeline.py --fetch         # descarga antes los datos crudos
  python scripts/run_pipeline.py --tune          # reafina SOLO con DEV (2014-2019) y guarda params
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nba_model.data import fetch_history
from nba_model.evaluate import load_params, prepare_dataset, results_markdown, run_full_evaluation
from nba_model.tune import average_top, random_search


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--n", type=int, default=700, help="muestras de la búsqueda")
    a = ap.parse_args()
    raw = ROOT / "data/raw"
    if a.fetch:
        fetch_history(raw)
    g = prepare_dataset(raw)
    params_path = ROOT / "models/params_v2.json"
    if a.tune:
        dev = g[g.season <= 2019].reset_index(drop=True)          # el afinado NUNCA ve VAL ni TEST
        S = dev.season.values
        res = random_search(dev, (S >= 2014) & (S <= 2019), n=a.n, seed=13)
        p = average_top(res)
        json.dump({"model": "elo_mov_v2", "tuned_on": "DEV 2014-2019", "params": p.as_dict()}, open(params_path, "w"), indent=2)
        print("parámetros guardados:", p)
    out = run_full_evaluation(g, load_params(params_path))
    (ROOT / "docs").mkdir(exist_ok=True)
    json.dump(out, open(ROOT / "docs/RESULTADOS.json", "w"), indent=2, default=float)
    (ROOT / "docs/RESULTADOS.md").write_text(results_markdown(out), encoding="utf-8")
    t = out["blocks"]["TEST"]
    print("TEST 2022-2026 log loss -> v0: %.4f | v2: %.4f | mercado: %.4f" % (t["v0_ridge"]["log_loss"], t["v2_elo"]["log_loss"], t["mercado"]["log_loss"]))
    print("Detalle completo en docs/RESULTADOS.json")


if __name__ == "__main__":
    main()
