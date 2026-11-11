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
Genera dos páginas autocontenidas y abre la primera:

**`viz/takes-nba.html` (resumen visual).** La jornada en frases claras: «Gana Houston Rockets · 68 %», «Más de 21,5 puntos · 59 %».
Cuatro pestañas (Top del día, Partidos, Jugadores, Combinadas), colores por nivel de probabilidad (fuerte ≥ 65 %, media ≥ 57 %,
ajustada) y, al tocar un take, sus datos: proyección, línea, últimos partidos, modelo frente a casa, bajas. Se pueden montar
combinadas con su probabilidad y su cuota. El porcentaje grande **combina el modelo y la casa** (el modelo a secas es demasiado
confiado); los takes con jugador en duda o con una diferencia sospechosa con la casa quedan marcados y fuera del Top.

**`viz/portal-nba.html` (tablas completas, `--open-portal` para abrirla directamente):**
- **Jornada**: cada partido con la probabilidad del modelo v2, las cuotas de DraftKings (vía ESPN, gratis y sin clave),
  descanso y parte de lesiones.
- **Jugadores**: proyección de puntos, rebotes, asistencias, triples y combinadas (P+R+A, P+R, P+A, R+A) de cada jugador,
  con forma reciente, rival, línea de la casa y probabilidad de superarla. Se puede escribir la línea y las cuotas de otra casa.
- **Picks**: líneas donde el modelo más discrepa de la casa, con el historial medido de ese nivel de discrepancia.
- **Historial**: acierto real de las predicciones guardadas en días anteriores (`data/predictions/`).

Conviene generarlo cerca de la hora de los partidos (lesiones y líneas cambian durante el día). Otras opciones:
`--date AAAA-MM-DD` (otra jornada) y `--no-fetch` (no actualiza resultados). Necesita conexión a `site.api.espn.com`,
`sports.core.api.espn.com` y GitHub.

**Qué esperar del modelo de jugadores** (detalle en `docs/RESULTADOS_PROPS.md` y `docs/AUDITORIA.md`, sección 9): proyecta
mejor que la media de temporada o de los últimos 10 partidos en todos los bloques (RMSE de puntos en TEST 6,01 frente a
6,32), pero las líneas de DraftKings fallan algo menos que él. En 154 partidos de 2026-27, apostar siguiendo al modelo dio
entre −1,5 % y +2,4 % según el filtro, con intervalos que incluyen pérdidas: **no hay ventaja demostrada**.

## Inicio rápido
```
uv sync                                                # crea .venv con Python 3.13 y las versiones exactas de uv.lock (https://docs.astral.sh/uv/)
uv run pre-commit install                              # una vez: lint automático antes de cada commit
uv run pytest -q                                       # 75 tests
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
