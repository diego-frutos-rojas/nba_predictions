@echo off
rem Genera el sitio web NBA (webapp\dist) y lo abre en el navegador (doble clic).
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
"%PY%" webapp\build.py --open %*
if errorlevel 1 pause
