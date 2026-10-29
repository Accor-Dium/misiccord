"""Lo que cambia entre Windows y Android: carpetas, ffmpeg y el intérprete de JavaScript.

La app (Kotlin en Android, el servicio en Windows) llama a configurar() al arrancar.
"""
import os
import shutil
import sys
from pathlib import Path

_config = {
    "datos": None,    # base de datos, ajustes, recomendaciones
    "musica": None,   # carpeta de descargas
    "cache": None,    # vistas previas, portadas extraídas, caché de yt-dlp
    "libs": None,     # Android: carpeta de librerías nativas (ahí está libqjs.so)
}


def configurar(datos: str, musica: str, cache: str, libs: str | None = None) -> None:
    for clave, valor in (("datos", datos), ("musica", musica), ("cache", cache)):
        Path(valor).mkdir(parents=True, exist_ok=True)
        _config[clave] = valor
    _config["libs"] = libs


def es_android() -> bool:
    return hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ


def _carpeta(clave: str, por_defecto: Path) -> Path:
    ruta = Path(_config[clave]) if _config[clave] else por_defecto
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def carpeta_datos() -> Path:
    return _carpeta("datos", Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WaveDrop")


def carpeta_musica() -> Path:
    return _carpeta("musica", Path.home() / "Music" / "Misiccord")


def carpeta_cache() -> Path:
    return _carpeta("cache", carpeta_datos() / "cache")


def herramienta(nombre: str) -> str | None:
    """ffmpeg, ffprobe o deno: junto al ejecutable empaquetado (bin/) o en el PATH."""
    if es_android():
        return None
    base = Path(getattr(sys, "_MEIPASS", "")) / "bin" if getattr(sys, "frozen", False) else None
    if base and (base / f"{nombre}.exe").exists():
        return str(base / f"{nombre}.exe")
    return shutil.which(nombre)


def hay_ffmpeg() -> bool:
    return bool(herramienta("ffmpeg") and herramienta("ffprobe"))


def archivo_nuevo(ruta: Path) -> None:
    """Android: avisa al sistema de la canción nueva para que aparezca en las demás apps de música."""
    if not es_android():
        return
    try:
        from java import jarray, jclass
        contexto = jclass("com.chaquo.python.Python").getPlatform().getApplication()
        rutas = jarray(jclass("java.lang.String"))([str(ruta)])
        jclass("android.media.MediaScannerConnection").scanFile(contexto, rutas, None, None)
    except Exception:
        pass


def lib_nativa(nombre: str) -> Path | None:
    """Android: un ejecutable que viaja en el APK como lib<nombre>.so (qjs, cloudflared)."""
    if es_android() and _config["libs"]:
        ruta = Path(_config["libs"]) / f"lib{nombre}.so"
        if ruta.exists():
            return ruta
    return None


def js_runtimes() -> dict:
    """Intérprete de JavaScript para los retos de YouTube: QuickJS en Android, deno en Windows."""
    if es_android() and _config["libs"]:
        qjs = Path(_config["libs"]) / "libqjs.so"
        if qjs.exists():
            return {"quickjs": {"path": str(qjs)}}
        return {}
    deno = herramienta("deno")
    return {"deno": {"path": deno}} if deno else {}
