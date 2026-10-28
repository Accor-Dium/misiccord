@echo off
cd /d "%~dp0"

set "URL=%~1"
if "%URL%"=="" set /p "URL=Pega el link de la playlist: "

venv\Scripts\python.exe descargar_playlist.py "%URL%"
pause
