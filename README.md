# Modelo NBA: probabilidades, cuotas y auditoría (v2)

Proyecto para estimar probabilidades de partidos de la NBA, compararlas con el mercado y entender de dónde
vienen las discrepancias. Incluye datos históricos reales (2011-12 a 2026-27), el modelo, una evaluación
sin fuga de información y la auditoría del modelo anterior.

## Resultado en una línea
v2 mejora al modelo anterior en **−0,0211 de log loss** (IC95 % [−0,0266; −0,0154]) en 6.153 partidos de
prueba que no se usaron para ajustar nada, y cierra el 52 % de la distancia con el mercado. **No bate al
mercado**, y las discrepancias entre ambos no contienen información real. Detalle en `docs/AUDITORIA.md`.

| TEST 2022-26 | Log loss | Acierto | ECE |
|---|---|---|---|
| v0 (anterior) | 0,6329 | 65,0 % | 0,037 |
| **v2** | **0,6117** | **66,3 %** | **0,021** |
| Mercado (spread de cierre) | 0,5922 | 68,6 % | 0,023 |

## Inicio rápido
```
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                                              # 13 tests
python scripts/run_pipeline.py                         # evaluación completa -> docs/RESULTADOS.json y .md
python scripts/run_report.py                           # informe de los partidos del snapshot (10-nov-2026)
```
Los datos crudos ya vienen en `data/raw/` (19 MB). Para refrescarlos: `python scripts/run_pipeline.py --fetch`.
Para reafinar parámetros (solo con DEV 2014-2019): `python scripts/run_pipeline.py --tune`.

## Estructura
- `nba_model/data.py`: descarga, limpieza y unión de fuentes (ESPN, SBR, hoopR). Incluye la reparación de spreads intercambiados.
- `nba_model/elo.py`: **el modelo v2** (ratings secuenciales, ventaja de campo adaptativa, descanso, disponibilidad, sigma online).
- `nba_model/availability.py`: talento disponible hoy frente al habitual (bajas y regresos) y su versión con probabilidades de jugar.
- `nba_model/baselines.py`: mercado, v0 en walk-forward, siempre-local. `nba_model/ratings.py` es el v0 original.
- `nba_model/tune.py`: búsqueda acotada con promediado del 5 % mejor. `nba_model/evaluate.py`: evaluación y pruebas contra el mercado.
- `nba_model/market.py`, `odds.py`, `metrics.py`, `injuries.py`: utilidades. `player_model.py`: experimento descartado (ver auditoría).
- `models/params_v2.json`: parámetros congelados (afinados solo con DEV).
- `docs/`: `AUDITORIA.md` (hallazgos y decisiones), `RESULTADOS.md/.json` (generados), `INFORME_2026-11-10.txt`.
- `data/snapshot_2026-11-10/`: mercado, lesiones y descanso de los 6 partidos analizados, y resultados del 7 al 9 de noviembre.
- `viz/mesa-cuotas-nba.html`: visualización interactiva **basada en el modelo v0** (no se ha actualizado a v2).

## Usar el modelo con otro día
1. `python scripts/run_pipeline.py --fetch` para traer los últimos resultados.
2. Crear un JSON como `data/snapshot_2026-11-10/market_2026-11-10.json` (equipos, spread, cuotas, lesiones con estado, descanso).
3. `python scripts/run_report.py --market tu_archivo.json --recent resultados_recientes.csv`.

## Analizador web (partidos de hoy)
`viz/analizador-nba.html` es una página autocontenida (sin servidor) con el modelo v2 dentro:
1. Busca el partido (`MIA @ UTA`, `Heat en Jazz`, `Lakers vs Suns`) o pulsa uno de la jornada.
2. Ajusta lesiones por jugador o pega el parte de lesiones; el descanso se calcula de las fechas.
3. Mete el spread y las cuotas de hasta 3 casas.
4. Devuelve margen, probabilidad, de dónde sale cada punto, y una lista de takes ordenados por robustez
   (precio frente al consenso, alertas de bajas, probabilidad, discrepancia con el mercado y su evidencia histórica).

La página **no consulta datos en vivo** (cuotas y lesiones se introducen o se pegan). Para regenerarla con datos nuevos:
```
python scripts/run_pipeline.py --fetch            # resultados recientes
python scripts/export_web.py --asof AAAA-MM-DD --market tu_mercado.json --recent resultados_recientes.csv
NODE_PATH=... node web/tests/web_parity.js        # (opcional) comprueba que la página y Python dan lo mismo
```
La plantilla está en `web/analizador_template.html` y el estado exportado en `web/state.json`.

## Límites
Ver `docs/AUDITORIA.md`, sección 8. Herramienta de análisis, no asesoramiento financiero ni recomendación de
apuesta. Solo mayores de 18 años.
