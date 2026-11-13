#!/usr/bin/env bash
# Genera el sitio web NBA (webapp/dist) y lo abre en el navegador.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
exec "$PY" webapp/build.py --open "$@"
