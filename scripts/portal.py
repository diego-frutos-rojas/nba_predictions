"""Genera el portal del día: viz/portal-nba.html (página autocontenida, se abre con doble clic).

Uso:
  python scripts/portal.py                 # jornada de hoy (fecha de la costa este de EE. UU.)
  python scripts/portal.py --date 2026-11-10
  python scripts/portal.py --no-fetch      # no actualiza resultados (sí pide jornada, cuotas y lesiones a ESPN)
  python scripts/portal.py --open          # abre la página en el navegador al terminar
"""
import argparse
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nba_model import daily


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="AAAA-MM-DD (fecha de la jornada en la costa este)")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "viz/portal-nba.html"))
    a = ap.parse_args()
    try:
        state = daily.build_state(ROOT, a.date, fetch=not a.no_fetch)
    except RuntimeError as e:                                     # ESPN no responde: sin jornada no hay portal
        print(f"\nERROR: {e}\nComprueba la conexión a internet y vuelve a intentarlo. El portal anterior no se ha tocado.")
        sys.exit(1)
    state["track"] = daily.grade_history(ROOT, before=state["date"])
    pred = daily.save_predictions(ROOT, state) if state["games"] else "(sin partidos: no se guarda nada)"
    out = daily.render(ROOT, state, a.out)
    print(f"\nPortal listo: {out}  ({out.stat().st_size // 1024} KB)")
    print(f"  {len(state['games'])} partidos, {len(state['players'])} jugadores, {len(state['picks'])} líneas con precio; predicciones guardadas en {pred}")
    for w in state["warnings"]:
        print("  AVISO:", w)
    if a.open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
