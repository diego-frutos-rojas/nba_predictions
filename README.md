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

## Portal diario (lo que se abre cada día)
```
python scripts/portal.py --open        # o doble clic en portal.bat (Windows) / ./portal.sh (Mac, Linux)
```
Genera `viz/portal-nba.html`, una página autocontenida con la jornada de hoy:
- **Partidos**: la jornada con la probabilidad del modelo v2 y la lectura frente al mercado (DraftKings, vía ESPN, gratis y
  sin clave). Cada partido tiene su ficha: apuestas de jugador y de equipo, proyecciones, desglose del modelo y bajas.
- **Buscador de props**: jugadores que han llegado a una cifra en sus últimos 5 o 10 partidos, con la probabilidad del modelo.
- **Apuestas de jugador**: líneas con precio (tarjetas o vista compacta) con cuota, probabilidad del modelo frente a la casa,
  acierto reciente y el historial medido de ese nivel de discrepancia. Filtros por mercado, lado, ventaja, cuota y partido.
- **Apuestas de equipo**: ganador, hándicap y total de cada partido frente al modelo (no son recomendaciones).
- **Proyecciones**: puntos, rebotes, asistencias, triples y combinadas (P+R+A, P+R, P+A, R+A) de cada jugador, con forma
  reciente, rival y línea de la casa. Se puede escribir la línea y las cuotas de otra casa.
- **Favoritos** (estrella, se guarda en el navegador) e **Historial**: acierto real de las predicciones guardadas en días
  anteriores (`data/predictions/`).

Conviene generarlo cerca de la hora de los partidos (lesiones y líneas cambian durante el día). Otras opciones:
`--date AAAA-MM-DD` (otra jornada) y `--no-fetch` (no actualiza resultados). Necesita conexión a `site.api.espn.com`,
`sports.core.api.espn.com` y GitHub.

## Sitio web (`webapp/`)
```
python webapp/build.py --open          # o doble clic en sitio.bat (Windows) / ./sitio.sh (Mac, Linux)
```
El mismo contenido que el portal, como sitio de varias páginas y con lo que no cabe en un solo archivo: navegación por
días (anteriores con su resultado, siguientes con el calendario), ficha de cada partido con cara a cara y quintetos
probables, y la página de liga (clasificación, líderes y tablas). Hace también el trabajo de `scripts/portal.py`
(guarda las predicciones del día), así que basta con ejecutar uno de los dos. Detalle en `webapp/README.md`.

**Qué esperar del modelo de jugadores** (detalle en `docs/RESULTADOS_PROPS.md` y `docs/AUDITORIA.md`, sección 9): proyecta
mejor que la media de temporada o de los últimos 10 partidos en todos los bloques (RMSE de puntos en TEST 6,01 frente a
6,32), pero las líneas de DraftKings fallan algo menos que él. En 154 partidos de 2026-27, apostar siguiendo al modelo dio
entre −1,5 % y +2,4 % según el filtro, con intervalos que incluyen pérdidas: **no hay ventaja demostrada**.

## Inicio rápido
```
uv sync                                                # crea .venv con Python 3.13 y las versiones exactas de uv.lock (https://docs.astral.sh/uv/)
uv run pre-commit install                              # una vez: lint automático antes de cada commit
uv run pytest -q                                       # 76 tests
uv run python scripts/run_pipeline.py                  # evaluación completa -> docs/RESULTADOS.json y .md
uv run python scripts/run_report.py                    # informe de los partidos del snapshot (10-nov-2026)
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
- `nba_model/props.py`: **modelo de jugadores** (minutos, ritmo por minuto, rival, bajas, distribución). `props_eval.py`: su evaluación.
- `nba_model/espn.py`: lectores de la API pública de ESPN (jornada, cuotas, lesiones, cajas, props). `live.py`: caché en `data/live/`.
- `nba_model/daily.py` + `web/portal_template.html` + `scripts/portal.py`: el portal diario.
- `nba_model/site.py` + `webapp/`: el sitio web de varias páginas (`webapp/build.py` lo genera en `webapp/dist`).
- `scripts/run_props.py`: evalúa (o reajusta con `--fit`, solo DEV) el modelo de jugadores. `scripts/fetch_market_history.py`:
  baja las líneas de cierre de props de la temporada en curso para medirlo contra la casa.
- `models/params_v2.json`, `models/props_v1.json`: parámetros congelados (afinados solo con DEV).
- `docs/`: `AUDITORIA.md` (hallazgos y decisiones), `RESULTADOS.md/.json` (generados), `INFORME_2026-11-10.txt`.
- `data/snapshot_2026-11-10/`: mercado, lesiones y descanso de los 6 partidos analizados, y resultados del 7 al 9 de noviembre.
- `archive/mesa-cuotas-nba.html`: visualización antigua **basada en el modelo v0** (archivada, no se mantiene).

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
