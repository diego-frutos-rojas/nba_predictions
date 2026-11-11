---
name: traspaso
description: Nota de fin de sesión para que el otro (o su Claude) retome el trabajo del proyecto NBA. Usar al terminar una sesión o cuando se pida un traspaso / handoff.
---

# /traspaso

1. Recoge el estado real, sin suponer: `git status -sb`, `git log --oneline -10`, rama actual, PRs abiertos si se conocen.
2. Ejecuta `uv run pytest -q` y `uv run ruff check .` y anota el resultado tal cual (si algo falla, se dice).
3. Añade **una línea** al final de `ROADMAP.md` → "Registro de traspasos":
   `- AAAA-MM-DD · quién · qué se hizo (pasos del roadmap) · qué queda a medias / siguiente paso`
4. Marca `[x]` los pasos terminados y pon el nombre en `[resp: ]` de los que estén en curso.
5. Si se descartó algún experimento: comprueba que está en `docs/AUDITORIA.md` §5.
6. Devuelve en el chat un resumen de 5 líneas como máximo: hecho, a medias, bloqueos, decisiones pendientes del socio, siguiente paso.

No hagas commit ni push sin que te lo pidan.
