"""Reproducir canciones de YouTube Music mientras se descargan (streaming).

Antes la vista previa se bajaba completa y hasta entonces sonaba. Ahora:
  1. yt-dlp solo averigua la dirección directa del audio (un par de segundos).
  2. El reproductor pide http://127.0.0.1:<puerto>/flujo/<id> a este servidor local, que va trayendo
     el audio de YouTube por pedazos y se los pasa al reproductor conforme llegan: suena con el primero.
  3. Si la canción se escucha completa de corrido, lo que pasó por aquí se guarda en la caché de previas
     y la próxima vez suena al instante sin internet.

El reproductor pide rangos (Range) para adelantar; se reenvían tal cual a YouTube.
"""
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
import yt_dlp

from . import descargas as nucleo
from . import explorar

VIGENCIA = 4 * 3600  # las direcciones de YouTube caducan a las ~6 h
_info: dict[str, dict] = {}  # video_id -> {url, headers, tam, ext, tipo, hora}
_en_curso: dict[str, threading.Event] = {}  # video_id que yt-dlp está resolviendo ahorita
_candado = threading.Lock()
_servidor: dict = {"puerto": None, "token": secrets.token_urlsafe(12)}
PREFIJO_VIDEO = "v:"  # en _info/_en_curso el video de una canción va aparte de su audio
# Precarga: lo que está en pantalla se resuelve antes de que lo toques (pocos a la vez, la más reciente primero)
_pendientes: list[str] = []
_hay_pendientes = threading.Condition()


def _resolver(video_id: str, forzar: bool = False) -> dict:
    while True:
        with _candado:
            i = _info.get(video_id)
            if i and not forzar and time.time() - i["hora"] < VIGENCIA:
                return i
            evento = _en_curso.get(video_id)
            if evento is None:
                # Nadie la está resolviendo: me toca a mí
                _en_curso[video_id] = threading.Event()
                break
        evento.wait(60)  # ya la está resolviendo la precarga: se espera ese mismo resultado
        forzar = False
        if video_id not in _info:
            continue
    try:
        return _extraer(video_id)
    finally:
        with _candado:
            _en_curso.pop(video_id).set()


def _extraer(clave: str) -> dict:
    inicio = time.time()
    video_id = clave.removeprefix(PREFIJO_VIDEO)
    if clave.startswith(PREFIJO_VIDEO):
        return _extraer_video(clave, video_id)
    url = f"https://music.youtube.com/watch?v={video_id}"
    base = {"format": "bestaudio[ext=m4a]/bestaudio", "noplaylist": True}
    # Camino rápido: el cliente de la app de YouTube Music da el audio sin correr el JavaScript del
    # reproductor (en el cel eso lo hace QuickJS y tarda ~10 s por canción). Si no sirve, el camino normal.
    info = None
    try:
        rapido = nucleo._opciones_base(nucleo._Logger()) | base | {
            "extractor_args": {"youtube": {"player_client": ["android_music"]}}, "js_runtimes": {}}
        with yt_dlp.YoutubeDL(rapido) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        info = None
    if not info or not (info.get("requested_formats") or [info])[0].get("url"):
        logger = nucleo._Logger()
        try:
            info = nucleo.extraer(nucleo._opciones_base(logger) | base, url, False, logger)
        except Exception as e:
            raise RuntimeError(logger.ultimo_error or str(e)) from e
    formato = (info.get("requested_formats") or [info])[0]
    if not formato.get("url"):
        raise RuntimeError("YouTube no dio una dirección para esta canción")
    ext = formato.get("ext") or "m4a"
    i = {"url": formato["url"], "headers": dict(formato.get("http_headers") or {}),
         "tam": formato.get("filesize") or formato.get("filesize_approx"), "ext": ext,
         "tipo": "audio/mp4" if ext in ("m4a", "mp4") else f"audio/{ext}", "hora": time.time()}
    with _candado:
        _info[video_id] = i
    print(f"[flujo] {video_id} resuelto en {time.time() - inicio:.1f} s", flush=True)
    return i


def _extraer_video(clave: str, video_id: str) -> dict:
    """Solo la imagen del clip (el sonido ya viene del audio), sin caché.

    El cliente "android" da un mp4 de 360p que se puede pedir por rangos sin token ni JavaScript (rápido, también
    en el cel). Los clientes que dan más calidad (tv, web) necesitan un token de YouTube y responden 403 al pedirlo
    por rangos: por eso cada candidato se prueba antes de usarlo.
    """
    inicio = time.time()
    url = f"https://www.youtube.com/watch?v={video_id}"
    base = {"format": "best[height<=720][ext=mp4]/bestvideo[height<=720][ext=mp4]/best[height<=720]", "noplaylist": True}
    candidatos = []
    try:
        rapido = nucleo._opciones_base(nucleo._Logger()) | base | {
            "extractor_args": {"youtube": {"player_client": ["android"]}}, "js_runtimes": {}}
        with yt_dlp.YoutubeDL(rapido) as ydl:
            candidatos.append(ydl.extract_info(url, download=False))
    except Exception:
        pass
    logger = nucleo._Logger()
    for info in candidatos + [None]:
        if info is None:  # camino normal de yt-dlp, por si "android" ya no sirve
            try:
                info = nucleo.extraer(nucleo._opciones_base(logger) | base, url, False, logger)
            except Exception as e:
                raise RuntimeError(logger.ultimo_error or str(e)) from e
        formato = (info.get("requested_formats") or [info])[0] if info else {}
        if not formato.get("url"):
            continue
        ext = formato.get("ext") or "mp4"
        i = {"url": formato["url"], "headers": dict(formato.get("http_headers") or {}),
             "tam": formato.get("filesize") or formato.get("filesize_approx"), "ext": ext,
             "tipo": "video/webm" if ext == "webm" else "video/mp4", "hora": time.time()}
        if _responde(i):
            with _candado:
                _info[clave] = i
            print(f"[flujo] video {video_id} resuelto en {time.time() - inicio:.1f} s", flush=True)
            return i
    raise RuntimeError("YouTube no deja transmitir el video de esta canción")


def _responde(i: dict) -> bool:
    """¿YouTube entrega esta dirección por rangos? (pide 1 byte)"""
    try:
        r = requests.get(i["url"], headers={**i["headers"], "Range": "bytes=0-0"}, stream=True, timeout=(8, 15))
        r.close()
        return r.status_code in (200, 206)
    except requests.RequestException:
        return False


def _trabajador_precarga() -> None:
    while True:
        with _hay_pendientes:
            while not _pendientes:
                _hay_pendientes.wait()
            video_id = _pendientes.pop()
        try:
            _resolver(video_id)
        except Exception:
            pass  # si falla, al tocarla se vuelve a intentar (y se ve el error)


def precargar(ids: list[str]) -> None:
    """Resuelve en segundo plano las canciones que el usuario está viendo para que suenen al tocarlas."""
    with _hay_pendientes:
        if not _hilos_precarga:
            for k in range(2):
                hilo = threading.Thread(target=_trabajador_precarga, name=f"precarga-{k}", daemon=True)
                hilo.start()
                _hilos_precarga.append(hilo)
        nuevos = [v for v in ids if v and v not in _info and v not in _en_curso and v not in _pendientes]
        # Lo último que se pidió es lo que está en pantalla ahora: va primero; nunca más de 12 en espera
        _pendientes[:] = (_pendientes + list(reversed(nuevos)))[-12:]
        _hay_pendientes.notify_all()


_hilos_precarga: list[threading.Thread] = []


def _pedir(video_id: str, rango: str):
    for intento in range(2):
        i = _resolver(video_id, forzar=intento > 0)
        r = requests.get(i["url"], headers={**i["headers"], "Range": rango}, stream=True, timeout=(8, 30))
        if r.status_code in (200, 206):
            return i, r
        r.close()  # 403/410: la dirección caducó; se pide otra
    raise RuntimeError(f"YouTube respondió {r.status_code}")


def servir(manejador: BaseHTTPRequestHandler, video_id: str, rango: str | None, cabeceras=None,
           video: bool = False) -> None:
    """Pasa el audio de YouTube a quien lo pidió (el reproductor local o un invitado del jam) conforme llega.

    cabeceras: función que agrega las suyas a la respuesta (el jam pone las de CORS).
    video: manda la imagen del clip en vez del audio (no se guarda en la caché de previas).
    """
    rango = rango or "bytes=0-"
    try:
        i, r = _pedir((PREFIJO_VIDEO if video else "") + video_id, rango)
    except Exception as e:
        manejador.send_error(502, str(e)[:100])
        return
    manejador.send_response(r.status_code)
    if cabeceras:
        cabeceras()
    manejador.send_header("Content-Type", i["tipo"])
    manejador.send_header("Accept-Ranges", "bytes")
    for cabecera in ("Content-Length", "Content-Range"):
        if r.headers.get(cabecera):
            manejador.send_header(cabecera, r.headers[cabecera])
    manejador.send_header("Cache-Control", "no-store")
    manejador.end_headers()

    # Si es la canción entera desde el principio, se va guardando para la caché de previas
    total = r.headers.get("Content-Range", "").rsplit("/", 1)[-1]
    completa = rango.strip() == "bytes=0-" and not video
    final = explorar.carpeta_cache() / f"{video_id}.{i['ext']}"
    temporal = final.with_name(f"{final.name}.{secrets.token_hex(3)}.parte") if completa else None
    archivo = open(temporal, "wb") if temporal else None
    recibido = 0
    inicio = time.time()
    try:
        for bloque in r.iter_content(64 * 1024):
            manejador.wfile.write(bloque)
            manejador.wfile.flush()  # cada pedazo sale en cuanto llega: el reproductor arranca con los primeros
            if archivo:
                archivo.write(bloque)
            if not recibido:
                print(f"[flujo] {video_id} {rango}: primer pedazo enviado a los {time.time() - inicio:.1f} s", flush=True)
            recibido += len(bloque)
        print(f"[flujo] {video_id} {rango}: {recibido / 1e6:.1f} MB enviados en {time.time() - inicio:.1f} s", flush=True)
    except (ConnectionError, TimeoutError):
        pass  # el reproductor cerró la conexión (adelantaste o cambiaste de canción)
    finally:
        r.close()
        if archivo:
            archivo.close()
            esperado = int(total) if total.isdigit() else int(r.headers.get("Content-Length") or 0)
            if esperado and recibido == esperado:
                temporal.replace(final)  # {id}.m4a: explorar.previa ya la encuentra
                _recortar_cache()
            else:
                temporal.unlink(missing_ok=True)


class _Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        partes = urllib.parse.urlparse(self.path)
        consulta = urllib.parse.parse_qs(partes.query)
        if not partes.path.startswith(("/flujo/", "/video/")) or consulta.get("t", [""])[0] != _servidor["token"]:
            self.send_error(404)
            return
        # CORS: el ecualizador (Web Audio) deja en silencio el audio de otro origen que no lo permita
        servir(self, partes.path.split("/")[2], self.headers.get("Range"),
               cabeceras=lambda: self.send_header("Access-Control-Allow-Origin", "*"), video=partes.path.startswith("/video/"))


def _recortar_cache(maximo: int = 25) -> None:
    viejas = sorted((p for p in explorar.carpeta_cache().iterdir() if p.suffix not in (".parte", ".lrc")),
                    key=lambda p: p.stat().st_mtime, reverse=True)[maximo:]
    for p in viejas:
        p.unlink(missing_ok=True)


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # cortes normales del reproductor al adelantar o cambiar de canción


def _arrancar() -> int:
    with _candado:
        if _servidor["puerto"]:
            return _servidor["puerto"]
        servidor = _Servidor(("127.0.0.1", 0), _Manejador)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        _servidor["puerto"] = servidor.server_address[1]
        return _servidor["puerto"]


def url(video_id: str, video: bool = False) -> str:
    """Dirección local para reproducir la canción (o su clip) mientras llega; resuelve la de YouTube antes."""
    _resolver((PREFIJO_VIDEO if video else "") + video_id)
    return f"http://127.0.0.1:{_arrancar()}/{'video' if video else 'flujo'}/{video_id}?t={_servidor['token']}"
