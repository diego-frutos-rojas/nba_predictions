---
name: nueva-variable
description: Protocolo completo para añadir una variable, parámetro o feature al modelo NBA sin sobreajustar (DEV → fuga → paridad → TEST una vez → documentar). Usar siempre que se proponga cambiar el modelo.
---

# /nueva-variable

Protocolo obligatorio de `AGENTS.md`. Sigue los pasos en orden y **para** si uno falla.

0. **¿Ya se probó?** Lee `docs/AUDITORIA.md` §5 (negativos). Si está descartada, dilo y no la repitas.
1. **Hipótesis antes de mirar datos.** Escribe en una línea qué efecto esperas y por qué. Fija a priori cualquier constante o umbral.
2. **Rama** `feat/<variable>`.
3. **Validación cruzada solo en DEV (2014-2019).** Afinar en 2014-16 y evaluar en 2017-19, y al revés.
   Los hiperparámetros salen del promedio del 5 % mejor (`tune.py`), nunca del mejor.
   - Si no mejora en **las dos** mitades → descartada: salta al paso 7.
   - **Prohibido** abrir VAL (2020-21) o TEST (2022-26) en este paso.
4. **Test de fuga temporal.** Añade a `tests/` un test como los de `test_core.py`: cambiar un resultado futuro no altera ninguna predicción pasada.
5. **Paridad JS.** Si tocaste `elo.py` o `availability.py`: replica en el bloque `MODEL-START/END` de `web/analizador_template.html` y pasa `node web/tests/web_parity.js`. Si tocaste `daily.side_eval` / `edge_bucket`: bloque `CALC-START/END`.
6. **TEST una sola vez.** `uv run python scripts/run_pipeline.py`. Reporta log loss con IC y la comparación con el mercado, salga lo que salga. No se itera después de mirar TEST.
7. **Documentar.** Positivo o negativo, a `docs/AUDITORIA.md` (§5 si no funcionó). Actualiza la memoria de experimentos descartados.
8. `uv run pytest -q` y `uv run ruff check .` en verde → PR con la plantilla.

Nunca presentes un valor esperado positivo como recomendación de apuesta.
