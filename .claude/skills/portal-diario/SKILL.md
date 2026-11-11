---
name: portal-diario
description: Genera el portal NBA del día y revisa los avisos (ESPN, lesiones, líneas sin verificar). Usar cuando se pida el portal, la jornada de hoy o las predicciones del día.
---

# /portal-diario

1. `uv run python scripts/portal.py --open` (opciones: `--date AAAA-MM-DD`, `--no-fetch`).
2. Lee la salida completa. Resume los **avisos**: partidos sin cuotas, props con `side_ok = False` (no usar esos precios), jugadores sin emparejar, calendario ESPN atrasado.
3. Comprueba que existe `data/predictions/<fecha>.json`. **Nunca borres ni reescribas a mano** nada de `data/predictions/`: es el historial real.
4. Si ESPN falla o cambió el formato: ejecuta `uv run pytest -q tests/test_espn.py` y di qué `parse_*` rompe. No parchees el parser sin actualizar el fixture en `tests/fixtures/`.
5. Resumen final corto: nº de partidos, avisos, y recordatorio de que las discrepancias con el mercado no son recomendaciones (`AGENTS.md`, regla 5).

`viz/portal-nba.html` es generado y no se versiona. Los cambios en `data/live/` y `data/predictions/` sí se commitean (commit de datos aparte, nunca mezclado con código).
