"""Lógica de descarga compartida por la app gráfica y el script de consola.

Fuentes:
- YouTube, YouTube Music, SoundCloud y cualquier otro sitio que soporte yt-dlp: se descargan directo.
- Spotify: su audio está protegido, así que se lee la lista de canciones (título, artista)
  y cada una se busca y descarga desde YouTube Music.
"""
import json
import re
import shutil
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import requests
import yt_dlp
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import sanitize_filename

# Primer artista de la canción; si no se conoce, usa el nombre del canal.
ARTISTA = "%(artists.0,artist,uploader|Desconocido)s"

# En el ejecutable empaquetado, ffmpeg/ffprobe/deno viajan en la carpeta "bin".
_BIN = Path(getattr(sys, "_MEIPASS", "")) / "bin" if getattr(sys, "frozen", False) else None


def ruta_herramienta(nombre: str) -> str | None:
    if _BIN:
        exe = _BIN / f"{nombre}.exe"
        if exe.exists():
            return str(exe)
    return shutil.which(nombre)


def ffmpeg_disponible() -> bool:
    return bool(ruta_herramienta("ffmpeg") and ruta_herramienta("ffprobe"))


# ---------- Fuentes ----------

FUENTES = {
    "spotify": "Spotify",
    "ytmusic": "YT Music",
    "youtube": "YouTube",
    "soundcloud": "SoundCloud",
    "otro": "Otro sitio",
}


def detectar_fuente(url: str) -> str:
    host = urllib.parse.urlparse(url.strip()).netloc.lower()
    if "spotify.com" in host:
        return "spotify"
    if "music.youtube.com" in host:
        return "ytmusic"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "soundcloud.com" in host:
        return "soundcloud"
    return "otro"


# ---------- Formatos ----------

@dataclass(frozen=True)
class Formato:
    codec: str  # mp3, m4a, opus
    calidad: str  # kbps para mp3/m4a; "0" = sin recomprimir
    etiqueta: str

    @property
    def corto(self) -> str:
        return f"{self.codec.upper()} · {self.calidad} kbps" if self.calidad != "0" else f"{self.codec.upper()} · original"


FORMATOS = [
    Formato("mp3", "320", "MP3 · 320 kbps"),
    Formato("mp3", "256", "MP3 · 256 kbps"),
    Formato("mp3", "192", "MP3 · 192 kbps"),
    Formato("mp3", "128", "MP3 · 128 kbps"),
    Formato("m4a", "256", "M4A / AAC · 256 kbps"),
    Formato("opus", "0", "Opus · original (sin recomprimir)"),
]
EXTENSIONES_AUDIO = {".mp3", ".m4a", ".opus"}


# ---------- Lectura de colecciones ----------

@dataclass
class Entrada:
    indice: int
    id: str
    titulo: str
    artista: str
    url: str  # página del video, o búsqueda en YouTube Music para Spotify
    fuente: str
    duracion: float | None = None
    miniatura: str | None = None
    album: str | None = None
    clave: str = ""  # identificador en descargados.txt

    @property
    def por_busqueda(self) -> bool:
        return self.fuente == "spotify"


@dataclass
class Coleccion:
    titulo: str
    fuente: str
    portada: str | None
    entradas: list[Entrada] = field(default_factory=list)


class _Logger:
    """Recoge los mensajes de yt-dlp en vez de imprimirlos (la app no tiene consola)."""

    def __init__(self):
        self.ultimo_error = ""

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.ultimo_error = msg.removeprefix("ERROR: ")


def _opciones_base(logger: _Logger) -> dict:
    opciones = {"quiet": True, "no_warnings": True, "noprogress": True, "logger": logger}
    deno = ruta_herramienta("deno")
    if deno:
        opciones["js_runtimes"] = {"deno": {"path": deno}}
    ffmpeg = ruta_herramienta("ffmpeg")
    if ffmpeg:
        opciones["ffmpeg_location"] = str(Path(ffmpeg).parent)
    return opciones


def _sin_topic(nombre: str | None) -> str:
    return re.sub(r" - Topic$", "", nombre or "")


def _mejor_miniatura(thumbs: list | None) -> str | None:
    """La miniatura más chica que siga viéndose bien (para la tabla)."""
    if not thumbs:
        return None
    con_tamano = [t for t in thumbs if t.get("width") and t["width"] >= 120]
    if con_tamano:
        return min(con_tamano, key=lambda t: t["width"])["url"]
    return thumbs[-1].get("url")


def obtener_coleccion(url: str) -> Coleccion:
    """Lee la lista de canciones sin descargar nada."""
    fuente = detectar_fuente(url)
    if fuente == "spotify":
        return _leer_spotify(url)
    return _leer_ytdlp(url, fuente)


def _leer_ytdlp(url: str, fuente: str) -> Coleccion:
    logger = _Logger()
    opciones = _opciones_base(logger) | {"extract_flat": "in_playlist", "noplaylist": False}
    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError(logger.ultimo_error or "No se pudo leer el link")

    if info.get("_type") != "playlist":  # un solo video
        info = {"title": info.get("title"), "thumbnails": info.get("thumbnails"), "entries": [info]}

    col = Coleccion(info.get("title") or "Playlist", fuente, _mejor_miniatura(info.get("thumbnails")))
    for i, e in enumerate(info.get("entries") or [], start=1):
        if not e:
            continue
        ie = (e.get("ie_key") or e.get("extractor_key") or "").lower()
        id_ = e.get("id") or ""
        col.entradas.append(Entrada(
            indice=i,
            id=id_,
            titulo=e.get("title") or e.get("url") or id_,
            artista=_sin_topic(e.get("artist") or e.get("channel") or e.get("uploader")),
            url=e.get("webpage_url") or e.get("url") or f"https://www.youtube.com/watch?v={id_}",
            fuente=fuente,
            duracion=e.get("duration"),
            miniatura=_mejor_miniatura(e.get("thumbnails")) or e.get("thumbnail"),
            clave=f"{ie} {id_}" if ie and id_ else "",
        ))
    return col


def _leer_spotify(url: str) -> Coleccion:
    m = re.search(r"spotify\.com/(?:intl-[a-z]+/)?(?:embed/)?(playlist|album|track)/([A-Za-z0-9]+)", url)
    if not m:
        raise RuntimeError("Link de Spotify no reconocido. Usa un link de playlist, álbum o canción.")
    tipo, id_ = m.groups()
    r = requests.get(f"https://open.spotify.com/embed/{tipo}/{id_}", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    datos = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', r.text, re.S)
    if not datos:
        raise RuntimeError("Spotify no devolvió la lista (¿la playlist es privada?)")
    ent = json.loads(datos.group(1))["props"]["pageProps"]["state"]["data"]["entity"]

    portadas = (ent.get("coverArt") or {}).get("sources") or []
    portada = portadas[0]["url"] if portadas else None
    nombre = ent.get("name") or ent.get("title") or "Spotify"
    album = nombre if tipo == "album" else None

    if tipo == "track":
        artistas = ", ".join(a["name"] for a in ent.get("artists") or []) or ent.get("subtitle", "")
        pistas = [{"uri": ent.get("uri", f"spotify:track:{id_}"), "title": nombre, "subtitle": artistas,
                   "duration": ent.get("duration")}]
    else:
        pistas = ent.get("trackList") or []

    col = Coleccion(nombre, "spotify", portada)
    for i, p in enumerate(pistas, start=1):
        pista_id = p.get("uri", "").rsplit(":", 1)[-1]
        artista = (p.get("subtitle") or "").replace(" ", " ")
        principal = artista.split(",")[0].strip()
        busqueda = f"{principal} {p.get('title', '')}"
        col.entradas.append(Entrada(
            indice=i,
            id=pista_id,
            titulo=p.get("title") or pista_id,
            artista=artista,
            url=f"https://music.youtube.com/search?q={urllib.parse.quote(busqueda)}#songs",
            fuente="spotify",
            duracion=(p.get("duration") or 0) / 1000 or None,
            miniatura=portada,
            album=album,
            clave=f"spotify {pista_id}",
        ))
    return col


# ---------- Descarga ----------

class Cancelado(Exception):
    pass


@dataclass
class Resultado:
    ruta: str
    tamano: int
    titulo: str
    artista: str
    miniatura: str | None


class _FijarMetadatos(PostProcessor):
    """Antes de descargar: ajusta título/artista (los de Spotify mandan) y limpia " - Topic"."""

    def __init__(self, entrada: Entrada):
        super().__init__()
        self.entrada = entrada

    def run(self, info):
        if info.get("uploader"):
            info["uploader"] = _sin_topic(info["uploader"])
        if self.entrada.por_busqueda:
            artistas = [a.strip() for a in self.entrada.artista.split(",") if a.strip()]
            info["title"] = info["track"] = self.entrada.titulo
            info["artists"] = artistas or [info.get("uploader") or "Desconocido"]
            info["artist"] = ", ".join(info["artists"])
            if self.entrada.album:
                info["album"] = self.entrada.album
        return [], info


ProgresoCb = Callable[[str, int, float | None, float | None], None]  # estado, %, bytes/s, eta


class Descargador:
    def __init__(self, carpeta: str, formato: Formato, por_playlist: bool, titulo_coleccion: str):
        self.carpeta = Path(carpeta)
        self.formato = formato
        self.por_playlist = por_playlist
        self.titulo_coleccion = titulo_coleccion
        self.archivo_registro = self.carpeta / "descargados.txt"

    def ya_descargada(self, entrada: Entrada) -> bool:
        if not entrada.clave:
            return False
        try:
            lineas = self.archivo_registro.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return False
        return entrada.clave in lineas

    def _registrar(self, entrada: Entrada) -> None:
        # yt-dlp anota el id del video; para Spotify anotamos además el id de la pista
        if entrada.por_busqueda and entrada.clave:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            with open(self.archivo_registro, "a", encoding="utf-8") as f:
                f.write(entrada.clave + "\n")

    def _plantilla(self, entrada: Entrada) -> str:
        if self.por_playlist:
            # El título va fijo en la ruta: se limpian caracteres y se escapa el %
            carpeta = sanitize_filename(self.titulo_coleccion).replace("%", "%%")
            return f"{carpeta}/{entrada.indice:03d} - %(title)s.%(ext)s"
        return f"{ARTISTA}/%(title)s.%(ext)s"

    def _postprocesadores(self) -> list[dict]:
        f = self.formato
        return [
            {"key": "FFmpegExtractAudio", "preferredcodec": f.codec, "preferredquality": f.calidad},
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ]

    def _formato_origen(self) -> str:
        return {
            "m4a": "bestaudio[ext=m4a]/bestaudio/best",
            "opus": "bestaudio[acodec=opus]/bestaudio/best",
        }.get(self.formato.codec, "bestaudio/best")

    def descargar(self, entrada: Entrada, al_progreso: ProgresoCb, cancelado: Callable[[], bool]) -> Resultado:
        """Descarga una canción. Lanza Cancelado o RuntimeError si no se pudo."""
        logger = _Logger()

        def progreso(d):
            if cancelado():
                raise Cancelado()
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                pct = int(d.get("downloaded_bytes", 0) * 100 / total) if total else 0
                al_progreso("Descargando", min(pct, 100), d.get("speed"), d.get("eta"))

        def postproceso(d):
            if d["status"] == "started" and d["postprocessor"] == "ExtractAudio":
                al_progreso("Convirtiendo", 100, None, None)

        opciones = _opciones_base(logger) | {
            "format": self._formato_origen(),
            "outtmpl": str(self.carpeta / self._plantilla(entrada)),
            "download_archive": str(self.archivo_registro),
            "writethumbnail": True,
            "progress_hooks": [progreso],
            "postprocessor_hooks": [postproceso],
            "postprocessors": self._postprocesadores(),
        }
        if entrada.por_busqueda:
            opciones["playlist_items"] = "1"  # el primer resultado de la búsqueda
        else:
            opciones["noplaylist"] = True

        al_progreso("Buscando en YT Music" if entrada.por_busqueda else "Descargando", 0, None, None)
        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                ydl.add_post_processor(_FijarMetadatos(entrada), when="pre_process")
                info = ydl.extract_info(entrada.url, download=True)
        except Cancelado:
            raise
        except Exception as e:
            if cancelado():
                raise Cancelado() from e
            raise RuntimeError(logger.ultimo_error or str(e)) from e

        if info and info.get("_type") == "playlist":  # resultado de búsqueda
            info = next((e for e in info.get("entries") or [] if e), None)
            if info is None:
                raise RuntimeError("No se encontró en YouTube Music")
        if not info or not info.get("requested_downloads"):
            raise RuntimeError(logger.ultimo_error or "No se descargó nada")

        ruta = info["requested_downloads"][0]["filepath"]
        self._registrar(entrada)
        return Resultado(
            ruta=ruta,
            tamano=Path(ruta).stat().st_size if Path(ruta).exists() else 0,
            titulo=info.get("title") or entrada.titulo,
            artista=info.get("artist") or _sin_topic(info.get("uploader")) or entrada.artista,
            miniatura=entrada.miniatura or _mejor_miniatura(info.get("thumbnails")),
        )
