# CLAUDE.md

Lee y sigue siempre `AGENTS.md` (raíz de este proyecto) antes de cambiar nada: contiene las reglas anti-sobreajuste,
la estructura y la hoja de ruta. Lee también `docs/AUDITORIA.md` para entender qué se descartó y por qué.

Reglas mínimas:
- No tocar parámetros, variables ni umbrales mirando los bloques VAL (2020-21) o TEST (2022-26).
- Cada cambio nuevo lleva test y `pytest -q` debe seguir pasando.
- Nunca guardes claves de API en archivos del repositorio: usa variables de entorno.
- Si cambias la matemática de `elo.py` o `availability.py`, replícala en `web/analizador_template.html` y pasa `web/tests/web_parity.js`.
