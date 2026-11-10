#!/usr/bin/env bash
# Genera el portal NBA del día y lo abre en el navegador.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
exec "$PY" scripts/portal.py --open "$@"
