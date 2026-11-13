"""Genera el sitio web del proyecto en webapp/dist (se abre con doble clic en index.html o se sube a un alojamiento estático).

Hace lo mismo que scripts/portal.py (calcula la jornada, puntúa el historial y guarda las predicciones del día) y además
escribe el sitio con sus páginas: partidos por día, ficha de partido, liga, buscador de props, apuestas de jugador y de
equipo, proyecciones, favoritos, historial y metodología.

Uso:
  python webapp/build.py                    # jornada de hoy (fecha de la costa este de EE. UU.)
  python webapp/build.py --open             # abre el sitio en el navegador al terminar
  python webapp/build.py --date 2026-11-10  # otra jornada
  python webapp/build.py --no-fetch         # no actualiza resultados (sí pide jornada, cuotas y lesiones a ESPN)
  python webapp/build.py --bundle viz/sitio-nba.html   # además, una versión de un solo archivo para compartir
  python webapp/build.py --portal           # además, el portal de un solo archivo de siempre (viz/portal-nba.html)
  python webapp/build.py --no-save          # no guarda las predicciones del día (para pruebas)
"""
import argparse
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nba_model import daily, site


def main():
    ap = argparse.ArgumentParser(description="Genera el sitio web del modelo NBA")
    ap.add_argument("--date", default=None, help="AAAA-MM-DD (fecha de la jornada en la costa este)")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--portal", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "webapp/dist"))
    ap.add_argument("--bundle", default=None, help="ruta de la versión de un solo archivo")
    ap.add_argument("--upcoming", type=int, default=6, help="días siguientes de calendario (0 = ninguno)")
    a = ap.parse_args()
    try:
        state = daily.build_state(ROOT, a.date, fetch=not a.no_fetch)
    except RuntimeError as e:                                     # ESPN no responde: sin jornada no hay sitio
        print(f"\nERROR: {e}\nComprueba la conexión a internet y vuelve a intentarlo. El sitio anterior no se ha tocado.")
        sys.exit(1)
    state["track"] = daily.grade_history(ROOT, before=state["date"])
    pred = "(no se guardan: --no-save)" if a.no_save else daily.save_predictions(ROOT, state) if state["games"] else "(sin partidos: no se guarda nada)"
    print("generando el sitio...")
    out = site.build_site(ROOT, state, a.out, upcoming=a.upcoming, bundle=a.bundle)
    print(f"\nSitio listo: {out / 'index.html'}")
    print(f"  {len(state['games'])} partidos, {len(state['players'])} jugadores, {len(state['picks'])} líneas con precio; predicciones: {pred}")
    if a.bundle:
        print(f"  versión de un solo archivo: {a.bundle}  ({Path(a.bundle).stat().st_size // 1024} KB)")
    if a.portal:
        print(f"  portal de un solo archivo: {daily.render(ROOT, state)}")
    for w in state["warnings"]:
        print("  AVISO:", w)
    if a.open:
        webbrowser.open((out / "index.html").resolve().as_uri())


if __name__ == "__main__":
    main()
