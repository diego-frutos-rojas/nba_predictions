# AGENTS.md: modelo de análisis NBA (probabilidad y mercado)

## Objetivo
Obtener **probabilidades calibradas** de partidos NBA y medir si alguna vez difieren del mercado por información
real. Después se ampliará a fútbol (Poisson / Dixon-Coles). El objetivo NO es listar apuestas: la auditoría
(`docs/AUDITORIA.md`) demuestra que las discrepancias del modelo con el mercado hoy son ruido.

## Comandos
```
pip install -r requirements.txt
pytest -q                                   # deben pasar siempre (13 tests, incluye detección de fuga temporal)
python scripts/run_pipeline.py              # evaluación completa con parámetros congelados
python scripts/run_pipeline.py --tune       # reafinado SOLO con DEV (2014-2019)
python scripts/run_report.py                # informe del snapshot del 10-nov-2026
```

## Reglas innegociables (anti-sobreajuste)
1. **Bloques**: DEV = 2014-2019 (único que se usa para afinar), VAL = 2020-2021, TEST = 2022-2026. Prohibido
   elegir parámetros, variables o umbrales mirando VAL o TEST. Una variable nueva se valida primero con
   validación cruzada temporal dentro de DEV (afinar en 2014-16 y evaluar en 2017-19, y al revés) y solo
   después se mira TEST **una vez**.
2. **Cero fuga de información**: cada predicción usa solo partidos anteriores. `tests/test_core.py` lo comprueba
   (cambiar un resultado futuro no puede alterar predicciones pasadas). Todo feature nuevo necesita ese test.
3. **Promediar, no elegir**: los hiperparámetros salen del promedio del 5 % mejor de una búsqueda acotada.
4. Reportar los negativos (qué se probó y no funcionó) en `docs/AUDITORIA.md`, sección 5.
5. No presentar un valor esperado positivo del modelo como recomendación: casi siempre es un error del modelo.
   Comparar siempre con el mercado (log loss y contraste de la parte real de la discrepancia).

## Estructura (ver README)
`data.py` (datos) → `availability.py` (disponibilidad) → `elo.py` (modelo) → `evaluate.py` (pruebas) y
`scripts/run_report.py` (uso diario). Parámetros en `models/params_v2.json`.

## Analizador web
`web/analizador_template.html` + `nba_model/webstate.py` + `scripts/export_web.py` generan `viz/analizador-nba.html`.
La matemática del modelo está duplicada en JS (bloque `MODEL-START/END` de la plantilla). **Cualquier cambio en `elo.py`
o `availability.py` debe replicarse allí** y comprobarse con `web/tests/web_parity.js` (usa `web/parity.json`, que sale de la
ruta Python). Los takes no se ordenan por rentabilidad sino por robustez: el único valor que no depende del modelo es el precio
entre casas; las discrepancias modelo-mercado se muestran con su evidencia histórica (ROI simulado negativo).

## Problemas conocidos
0. La web no tiene datos en vivo: cuotas y lesiones se escriben o se pegan. Pendiente: leer cuotas/lesiones de una API
   (ESPN scoreboard/injuries o The Odds API) en un script local y volcarlas al JSON del partido.
1. v2 no bate al mercado (log loss +0,019 en TEST). Falta información que el mercado sí tiene.
2. La disponibilidad histórica usa quién jugó; en producción es el parte de lesiones (más incierto). Hay que medir
   cuánto empeora (guardar partes de lesiones con marca de tiempo).
3. Sin cuotas de moneyline posteriores a 2019 ni cuotas de apertura/cierre con marca de tiempo.
4. El calendario ESPN puede ir 1-2 días por detrás; se completa con `data/snapshot_*/games.csv`.
5. La calibración tiene pendiente 1,05-1,08 en TEST (algo poco confiado); no se recalibró para no sobreajustar.

## Hoja de ruta (por prioridad)
1. Cuotas de **apertura y cierre con marca de tiempo** (ESPN core API da DraftKings open/close desde 2025-26) para medir
   el valor frente al cierre (CLV) y cuándo se mueven las líneas respecto a las noticias de lesión.
2. Datos de **quintetos / jugada a jugada** (hoopR pbp) para un impacto de jugador estable (el intento con solo
   marcadores sobreajustó; ver `player_model.py`).
3. **Prior de inicio de temporada** con proyecciones de victorias de las casas y cambios de plantilla.
4. Guardar partes de lesiones por hora y medir su valor frente a las líneas.
5. Módulo de fútbol (Poisson / Dixon-Coles con xG) con el mismo protocolo DEV/VAL/TEST.
6. Mercados menos eficientes que el spread (props de jugador): exigen el mismo rigor y cuotas históricas.

## Convenciones
Identificadores en inglés; docstrings y mensajes en español. Probabilidades en [0,1]; márgenes en puntos del local
(+ favorece al local). Cuotas americanas. Sin claves ni credenciales en el repositorio.
