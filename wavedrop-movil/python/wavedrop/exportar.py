"""Sacar canciones de la app en la PC: copiarlas a una USB o carpeta, o al portapapeles para pegarlas
en WhatsApp o Telegram de escritorio. (En Android se comparten con el menú del sistema, desde Kotlin.)
"""
import os
import shutil
import string
import subprocess
import sys
from pathlib import Path

_PROHIBIDOS = '<>:"/\\|?*'


def _limpio(nombre: str) -> str:
    limpio = "".join("_" if ch in _PROHIBIDOS or ord(ch) < 32 else ch for ch in nombre).strip(" .")
    return limpio[:80] or "Misiccord"


def destinos() -> list[dict]:
    """Memorias USB y discos externos conectados (Windows). Los discos del sistema no salen."""
    if sys.platform != "win32":
        return []
    import ctypes
    k32 = ctypes.windll.kernel32
    sistema = os.environ.get("SystemDrive", "C:").upper()
    res = []
    mascara = k32.GetLogicalDrives()
    for i, letra in enumerate(string.ascii_uppercase):
        if not mascara & (1 << i) or f"{letra}:" == sistema:
            continue
        raiz = f"{letra}:\\"
        tipo = k32.GetDriveTypeW(raiz)
        if tipo != 2:  # DRIVE_REMOVABLE (memorias, tarjetas). Los discos fijos y de red no
            continue
        nombre = ctypes.create_unicode_buffer(261)
        if not k32.GetVolumeInformationW(raiz, nombre, 261, None, None, None, None, 0):
            continue  # lector sin tarjeta
        try:
            libre = shutil.disk_usage(raiz).free
        except OSError:
            continue
        res.append({"ruta": raiz, "nombre": nombre.value or "USB", "letra": letra, "libre_gb": round(libre / 1e9, 1)})
    return res


def copiar(grupos: list[dict], destino: str, avance=None) -> dict:
    """grupos: [{"carpeta": "Álbum o playlist" | "", "rutas": [...], "lista": bool}]. Todo va a destino/Misiccord/…

    Con "lista" (playlists) se escribe también un .m3u8 para abrirla igual en otro reproductor.
    Lo que ya está copiado (mismo nombre y tamaño) no se vuelve a copiar.
    """
    base = Path(destino) / "Misiccord"
    total = sum(len(g["rutas"]) for g in grupos)
    hechas, fallidas = 0, []
    for g in grupos:
        carpeta = base / _limpio(g["carpeta"]) if g.get("carpeta") else base
        carpeta.mkdir(parents=True, exist_ok=True)
        nombres = []
        for ruta in g["rutas"]:
            origen = Path(ruta)
            final = carpeta / origen.name
            try:
                if not (final.exists() and final.stat().st_size == origen.stat().st_size):
                    shutil.copyfile(origen, final)
                nombres.append(final.name)
            except OSError as e:
                fallidas.append({"ruta": ruta, "error": e.strerror or str(e)})
            hechas += 1
            if avance:
                avance(hechas, total)
        if g.get("lista") and nombres:
            (carpeta / f"{_limpio(g['carpeta'])}.m3u8").write_text(
                "#EXTM3U\n" + "\n".join(nombres) + "\n", encoding="utf-8")
    return {"copiadas": hechas - len(fallidas), "fallidas": fallidas, "carpeta": str(base)}


def al_portapapeles(rutas: list[str]) -> None:
    """Pone los archivos en el portapapeles de Windows (como "Copiar" en el Explorador): se pegan en WhatsApp,
    Telegram, Discord o una carpeta con Ctrl+V."""
    if sys.platform != "win32":
        raise RuntimeError("Solo en Windows")
    import ctypes
    from ctypes import wintypes

    # DROPFILES + lista de rutas separadas por \0 y terminada en \0\0 (UTF-16)
    lista = ("\0".join(str(Path(r).resolve()) for r in rutas) + "\0\0").encode("utf-16-le")
    cabecera = (20).to_bytes(4, "little") + bytes(8) + bytes(4) + (1).to_bytes(4, "little")  # pFiles, pt, fNC, fWide
    datos = cabecera + lista

    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    memoria = k32.GlobalAlloc(0x0042, len(datos))  # GHND: movible y en ceros
    ctypes.memmove(k32.GlobalLock(memoria), datos, len(datos))
    k32.GlobalUnlock(memoria)
    if not u32.OpenClipboard(None):
        raise RuntimeError("El portapapeles está ocupado, intenta otra vez")
    try:
        u32.EmptyClipboard()
        if not u32.SetClipboardData(15, memoria):  # CF_HDROP
            raise RuntimeError("No se pudo copiar al portapapeles")
    finally:
        u32.CloseClipboard()


def mostrar(ruta: str) -> None:
    """Abre la carpeta con el archivo marcado (Windows), para arrastrarlo a donde quieras."""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(Path(ruta))])
    else:
        subprocess.Popen(["xdg-open", str(Path(ruta).parent)])
