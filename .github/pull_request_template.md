## Qué cambia
<!-- 1-3 líneas. Paso del ROADMAP si aplica (por ejemplo: 2.1). -->

## Checklist
- [ ] `uv run pytest -q` y `uv run ruff check .` pasan en local.
- [ ] Hay test nuevo para lo que cambia (o explico por qué no hace falta).
- [ ] **No** he elegido parámetros, variables ni umbrales mirando VAL (2020-21) o TEST (2022-26).
- [ ] Si es una variable nueva: validación cruzada dentro de DEV + test de fuga temporal.
- [ ] Si toqué `elo.py`, `availability.py` o `daily.side_eval` / `edge_bucket`: réplica en JS y paridad comprobada.
- [ ] Si probé algo que no funcionó: está en `docs/AUDITORIA.md`, sección 5.
- [ ] Marqué el paso en `ROADMAP.md` y añadí la línea de traspaso.
