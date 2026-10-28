@echo off
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo Creando entorno virtual...
    python -m venv venv
)

echo Instalando yt-dlp...
venv\Scripts\python.exe -m pip install -U -r requirements.txt

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo Instalando ffmpeg...
    winget install --id Gyan.FFmpeg -e
    echo.
    echo IMPORTANTE: cierra y vuelve a abrir la terminal para que se detecte ffmpeg.
) else (
    echo ffmpeg ya esta instalado.
)

where deno >nul 2>nul
if errorlevel 1 (
    echo Instalando deno ^(lo usa yt-dlp para leer YouTube^)...
    winget install --id DenoLand.Deno -e
) else (
    echo deno ya esta instalado.
)

echo.
echo Instalacion terminada.
pause
