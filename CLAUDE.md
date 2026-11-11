# CLAUDE.md

Antes de cambiar nada, lee:
- `AGENTS.md`: reglas anti-sobreajuste, comandos, estructura y problemas conocidos. **Manda sobre todo lo demás.**
- `ROADMAP.md`: plan por fases y registro de traspasos (qué está hecho y qué toca).
- `docs/AUDITORIA.md` §5: qué se probó y se descartó (no repetirlo).

Reglas mínimas:
- No tocar parámetros, variables ni umbrales mirando los bloques VAL (2020-21) o TEST (2022-26).
- Cada cambio lleva test; `uv run pytest -q` y `uv run ruff check .` deben pasar.
- Trabajo en rama + PR; nunca push directo a `main`. No hacer commit ni push sin que lo pida el usuario.
- Nunca guardes claves de API en el repositorio: usa variables de entorno.
- Si cambias la matemática de `elo.py` o `availability.py`, replícala en `web/analizador_template.html` y pasa `web/tests/web_parity.js`.

Skills del proyecto (`.claude/skills/`): `/nueva-variable`, `/portal-diario`, `/traspaso`.
