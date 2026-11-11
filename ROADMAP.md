# ROADMAP: proyecto NBA

> Plan de trabajo por fases. Detalle técnico de cada punto en `docs/AUDITORIA_TECNICA.md`.
> **Cómo se usa:**
> - Cada paso es **una rama + un PR** (`tipo/descripcion-corta`, por ejemplo `ci/github-actions`) y lo revisa el otro antes del merge.
> - Para cogerse un paso, se pone el nombre en `[resp: ]`. Al acabar, se marca `[x]` en el mismo PR.
> - No se empieza una fase sin cerrar los pasos marcados como 🔒 (bloqueantes) de la anterior.
> - Las reglas de `AGENTS.md` (DEV/VAL/TEST, test de fuga, paridad JS) se aplican a **todos** los pasos.

**Leyenda:** 🔒 bloqueante · ⏱ esfuerzo estimado · ✅ "hecho cuando…"

---

## FASE 0: Limpieza del repo · semana 1 · ⏱ 1-2 h
*Objetivo: un repo ligero que funcione igual para los dos.*

- [x] **0.1** 🔒 Sacar `.venv/` de git `[resp: Diego]`
  - `.gitignore` ya actualizado. Falta: `git rm -r --cached .venv`, commit, PR y merge.
  - ✅ `git ls-files | grep .venv` no devuelve nada.
  - ⚠️ Tras el pull, el socio recrea su entorno: `python -m venv .venv` + `pip install -r requirements.txt`.
- [x] **0.2** 🔒 Sacar `__pycache__/` de git `[resp: Diego]`
  - `git rm -r --cached nba_model/__pycache__ tests/__pycache__`
  - ✅ No hay ningún `.pyc` versionado.
- [x] **0.3** 🔒 Fijar la versión de Python `[resp: Diego]`
  - `.python-version` = **3.13** (no 3.12: es la que ya tiene `uv` instalada y tiene wheels de todo; 3.15 aún no). El entorno se recrea con ella en el paso 1.1 (`uv sync`).
  - ✅ Los dos ejecutáis `python --version` y sale lo mismo.
- [x] **0.4** Sacar `viz/portal-nba.html` de git (generado, 636 KB) `[resp: Diego]`
  - Añadirlo a `.gitignore` y `git rm --cached viz/portal-nba.html`.
- [x] **0.5** Archivar `viz/mesa-cuotas-nba.html` (obsoleto, modelo v0) `[resp: Diego]`
  - Movido a `archive/`.
- [ ] **0.6** (Opcional) Reducir el historial de git de 86 MB `[resp: ]`
  - `git filter-repo --path .venv --invert-paths`. **Solo con los dos de acuerdo**; después, los dos re-clonáis.

---

## FASE 1: Base de equipo y herramientas · semana 1-2 · ⏱ ½-1 día
*Objetivo: no romper nada sin enterarse y trabajar igual los dos.*

- [ ] **1.1** 🔒 `pyproject.toml` + lockfile `[resp: ]`
  - Pasar `requirements.txt` a `pyproject.toml`, usar `uv lock` y documentar `uv sync` en el README.
  - ✅ En una carpeta limpia, `uv sync && pytest -q` da 39 passed.
- [ ] **1.2** 🔒 CI con GitHub Actions (`.github/workflows/ci.yml`) `[resp: ]`
  - En cada PR: `ruff check`, `pytest -q` y los tests de paridad JS (node + `npm ci` en `web/tests`).
  - ✅ El PR muestra el check verde, y un test roto lo pone rojo.
- [ ] **1.3** 🔒 Proteger `main` en GitHub `[resp: ]`
  - Settings → Branches: exigir PR, 1 aprobación y CI en verde. Nadie hace push directo a `main`.
- [ ] **1.4** Plantilla de PR (`.github/pull_request_template.md`) `[resp: ]`
  - Checklist: ¿test nuevo?, ¿miraste VAL o TEST? (no), ¿paridad JS?, ¿actualizaste `AUDITORIA.md` si hubo negativos?
- [ ] **1.5** Lint y formato: `ruff` + `pre-commit` `[resp: ]`
  - Configuración en `pyproject.toml` y `pre-commit install`. Arreglar los 3 imports y la variable sin usar.
- [ ] **1.6** Unificar la σ del mercado (11,25 en `baselines.py` y 12,0 en `market.py`) `[resp: ]`
  - Una sola constante importada desde un único módulo, con su test.
- [ ] **1.7** Claude para los dos `[resp: ambos]`
  - Instalar la extensión Claude Code en VS Code.
  - Plugins: `github`, `Data`, `Cairn Memory`.
  - Revisar `CLAUDE.md` (corto, que apunte a `AGENTS.md` y a este `ROADMAP.md`).
- [ ] **1.8** Skills propias del proyecto (`.claude/skills/`) `[resp: ]`
  - `/nueva-variable`: protocolo completo (validación cruzada en DEV → test de fuga → paridad → TEST una vez → documentar).
  - `/portal-diario`: generar el portal y revisar los avisos.
  - `/traspaso`: nota de fin de sesión para que el otro (o su Claude) retome.

---

## FASE 2: Blindar la evaluación · semana 2 · ⏱ 1 día
*Objetivo: que las conclusiones del README estén protegidas por tests.*

- [ ] **2.1** 🔒 Tests de `metrics.py` con valores conocidos `[resp: ]`
  - Log loss de p = 0,5 → ln 2; ECE de un predictor perfecto → 0; Brier de casos triviales.
- [ ] **2.2** 🔒 Tests de `baselines.py` `[resp: ]`
  - `market_prob(0) = 0,5`, simetría y `NaN` cuando no hay línea.
- [ ] **2.3** Tests de `evaluate.py` con un mini-dataset sintético `[resp: ]`
- [ ] **2.4** Tests de `props_eval.py`: ROI a −110 con un 50 % de acierto → −4,55 % `[resp: ]`
- [ ] **2.5** Test de `tune.py`: el promedio del 5 % mejor es determinista con semilla `[resp: ]`
- ✅ **Fin de fase:** cobertura ≥ 85 % en `metrics`, `baselines`, `evaluate` y `props_eval`.

---

## FASE 3: Automatización diaria · semana 2-3 · ⏱ 1-2 días
*Objetivo: el sistema recoge datos solo, todos los días. **Cada día sin esto es una muestra perdida.***

- [ ] **3.1** 🔒 Guardar las cuotas con marca de tiempo (append, no sobrescribir) `[resp: ]`
  - Cambiar `live.save_market` para que añada filas con `fetched_at` en `data/live/odds_snapshots.parquet` y `props_snapshots.parquet`.
  - Función `closing_line(game_id)` = última foto antes del inicio del partido.
  - ✅ Test: dos guardados seguidos dan 2 filas, no 1.
- [ ] **3.2** 🔒 Guardar los partes de lesiones con marca de tiempo `[resp: ]`
- [ ] **3.3** 🔒 Probar el acceso a ESPN desde GitHub Actions `[resp: ]`
  - Un workflow manual (`workflow_dispatch`) que solo descargue el scoreboard.
  - ✅ Responde 200. Si no, plan B: un *self-hosted runner* en el PC de uno de los dos.
- [ ] **3.4** `daily.yml` con 3 ejecuciones (UTC) `[resp: ]`
  - ~15:00 cuotas de apertura · ~22:30 pre-partido + predicciones · ~09:00 resultados y cierre.
  - Commits del bot a la rama **`data`**, nunca a `main`.
- [ ] **3.5** Alertas `[resp: ]`
  - Si `daily.py` acumula avisos, el job falla y GitHub manda un email.
- [ ] **3.6** Publicar el portal en GitHub Pages `[resp: ]`
  - ✅ Una URL fija con el portal del día, actualizada sola.
- ✅ **Fin de fase:** 7 días seguidos con snapshots y predicciones guardadas sin tocar nada.

---

## FASE 4: Refactor de arquitectura · semana 3-5 · ⏱ 1 semana
*Objetivo: un código preparado para crecer (web, más deportes) y fácil de repartir.*

- [ ] **4.1** Reorganizar en capas `[resp: ]`
  - `ingest/` (ESPN, GitHub) → `features/` (descanso, disponibilidad) → `models/` (elo, props) → `evaluation/` → `serving/` (portal, exportadores).
  - Partir `daily.py` (382 líneas) y `props.py` (485) por responsabilidades.
  - ✅ Los mismos tests pasan sin cambiar ninguna cifra de `RESULTADOS.md`.
- [ ] **4.2** Configuración centralizada (`config.py` con rutas, URLs y constantes) `[resp: ]`
- [ ] **4.3** DuckDB como almacén único (`data/nba.duckdb`) `[resp: ]`
  - Tablas: `games`, `boxes`, `odds_snapshots`, `props_snapshots`, `injuries_snapshots`, `predictions`.
- [ ] **4.4** Validación de datos con `pandera` en la entrada de cada tabla `[resp: ]`
- [ ] **4.5** `logging` en vez de `print`, y `with` en todos los `open()` (`daily.py:309`) `[resp: ]`
- [ ] **4.6** Registro de modelos `[resp: ]`
  - Cada `models/*.json` con versión, fecha, hash de los datos, commit y métricas DEV.
  - Cada predicción guarda qué versión la hizo.
- [ ] **4.7** Tipado + `mypy` en `models/` y `evaluation/` `[resp: ]`
- [ ] **4.8** Tests de fuga con `hypothesis` (propiedad: el futuro nunca altera el pasado) `[resp: ]`

---

## FASE 5: Análisis técnico · semana 4-7 · ⏱ 2-3 semanas
*Objetivo: el "apartado mucho más técnico". Cada punto lleva su notebook o informe en `docs/analisis/`.*

- [ ] **5.1** σ del mercado online (EWMA de `margen − spread`) `[resp: ]`
  - ¿Cambia la distancia entre modelo y mercado en TEST? Reportarlo salga lo que salga.
- [ ] **5.2** Evaluación de la distribución del margen: histograma PIT, CRPS, colas (normal frente a t de Student) `[resp: ]`
- [ ] **5.3** Descomposición de Brier (fiabilidad / resolución) y diagramas de fiabilidad por bloque `[resp: ]`
- [ ] **5.4** Recalibración de Platt ajustada **solo en DEV** y congelada `[resp: ]`
- [ ] **5.5** Calculadora de tamaño muestral: n necesario para detectar un ROI dado (≈ 8.700 apuestas para +2 %) `[resp: ]`
- [ ] **5.6** CLV como métrica principal, en cuanto haya 2-3 semanas de snapshots (requiere 3.1) `[resp: ]`
- [ ] **5.7** 🔒 **Modelo anclado al mercado**: el modelo predice la corrección sobre la línea, no la línea `[resp: ]`
  - Protocolo completo DEV → TEST una vez.
- [ ] **5.8** Informe técnico consolidado (`docs/INFORME_TECNICO.md`): metodología, resultados y negativos `[resp: ]`

---

## FASE 6: Visualización y web pública · semana 6-9 · ⏱ 1-2 semanas
*Objetivo: algo que se pueda enseñar. Primer activo público.*

- [ ] **6.1** 🔒 Página de **track record**: todas las predicciones, calibración, CLV e intervalos, sin borrar nada `[resp: ]`
- [ ] **6.2** Dashboard único: portal + analizador + track record con una navegación común `[resp: ]`
- [ ] **6.3** Gráficos de los análisis de la fase 5 (fiabilidad, PIT, evolución del CLV) `[resp: ]`
- [ ] **6.4** Mobile-first y modo oscuro `[resp: ]`
- [ ] **6.5** Página "metodología" para el público: cómo funciona el modelo y por qué no se venden picks `[resp: ]`
- [ ] **6.6** Dominio propio y analítica de visitas (Plausible o Umami, respetuosas con la privacidad) `[resp: ]`

---

## FASE 7: Modelo v3 · semana 8-14 · ⏱ continuo
*Objetivo: mejor modelo, siempre con el protocolo de `AGENTS.md`.*

- [ ] **7.1** Prior de inicio de temporada con las proyecciones de victorias de las casas `[resp: ]`
- [ ] **7.2** Impacto de jugador con jugada a jugada / quintetos (RAPM) `[resp: ]`
- [ ] **7.3** Props con un modelo bayesiano jerárquico (PyMC) `[resp: ]`
- [ ] **7.4** Totales (over/under del partido) `[resp: ]`
- [ ] **7.5** Probabilidad de victoria en directo `[resp: ]`
- [ ] **7.6** Variables nuevas: viajes, husos horarios, altitud, árbitros `[resp: ]`

---

## FASE 8: Validar el producto · mes 3-4
*Objetivo: descubrir qué interesa antes de construir más. Decidir con datos, no con intuición.*

- [ ] **8.1** 🔒 Consulta legal: normativa de juego española (Ley 13/2011, RD 958/2020) y términos de uso de ESPN y de las cuotas `[resp: ]`
- [ ] **8.2** 🔒 Fuente de datos con licencia si hay uso comercial (comparar APIs de cuotas de pago) `[resp: ]`
- [ ] **8.3** Contenido: newsletter + 1 red social, con 1-2 piezas por semana a partir de los análisis `[resp: ]`
- [ ] **8.4** Proyecciones fantasy a partir del modelo de props (prueba gratuita) `[resp: ]`
- [ ] **8.5** Métricas de tracción: suscriptores, visitas recurrentes, peticiones de API `[resp: ]`
- ✅ **Fin de fase:** una de las opciones (contenido, fantasy, B2B) tiene una tracción clara frente a las demás.

---

## FASE 9: Escalar o pivotar · mes 5+
*Decidir según los resultados de la fase 8.*

- [ ] **9.1** Monetizar el canal ganador: suscripción, patrocinio o API de pago `[resp: ]`
- [ ] **9.2** API con FastAPI y usuarios (la matemática duplicada en JS desaparece) `[resp: ]`
- [ ] **9.3** Expansión con el mismo protocolo: fútbol (Dixon-Coles), ACB/Euroliga o valoración salarial de jugadores `[resp: ]`
- [ ] **9.4** B2B: contactar con clubes ACB o medios con el track record como carta de presentación `[resp: ]`

---

## Hitos

| Hito | Cuándo | Señal de éxito |
|---|---|---|
| 🧹 Repo limpio y con CI | Fin de la semana 2 | PRs con check verde, `main` protegida |
| 🤖 Recogida automática | Fin de la semana 3 | 7 días seguidos sin intervención |
| 📊 Informe técnico | Semana 7 | `docs/INFORME_TECNICO.md` publicado |
| 🌐 Web pública con track record | Semana 9 | URL pública con historial y calibración |
| 💡 Decisión de producto | Mes 4 | Una vía con tracción medida |

## Registro de traspasos
*Al acabar cada sesión, una línea: fecha · quién · qué se hizo · qué queda a medias.*

- 2026-11-11 · Diego (+Claude) · Auditoría técnica (`docs/AUDITORIA_TECNICA.md`), roadmap y `.gitignore` con `.venv/` · Pendiente: 0.1 (`git rm --cached .venv` + PR)
- 2026-11-11 · Diego (+Claude) · Fase 0 cerrada (0.1-0.5): `.python-version` 3.13, `mesa-cuotas` a `archive/` · Pendiente: 0.6 (opcional, requiere acuerdo de los dos) y que el socio confirme la versión de Python
