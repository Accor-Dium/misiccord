"""Empaqueta el núcleo de Python como servicio-dist/misiccord-servicio/misiccord-servicio.exe.

Tauri lo incluye en el instalador de Windows (bundle.resources) y la app lo arranca al abrir.
ffmpeg, ffprobe y deno viajan en _internal/bin (plataforma.herramienta los busca ahí).

Uso:  ..\\venv\\Scripts\\python.exe scripts\\construir_servicio.py
"""
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def herramienta(nombre: str) -> Path:
    encontrada = shutil.which(nombre)
    if not encontrada:
        sys.exit(f"No encontré {nombre} en el PATH (instálalo con winget)")
    return Path(encontrada).resolve()  # winget deja accesos directos: hace falta el ejecutable real


def main() -> None:
    import PyInstaller.__main__

    os.chdir(RAIZ)
    binarios = [f"--add-binary={herramienta(n)}{os.pathsep}bin" for n in ("ffmpeg", "ffprobe", "deno")]
    PyInstaller.__main__.run([
        str(RAIZ / "python" / "servicio.py"),
        "--name=misiccord-servicio",
        "--console",  # se comunica por stdin/stdout; Tauri lo arranca sin ventana
        "--noconfirm",
        "--clean",
        f"--distpath={RAIZ / 'servicio-dist'}",
        f"--workpath={RAIZ / 'servicio-dist' / '.build'}",
        f"--specpath={RAIZ / 'servicio-dist' / '.build'}",
        f"--paths={RAIZ / 'python'}",
        f"--icon={RAIZ / 'src-tauri' / 'icons' / 'icon.ico'}",
        "--collect-submodules=wavedrop",
        "--collect-all=yt_dlp_ejs",
        "--collect-data=ytmusicapi",
        "--hidden-import=qrcode.image.svg",
        # Lo de la app vieja de escritorio que está en el mismo venv y aquí no se usa
        "--exclude-module=PySide6", "--exclude-module=shiboken6", "--exclude-module=tkinter",
        *binarios,
    ])
    exe = RAIZ / "servicio-dist" / "misiccord-servicio" / "misiccord-servicio.exe"
    print(f"\nServicio listo: {exe} ({sum(f.stat().st_size for f in exe.parent.rglob('*') if f.is_file()) / 1e6:.0f} MB en total)")


if __name__ == "__main__":
    main()
