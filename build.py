"""Arma la app de escritorio y su instalador.

1. Crea el icono (icono.ico) si no existe.
2. Empaqueta app.py con PyInstaller, metiendo ffmpeg, ffprobe y deno en dist/DescargadorPlaylists/_internal/bin.
3. Si Inno Setup está instalado, genera instalador/DescargadorPlaylists-Setup.exe.

Uso:  venv\\Scripts\\python.exe build.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).parent
NOMBRE = "DescargadorPlaylists"


def crear_icono(ruta: Path) -> None:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    img = QImage(256, 256, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    degradado = QLinearGradient(0, 0, 256, 256)
    degradado.setColorAt(0, QColor("#7b4dff"))
    degradado.setColorAt(1, QColor("#2a9df4"))
    p.setBrush(degradado)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 52, 52)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI Symbol", 150, QFont.Bold))
    p.drawText(QRectF(0, -8, 256, 256), Qt.AlignCenter, "♫")
    p.end()
    img.save(str(ruta))
    del app


def herramienta(nombre: str) -> Path:
    encontrada = shutil.which(nombre)
    if not encontrada:
        sys.exit(f"No encontré {nombre}. Corre instalar.bat y abre una terminal nueva.")
    # winget deja accesos directos (symlinks); hay que copiar el ejecutable real
    return Path(encontrada).resolve()


def buscar_iscc() -> Path | None:
    candidatos = [
        shutil.which("iscc"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
    ]
    for c in candidatos:
        if c and Path(c).exists():
            return Path(c)
    return None


def main() -> None:
    os.chdir(RAIZ)
    icono = RAIZ / "icono.ico"
    if not icono.exists():
        crear_icono(icono)

    binarios = [f"--add-binary={herramienta(n)}{os.pathsep}bin" for n in ("ffmpeg", "ffprobe", "deno")]

    import PyInstaller.__main__

    PyInstaller.__main__.run([
        "app.py",
        f"--name={NOMBRE}",
        "--windowed",
        "--noconfirm",
        "--clean",
        f"--icon={icono}",
        f"--add-data={icono}{os.pathsep}.",
        "--collect-all=yt_dlp_ejs",
        "--collect-data=ytmusicapi",  # textos e idiomas que ytmusicapi carga al iniciar
        *binarios,
    ])
    print(f"\nApp lista en: dist\\{NOMBRE}\\{NOMBRE}.exe")

    iscc = buscar_iscc()
    if not iscc:
        print("\nNo encontré Inno Setup, así que no se generó el instalador.")
        print("Instálalo con:  winget install JRSoftware.InnoSetup  y vuelve a correr build.py")
        return
    subprocess.run([str(iscc), "instalador.iss"], check=True)
    print(f"\nInstalador listo en: instalador\\{NOMBRE}-Setup.exe")


if __name__ == "__main__":
    main()
