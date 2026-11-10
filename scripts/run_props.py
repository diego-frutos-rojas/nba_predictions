"""Ajusta (opcional) y evalúa el modelo de jugadores -> docs/RESULTADOS_PROPS.json y .md

Uso:
  python scripts/run_props.py            # evalúa con models/props_v1.json (congelado)
  python scripts/run_props.py --fit      # reajusta los coeficientes SOLO con DEV (2014-2019) y guarda
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nba_model import live, props, props_eval


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    a = ap.parse_args()
    f, _ = props_eval.build(ROOT)
    path = ROOT / "models/props_v1.json"
    if a.fit:
        dev = props_eval.dev_rows(f)                              # el ajuste NUNCA ve VAL ni TEST
        props.save_model(props.fit(dev), path, {"n_dev": int(len(dev))})
        print(f"coeficientes guardados en {path} (n DEV = {len(dev)})")
    model = props.load_model(path)
    res = {"bloques": props_eval.block_metrics(f, model), "calibracion": props_eval.calibration(f, model),
           "mercado": props_eval.market_test(f, live.read_cache(ROOT / "data/live")["props"], model)}
    json.dump(res, open(ROOT / "docs/RESULTADOS_PROPS.json", "w"), indent=1, default=float)
    md = props_eval.results_markdown(res)
    (ROOT / "docs/RESULTADOS_PROPS.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
