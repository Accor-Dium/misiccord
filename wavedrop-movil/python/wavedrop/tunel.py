"""Jams por internet: un túnel rápido de Cloudflare (cloudflared) apunta una dirección pública
https://algo-al-azar.trycloudflare.com al servidor del jam de esta máquina.

No hace falta cuenta ni abrir puertos en el módem; la dirección cambia cada vez que se abre.
cloudflared se baja una sola vez del GitHub oficial de Cloudflare y se guarda en la carpeta de datos.
"""
import atexit
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

from . import plataforma

URL_DESCARGA = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
_PATRON = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
_actual: dict = {"proceso": None, "url": None, "puerto": None}
_candado = threading.Lock()
atexit.register(lambda: cerrar())  # que el túnel no se quede abierto si el servicio se cierra


_trabajo = None  # Job Object de Windows: si el servicio muere (la app lo cierra a la fuerza), muere cloudflared


def _atar_al_servicio(proceso: subprocess.Popen) -> None:
    global _trabajo
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.OpenProcess.restype = wintypes.HANDLE
        if _trabajo is None:
            class Limites(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD)]

            class Extendidos(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", Limites), ("IoInfo", ctypes.c_uint64 * 6),
                            ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

            trabajo = k32.CreateJobObjectW(None, None)
            info = Extendidos()
            info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            k32.SetInformationJobObject(trabajo, 9, ctypes.byref(info), ctypes.sizeof(info))  # ExtendedLimitInformation
            _trabajo = trabajo
        manija = k32.OpenProcess(0x0001 | 0x0100, False, proceso.pid)  # PROCESS_TERMINATE | PROCESS_SET_QUOTA
        k32.AssignProcessToJobObject(_trabajo, manija)
        k32.CloseHandle(manija)
    except Exception:
        pass  # sin esto solo se pierde la limpieza automática


def disponible() -> bool:
    """Windows (se baja cloudflared la primera vez) o Android (viaja en el APK, compilado para Android)."""
    if plataforma.es_android():
        return plataforma.lib_nativa("cloudflared") is not None
    return sys.platform == "win32"


def _ejecutable(al_progreso=None) -> Path:
    if plataforma.es_android():
        exe = plataforma.lib_nativa("cloudflared")
        if not exe:
            raise RuntimeError("Esta versión no trae cloudflared para Android")
        return exe
    propio = plataforma.herramienta("cloudflared")
    if propio:
        return Path(propio)
    destino = plataforma.carpeta_datos() / "bin" / "cloudflared.exe"
    if destino.exists() and destino.stat().st_size > 1_000_000:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".descargando")
    with requests.get(URL_DESCARGA, stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        bajado = 0
        with open(temporal, "wb") as f:
            for bloque in r.iter_content(256 * 1024):
                f.write(bloque)
                bajado += len(bloque)
                if al_progreso and total:
                    al_progreso(int(bajado * 100 / total))
    temporal.replace(destino)
    return destino


def abrir(puerto: int, al_progreso=None, espera: float = 40) -> str:
    """Abre (o reutiliza) el túnel hacia 127.0.0.1:puerto y devuelve la dirección pública."""
    with _candado:
        p = _actual["proceso"]
        if p and p.poll() is None and _actual["puerto"] == puerto and _actual["url"]:
            return _actual["url"]
        cerrar()
        exe = _ejecutable(al_progreso)
        entorno = dict(os.environ)
        if plataforma.es_android():
            # cloudflared quiere un HOME donde escribir; en Android la app solo puede en su carpeta
            entorno["HOME"] = str(plataforma.carpeta_cache())
        proceso = subprocess.Popen(
            [str(exe), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{puerto}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", env=entorno,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _atar_al_servicio(proceso)
        _actual.update(proceso=proceso, puerto=puerto, url=None)

        registrada = threading.Event()  # ya hay conexión con la red de Cloudflare
        lineas: list[str] = []

        def leer():
            for linea in proceso.stderr:  # cloudflared escribe su registro en stderr
                lineas.append(linea.strip())
                m = _PATRON.search(linea)
                if m and not _actual["url"]:
                    _actual["url"] = m.group(0)
                if "Registered tunnel connection" in linea:
                    registrada.set()
            registrada.set()  # se cerró el proceso

        threading.Thread(target=leer, daemon=True).start()
        registrada.wait(espera)
        if not _actual["url"] or proceso.poll() is not None:
            cerrar()
            ultima = next((l for l in reversed(lineas) if "ERR" in l), lineas[-1] if lineas else "")
            raise RuntimeError(f"No se pudo abrir el jam a internet. {ultima[-160:]}".strip())
        # Cloudflare tarda unos segundos en publicar el nombre nuevo. Se pregunta por DNS sobre HTTPS:
        # si se le pregunta antes al DNS de Windows, guarda el "no existe" por varios minutos.
        _esperar_dns(_actual["url"])
        return _actual["url"]


def _esperar_dns(url: str, segundos: float = 30) -> bool:
    nombre = url.removeprefix("https://")
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            r = requests.get("https://cloudflare-dns.com/dns-query", params={"name": nombre, "type": "A"},
                             headers={"Accept": "application/dns-json"}, timeout=5)
            if r.ok and r.json().get("Answer"):
                time.sleep(2)  # margen para que llegue a los demás servidores de Cloudflare
                return True
        except (requests.RequestException, ValueError):
            pass
        time.sleep(1.5)
    return False


def cerrar() -> None:
    p = _actual["proceso"]
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
    _actual.update(proceso=None, url=None, puerto=None)


def url() -> str | None:
    p = _actual["proceso"]
    return _actual["url"] if p and p.poll() is None else None
