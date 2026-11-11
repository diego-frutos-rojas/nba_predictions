# Auditoría técnica del repositorio (11-nov-2026)

> Revisión del repo `diego-frutos-rojas/nba_predictions`, commit `cce7021` (`main`).
> Complementa a `docs/AUDITORIA.md`, que audita el **modelo**. Este documento audita el **proyecto**: repo, código, tests,
> metodología de evaluación, automatización y camino a producto. Termina con un plan priorizado y los comandos de la fase 0.

## 0. Resumen

| Área | Estado | Lo más importante |
|---|---|---|
| Metodología del modelo | 🟢 Muy buena | DEV/VAL/TEST, test de fuga, promediado del 5 % mejor y negativos documentados. Pocas cosas que tocar. |
| Tests | 🟡 Bien, con huecos | 39 pasan (26 s) y la cobertura es del 70 %, pero el código que **produce las conclusiones** (`evaluate.py`, `props_eval.py`, `metrics.py`) está entre el 15 % y el 47 %. |
| Higiene del repo | 🔴 Urgente | `.venv/` está versionado: 7.837 de los 7.954 archivos del repo (98,5 %) y `.git` ocupa 86 MB. También `__pycache__` y archivos generados. |
| Trabajo en pareja | 🟡 | No hay CI, plantilla de PR ni tareas con responsable. Además usáis versiones distintas de Python (hay `.pyc` de 3.12 y de 3.13). |
| Automatización | 🔴 | Todo es manual. En `data/predictions/` hay **un solo día** guardado, y la "prueba limpia" del modelo de props depende de acumular ese historial. |
| Camino a web o producto | 🟡 | La matemática está duplicada en Python y JS (con tests de paridad), son tres HTML independientes y una de las páginas está obsoleta (v0). |

**Conclusión:** el modelo y el rigor estadístico están por encima de lo normal en un proyecto de este tipo. Lo que frena ahora es la infraestructura: git sucio, sin CI y sin recogida diaria. Arreglarlo cuesta poco y desbloquea todo lo demás.

---

## 1. Qué se revisó y cómo

- Se clonó el repo en un entorno limpio (Linux, Python 3.12) y se instaló `requirements.txt`.
- `pytest -q`: **39 passed en 25,6 s**.
- `pytest --cov=nba_model`: cobertura por módulo (tabla en la sección 3).
- `ruff check --select F,E9,B`: errores reales y bugs típicos.
- Tests de paridad JS (`web/tests/*.js`) y revisión manual de `elo.py`, `baselines.py`, `market.py`, `daily.py`, `espn.py` y `availability.py`.
- Historial de git, archivos versionados y su tamaño.

---

## 2. Repositorio y git

### 2.1 🔴 `.venv/` versionado (crítico)
- `git ls-files | grep ^.venv` devuelve **7.837 archivos** (`.venv/Lib`, `.venv/Scripts`): es un entorno virtual **de Windows**.
- **Por qué importa:**
  - Clonar y hacer pull es lento: `.git` ocupa 86 MB, cuando el código son unos 100 KB.
  - En Mac o Linux ese entorno no sirve.
  - Cada `pip install` genera cientos de cambios espurios y conflictos de merge.
- **Arreglo:** dejar de seguirlo (`git rm -r --cached .venv`) y añadirlo a `.gitignore`. Los comandos están en la sección 8.
- **Opcional:** borrarlo también del historial con `git filter-repo` para que el repo vuelva a pesar unos pocos MB. Reescribe el historial, así que solo se hace con los dos de acuerdo y re-clonando después.

### 2.2 🔴 `__pycache__/` versionado y versiones de Python distintas
- Hay `nba_model/__pycache__/*.cpython-312.pyc` **y** `*.cpython-313.pyc`, y también `tests/__pycache__`. Uno de los dos usa Python 3.12 y el otro 3.13.
- **Arreglo:** dejar de seguir esas carpetas, fijar la versión de Python (`.python-version` con `3.12` y `requires-python` en `pyproject.toml`) y usarla en la CI.

### 2.3 🟠 Archivos generados en git (causa de conflictos)
Cada ejecución del portal o del pipeline los reescribe, así que si los dos lo ejecutáis tendréis conflictos seguros:

| Archivo | Tamaño | Lo genera |
|---|---|---|
| `viz/portal-nba.html` | 636 KB | `scripts/portal.py` |
| `viz/analizador-nba.html` | 65 KB | `scripts/export_web.py` |
| `web/state.json`, `web/parity.json` | 43 KB | `export_web.py` |
| `docs/RESULTADOS*.json/.md` | 80 KB | `run_pipeline.py`, `run_props.py` |
| `data/live/*.csv` | 680 KB | `portal.py` |

**Propuesta:**
- `viz/*.html` **fuera de `main`**. Los genera la automatización diaria (sección 5) y se publican en GitHub Pages.
- `data/live/` **no se puede ignorar sin más**: `odds.csv` y `props.csv` guardan las cuotas previas a cada partido, y ESPN no las conserva después de la temporada. Son historial irrecuperable. Pasan a escribirse **solo por el bot** en la rama `data` (sección 5). Hasta entonces, que solo uno de los dos ejecute el portal y suba esos archivos.
- `docs/RESULTADOS*` se quedan en git, porque son resultados "oficiales", pero solo se regeneran en un PR dedicado ("re-evaluación").
- `data/predictions/` **sí** se versiona, ya que es el historial real, aunque lo escribe el bot y no vosotros a mano.

### 2.4 🟡 Datos crudos en git (19 MB, `sbr.json` de 7 MB)
De momento es aceptable porque se pueden re-descargar con `--fetch`. Cuando haya recogida diaria, mejor:
- `data/raw/` en `.gitignore` con una caché en la CI (`actions/cache`), o
- un *release* de GitHub con los parquet, o DVC si crece mucho.

### 2.5 🟡 Dependencias sin fijar
`requirements.txt` solo pone mínimos (`pandas>=2.0`). Si sale pandas 3, el modelo puede cambiar sin que nadie toque el código.
- **Arreglo:** `pyproject.toml` más un lockfile con `uv` (`uv lock`) o `pip-tools` (`requirements.lock`). Los dos instaláis exactamente lo mismo y la CI también.

---

## 3. Código y tests

### 3.1 Cobertura por módulo

| Módulo | Cobertura | Comentario |
|---|---|---|
| `availability.py`, `webstate.py` | 99-100 % | ✅ |
| `props.py`, `elo.py` | 95-97 % | ✅ El núcleo del modelo está bien cubierto. |
| `daily.py`, `market.py`, `odds.py` | 92-96 % | ✅ |
| `data.py`, `espn.py` | 82-85 % | OK, porque las partes sin cubrir son de red. |
| `live.py` | 67 % | |
| `metrics.py` | **47 %** | ⚠️ Calcula log loss y ECE, que son la base de **todas** las conclusiones. |
| `ratings.py`, `baselines.py` | 30-33 % | ⚠️ `baselines.market_prob` es la referencia "mercado". |
| `evaluate.py` | **25 %** | ⚠️ Produce las cifras de README y AUDITORIA. |
| `props_eval.py` | **15 %** | ⚠️ Produce el ROI de props y los umbrales de ventaja. |
| `tune.py`, `player_model.py` | 0 % | `player_model` es un experimento descartado; `tune` hay que cubrirlo. |

**Riesgo:** un error en `metrics.py` o `evaluate.py` invalidaría las conclusiones sin que ningún test fallase. Prioridad: tests con **valores conocidos a mano**, por ejemplo:
- el log loss de p = 0,5 es ln 2;
- el ECE de un predictor perfectamente calibrado es 0;
- `market_prob(0) = 0,5`;
- el ROI de apostar siempre a −110 y acertar el 50 % es −4,55 %.

### 3.2 Tests que se saltan en silencio
`tests/test_daily.py::test_page_math_matches_python` hace `pytest.skip` si no hay `node`, y `web/tests/web_parity.js` necesita `jsdom` (sin instalar falla con `Cannot find module 'jsdom'`). Ninguno de los dos se ejecuta en una CI, así que la paridad Python↔JS **puede romperse sin que nadie se entere**.
- **Arreglo:** la CI instala node y `npm ci` en `web/tests`, y ejecuta los dos `.js`.

### 3.3 Inconsistencia de constantes: σ del mercado
- `baselines.py`: `SIGMA_MARKET = 11.25` (ajustada en DEV) para convertir spread en probabilidad en la **evaluación**.
- `market.py`: `reference_prob(..., sigma=12.0)` y `needed_adjustment_pts(..., sigma=12.0)` en el **portal diario**.

Así, el "mercado" del portal no es el mismo que el del backtest. Hay que unificarlo en una sola constante, importada desde un único sitio.

### 3.4 Lint (ruff: F, E9, B)
- 3 imports sin usar: `scripts/run_pipeline.py:18` (`BOUNDS`), y `scripts/run_report.py:7` y `:23` (`json`, `normal_cdf`).
- 1 variable sin usar: `nba_model/webstate.py:58` (`probs`).
- Los avisos `B023` (lambdas dentro de bucles en `availability.py:54`, `espn.py:212` y `props.py:78`) son **falsos positivos**: las lambdas se usan dentro de la misma iteración. Aun así conviene cambiarlas por funciones auxiliares, porque es un patrón frágil.
- **Propuesta:** `ruff` con su configuración en `pyproject.toml` y `pre-commit`. Así se formatea y se revisa antes de cada commit, igual para los dos.

### 3.5 Menores
- `daily.py:309` hace `json.dump(out, open(path, "w"))` sin `with`. En Windows el archivo puede quedar bloqueado. Mejor `Path(path).write_text(json.dumps(...))`.
- `daily.py:167` y `:201` capturan `except Exception` y lo convierten en un aviso. Es razonable para el portal, pero en la automatización esos avisos deben hacer **fallar el job o notificar**. Si no, el historial se llena de días con datos incompletos sin que nadie lo sepa.
- `viz/mesa-cuotas-nba.html` está basado en v0 (lo dice el README). O se borra o se mueve a `archive/`.

### 3.6 Matemática duplicada Python ↔ JS
Hoy está controlada con tests de paridad, pero es la deuda técnica más cara a medio plazo: cada cambio del modelo se hace dos veces. Opciones, de menos a más trabajo:
1. **Seguir así**, pero con la paridad en la CI (3.2).
2. **Calcularlo todo en Python** y que el HTML solo pinte. Es lo que ya hace el portal, salvo el bloque `CALC`. El analizador interactivo es lo único que necesita calcular en el navegador.
3. **Pyodide**, que ejecuta el mismo `elo.py` en el navegador. Elimina la duplicación, pero la página pesa unos 10 MB.
4. **API (FastAPI)** cuando haya web de verdad. El front llama a la API y no queda ninguna copia de la matemática.

Recomendación: la 1 ahora y la 4 cuando paséis a web.

---

## 4. Modelo y metodología estadística

### 4.1 Lo que está muy bien (mantenerlo)
- Bloques DEV/VAL/TEST con TEST mirado una sola vez, y validación cruzada temporal dentro de DEV.
- Test explícito de fuga: cambiar un resultado futuro no altera predicciones pasadas.
- Hiperparámetros promediados sobre el 5 % mejor en vez de quedarse con el máximo.
- Contrastes preespecificados con corrección por comparaciones múltiples.
- Los negativos se documentan, y "el modelo no bate al mercado" se reporta con honestidad.

### 4.2 Mejoras propuestas (todas compatibles con las reglas de `AGENTS.md`)

**a) La σ del mercado es fija y la del modelo es dinámica.** El modelo estima σ online porque el margen NBA es más variable hoy (~16 puntos) que en 2012 (~13). En cambio, el mercado se convierte con σ = 11,25, fijada en 2012-19.
- Si la dispersión del residuo del mercado también ha crecido en 2022-26, esa σ fija hace al mercado **demasiado confiado** en TEST. Su log loss saldría peor de lo que es y la distancia modelo-mercado quedaría **infraestimada**.
- **Cómo comprobarlo sin fuga:** estimar la σ del mercado online (EWMA de `margen − spread`, igual que en `elo.py`) y ver la pendiente de calibración del mercado en TEST.
- Es una hipótesis que hay que medir, no un error confirmado.

**b) Evaluar la distribución, no solo la probabilidad de victoria.** El modelo predice un margen con distribución normal. Faltan tres comprobaciones:
- un **histograma PIT** (debe ser plano si la normal es adecuada);
- el **CRPS** del margen;
- las **colas**: si sobran blowouts, probar con una t de Student, cuyos grados de libertad se ajustan en DEV.

Esto importa para spreads y totales, no solo para el moneyline.

**c) Descomposición de Brier** en fiabilidad, resolución e incertidumbre, junto a diagramas de fiabilidad por bloque. Explica *por qué* el mercado gana: ¿por resolución (más información) o por calibración?

**d) Recalibración legítima.** La pendiente de 1,05-1,08 en TEST no se corrigió para no sobreajustar, y es correcto. Pero se puede ajustar una recalibración de Platt **solo en DEV** y aplicarla congelada. Eso no es mirar TEST.

**e) Tamaño muestral para hablar de ventaja.** Una apuesta a −110 tiene una desviación típica de unos 0,95 unidades. Para detectar con un 95 % de confianza un ROI real del +2 % hacen falta:

  n ≈ (1,96 × 0,95 / 0,02)² ≈ **8.700 apuestas**

Con 154 partidos de props no se puede concluir nada en ningún sentido, y así hay que contarlo en la web. Propuesta: mostrar siempre el intervalo de confianza y el n necesario junto a cualquier ROI.

**f) CLV (valor frente al cierre)** como métrica principal del modelo en producción, que ya es la prioridad 1 de la hoja de ruta. Converge con muchas menos muestras que el ROI y es lo que de verdad mide si hay información. Requiere guardar las cuotas con marca de tiempo varias veces al día, cosa que da la automatización.

**g) Inicio de temporada.** Todos los equipos aplican `carry = 0,75`, se haya reforzado mucho o no. El *prior* con las proyecciones de victorias de las casas (hoja de ruta, punto 3) es probablemente la mejora con mejor relación esfuerzo/ganancia del modelo de partidos.

---

## 5. Automatización diaria

**Por qué es prioritaria:** no es solo comodidad. `AGENTS.md` (problema 0b) reconoce que la única prueba limpia del modelo de props es el historial que acumula el portal, y hoy hay **un día** guardado (`data/predictions/2026-11-10.json`). Cada día sin recoger es una muestra perdida que no se recupera, porque ESPN solo guarda las props de la temporada en curso.

**Propuesta: GitHub Actions** (gratis en repos públicos).

```
.github/workflows/
├── ci.yml          # en cada PR: ruff + pytest + paridad JS (node + jsdom)
└── daily.yml       # cron: recoge, predice, guarda y publica
```

`daily.yml`, con horas UTC (los partidos empiezan entre las 00:00 y las 04:30 de Madrid):

| Ejecución | Hora | Qué hace |
|---|---|---|
| Mañana | ~15:00 UTC | Cuotas y lesiones de apertura (*snapshot* con marca de tiempo) |
| Pre-partido | ~22:30 UTC | Cuotas y lesiones cercanas al inicio; predicciones del día → `data/predictions/` |
| Post-jornada | ~09:00 UTC | Resultados, cajas y cierre; actualiza el historial de acierto |

- 🟠 **Bloqueante para el CLV:** `live.save_market` hace *upsert* por `game_id` (y por `pid` y `market` en las props), así que **cada ejecución sobrescribe la anterior**. Hoy solo queda la última foto de las cuotas, sin marca de tiempo. Para medir apertura frente a cierre y cómo se mueven las líneas tras una lesión, hay que guardar en modo *append* con `fetched_at` (por ejemplo `data/live/odds_snapshots.parquet`) y derivar de ahí la "última línea antes del inicio".
- Lo hace en la rama **`data`**, no en `main`, para que el bot no os genere conflictos. Publica `portal-nba.html` en **GitHub Pages**: una URL fija con el portal de cada día, sin servidor.
- Si `daily.py` acumula avisos (3.5), el job falla y GitHub os manda un email.
- **A verificar:** la API de ESPN no está documentada. Desde este entorno de revisión no se pudo comprobar su acceso (lo bloquea la red del entorno), así que lo primero es lanzar el workflow a mano (`workflow_dispatch`) y ver si los *runners* de GitHub reciben respuesta. Si no, la alternativa es un *runner* propio en vuestro PC.

---

## 6. Camino a web y monetización

1. **Ya (coste 0):** GitHub Pages con el portal diario y la página de historial y métricas.
2. **Después:** un dashboard único (Streamlit o Next.js estático) que junte portal, analizador e historial de rendimiento, con datos en DuckDB o SQLite.
3. **Producto:** API (FastAPI), usuarios y planes.

**Antes de monetizar o hacerlo público con tráfico, revisar:**
- **Términos de uso de las fuentes.** La API de ESPN no es pública ni documentada y las cuotas son de DraftKings. Para uso comercial probablemente haga falta una fuente con licencia (APIs de cuotas de pago).
- **Normativa española de juego.** Un producto que muestra "picks" y cuotas puede tocar la regulación del juego (Ley 13/2011) y la de comunicaciones comerciales de apuestas (RD 958/2020). Conviene consultarlo con alguien de derecho antes de lanzar. Esto no es asesoramiento legal.
- **Posicionamiento.** El valor demostrable del proyecto es el **rigor**, no los picks: probabilidades calibradas, transparencia y "por qué el mercado gana". Es más defendible legalmente y como producto (contenido, análisis o B2B) que vender apuestas.

---

## 7. Plan priorizado

| Fase | Qué | Esfuerzo | Por qué primero |
|---|---|---|---|
| **0. Limpieza** (hoy, juntos) | Quitar `.venv`/`__pycache__`/generados de git, `.gitignore`, `.python-version`, `pyproject.toml` y lock | ~1 h | Todo lo demás depende de un repo limpio |
| **1. Base de equipo** | `ci.yml`, plantilla de PR, protección de `main`, `TASKS.md`, unificar σ (3.3), lint | ~½ día | Evita romper cosas sin daros cuenta |
| **2. Tests de la evaluación** | `metrics.py`, `evaluate.py`, `props_eval.py`, `baselines.py` con valores conocidos | ~1 día | Protege las conclusiones |
| **3. Automatización** | Snapshots de cuotas con marca de tiempo (append) + `daily.yml` + rama `data` + GitHub Pages | ~1-2 días | Cada día perdido no se recupera |
| **4. Análisis técnico** | 4.2 a-f: σ del mercado, PIT/CRPS, Brier, Platt en DEV, n necesario, CLV | 1-2 semanas | Lo que pedís de "mucho más técnico" |
| **5. Visual** | Dashboard único de rendimiento (calibración, CLV, historial) | 1 semana | |
| **6. Producto** | API, web, estudio legal y de licencias de datos | — | |

---

## 8. Fase 0 paso a paso

> **Coordinaos:** que solo **uno** lo haga y el otro no tenga cambios sin subir. Al terminar, el otro hace `git pull`.

**1. Rama de trabajo**
```
git checkout main && git pull
git checkout -b chore/limpieza-repo
```

**2. Añadir a `.gitignore`**
```
# entornos
.venv/
venv/
# python
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.coverage
# node
node_modules/
# generados (los produce la automatización)
viz/portal-nba.html
# sistema
.DS_Store
Thumbs.db
```

**3. Dejar de seguir lo que ya estaba subido** (no borra nada de vuestro disco)
```
git rm -r --cached .venv nba_model/__pycache__ tests/__pycache__
git rm --cached viz/portal-nba.html
```
(`data/live/` se queda versionado de momento porque es historial de cuotas: ver 2.3).

**4. Fijar la versión de Python**
```
echo 3.12 > .python-version
```

**5. Comprobar que todo sigue funcionando**
```
pytest -q            # 39 passed
```

**6. Commit, push y PR**
```
git add .gitignore .python-version
git commit -m "chore: dejar de versionar .venv, __pycache__ y archivos generados"
git push -u origin chore/limpieza-repo
```
Después, abrid el PR en GitHub, que lo revise el otro y hacéis merge.

**7. (Opcional) Reducir el historial** de 86 MB a unos pocos con `git filter-repo --path .venv --invert-paths`. Reescribe el historial: después **los dos** volvéis a clonar.
