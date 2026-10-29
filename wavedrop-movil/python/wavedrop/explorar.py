"""Buscar música en YouTube Music y armar recomendaciones (con ytmusicapi, sin cuenta).

- buscar_canciones / buscar_albumes: resultados para la página "Buscar".
- previa: baja el audio original (sin convertir) a una caché temporal para escucharlo antes de descargar.
- recomendaciones: toma canciones que escuchas o descargas y busca su "radio" (canciones parecidas)
  en YouTube Music, quitando las que ya tienes.
"""
import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yt_dlp
from ytmusicapi import YTMusic

from . import biblioteca
from . import descargas as nucleo
from . import plataforma

_local = threading.local()


def _yt() -> YTMusic:
    # Un cliente por hilo: las búsquedas corren en segundo plano
    if not hasattr(_local, "cliente"):
        _local.cliente = YTMusic()
    return _local.cliente


@dataclass
class ResultadoCancion:
    video_id: str
    titulo: str
    artista: str
    album: str = ""
    duracion: float | None = None
    miniatura: str | None = None
    anio: str = ""


@dataclass
class ResultadoAlbum:
    browse_id: str
    titulo: str
    artista: str
    anio: str = ""
    tipo: str = ""
    miniatura: str | None = None


@dataclass
class Seccion:
    titulo: str
    canciones: list[ResultadoCancion] = field(default_factory=list)
    artistas: list[dict] = field(default_factory=list)  # {"nombre", "miniatura"}


def _miniatura(thumbs: list | None, lado: int = 300) -> str | None:
    if not thumbs:
        return None
    url = thumbs[-1].get("url", "")
    # Las portadas de YouTube Music aceptan cualquier tamaño cambiando "=w120-h120"
    return re.sub(r"=w\d+-h\d+", f"=w{lado}-h{lado}", url)


def _segundos(texto: str | None) -> float | None:
    if not texto:
        return None
    partes = [int(p) for p in texto.split(":") if p.isdigit()]
    total = 0
    for p in partes:
        total = total * 60 + p
    return float(total) or None


def _cancion(d: dict) -> ResultadoCancion | None:
    if not d.get("videoId"):
        return None
    return ResultadoCancion(
        video_id=d["videoId"],
        titulo=d.get("title") or "",
        artista=", ".join(a["name"] for a in d.get("artists") or [] if a.get("name")),
        # En búsquedas "album" es {"name": ...}; dentro de get_album viene como texto
        album=(d.get("album") if isinstance(d.get("album"), str) else (d.get("album") or {}).get("name")) or "",
        duracion=d.get("duration_seconds") or _segundos(d.get("duration") or d.get("length")),
        miniatura=_miniatura(d.get("thumbnails") or d.get("thumbnail")),
        anio=str(d.get("year") or ""),
    )


def buscar_canciones(consulta: str, limite: int = 30) -> list[ResultadoCancion]:
    return [c for c in (_cancion(d) for d in _yt().search(consulta, filter="songs", limit=limite)) if c]


def buscar_albumes(consulta: str, limite: int = 20) -> list[ResultadoAlbum]:
    return [
        ResultadoAlbum(
            browse_id=d["browseId"],
            titulo=d.get("title") or "",
            artista=", ".join(a["name"] for a in d.get("artists") or [] if a.get("name")),
            anio=str(d.get("year") or ""),
            tipo=d.get("type") or "",
            miniatura=_miniatura(d.get("thumbnails")),
        )
        for d in _yt().search(consulta, filter="albums", limit=limite) if d.get("browseId")
    ]


def url_album(browse_id: str) -> str:
    """Link de playlist del álbum, que el analizador de la cola ya sabe descargar."""
    album = _yt().get_album(browse_id)
    lista = album.get("audioPlaylistId")
    if not lista:
        raise RuntimeError("YouTube Music no tiene una lista de reproducción para este álbum")
    return f"https://music.youtube.com/playlist?list={lista}"


def radio(video_id: str, limite: int = 25) -> list[ResultadoCancion]:
    pistas = _yt().get_watch_playlist(video_id, limit=limite).get("tracks") or []
    return [c for c in (_cancion(p) for p in pistas[1:]) if c]  # la primera es la misma canción


def buscar_id(artista: str, titulo: str) -> ResultadoCancion | None:
    resultados = buscar_canciones(f"{biblioteca.artista_principal(artista)} {titulo}", limite=5)
    objetivo = biblioteca.normalizar(titulo)
    for r in resultados:
        if biblioteca.normalizar(r.titulo) == objetivo:
            return r
    return resultados[0] if resultados else None


def artistas_parecidos(nombre: str, limite: int = 10) -> list[dict]:
    encontrados = _yt().search(nombre, filter="artists", limit=3)
    if not encontrados or not encontrados[0].get("browseId"):
        return []
    info = _yt().get_artist(encontrados[0]["browseId"])
    return [{"nombre": r.get("title", ""), "browse_id": r.get("browseId"), "miniatura": _miniatura(r.get("thumbnails"))}
            for r in (info.get("related") or {}).get("results", [])[:limite] if r.get("title")]


def _artistas_de(d: dict) -> tuple[str, str | None]:
    artistas = [a for a in d.get("artists") or [] if a.get("name")]
    return ", ".join(a["name"] for a in artistas), (artistas[0].get("id") if artistas else None)


def buscar_artistas(consulta: str, limite: int = 10) -> list[dict]:
    return [{"browse_id": d["browseId"], "nombre": d.get("artist") or d.get("title") or "",
             "miniatura": _miniatura(d.get("thumbnails"))}
            for d in _yt().search(consulta, filter="artists", limit=limite) if d.get("browseId")]


def album(browse_id: str) -> dict:
    """Página de un álbum: portada, datos y canciones (con su video_id para descargar o escuchar)."""
    a = _yt().get_album(browse_id)
    artista, artista_id = _artistas_de(a)
    portada = _miniatura(a.get("thumbnails"), 600)
    canciones = []
    for t in a.get("tracks") or []:
        c = _cancion(t)
        if c:
            c.album = c.album or a.get("title", "")
            c.miniatura = c.miniatura or portada
            canciones.append(c)
    return {
        "browse_id": browse_id, "titulo": a.get("title", ""), "artista": artista, "artista_id": artista_id,
        "anio": str(a.get("year") or ""), "tipo": a.get("type", ""), "portada": portada,
        "duracion": a.get("duration", ""), "canciones": canciones,
        "lista": f"https://music.youtube.com/playlist?list={a['audioPlaylistId']}" if a.get("audioPlaylistId") else None,
    }


def artista(browse_id: str) -> dict:
    """Página de un artista: foto grande, descripción, canciones populares, álbumes y parecidos."""
    a = _yt().get_artist(browse_id)
    def lista(clave):
        return (a.get(clave) or {}).get("results") or []
    albumes = [ResultadoAlbum(browse_id=x["browseId"], titulo=x.get("title", ""), artista=a.get("name", ""),
                              anio=str(x.get("year") or ""), tipo=x.get("type") or "Álbum",
                              miniatura=_miniatura(x.get("thumbnails")))
               for x in lista("albums") + lista("singles") if x.get("browseId")]
    return {
        "browse_id": browse_id, "nombre": a.get("name", ""), "descripcion": a.get("description") or "",
        "portada": _miniatura(a.get("thumbnails"), 900), "oyentes": a.get("monthlyListeners") or "",
        "canciones": [c for c in (_cancion(s) for s in lista("songs")) if c],
        "albumes": albumes,
        "parecidos": [{"browse_id": r.get("browseId"), "nombre": r.get("title", ""),
                       "miniatura": _miniatura(r.get("thumbnails"))} for r in lista("related") if r.get("title")],
    }


def a_entrada(r: ResultadoCancion, indice: int = 1) -> nucleo.Entrada:
    return nucleo.Entrada(
        indice=indice, id=r.video_id, titulo=r.titulo, artista=r.artista,
        url=f"https://music.youtube.com/watch?v={r.video_id}", fuente="ytmusic",
        duracion=r.duracion, miniatura=r.miniatura, album=r.album or None, clave=f"youtube {r.video_id}",
    )


# ---------- Vista previa ----------

def carpeta_cache() -> Path:
    carpeta = plataforma.carpeta_cache() / "previas"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def previa(video_id: str) -> Path:
    """Baja el audio tal cual (sin convertir) para escucharlo. Se guardan como máximo 25 en caché."""
    cache = carpeta_cache()
    existentes = sorted(cache.glob(f"{video_id}.*"))
    audio = [p for p in existentes if p.suffix.lower() in (".m4a", ".webm", ".opus", ".mp3")]
    if audio:
        audio[0].touch()
        return audio[0]
    logger = nucleo._Logger()
    opciones = nucleo._opciones_base(logger) | {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": str(cache / "%(id)s.%(ext)s"),
        "noplaylist": True,
    }
    try:
        info = nucleo.extraer(opciones, f"https://music.youtube.com/watch?v={video_id}", True, logger)
    except Exception as e:
        raise RuntimeError(logger.ultimo_error or str(e)) from e
    if not info or not info.get("requested_downloads"):
        raise RuntimeError(logger.ultimo_error or "No se pudo cargar la vista previa")
    # Limpiar las más viejas
    viejas = sorted(cache.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[25:]
    for p in viejas:
        p.unlink(missing_ok=True)
    return Path(info["requested_downloads"][0]["filepath"])


# ---------- Recomendaciones ----------

def _cache_recomendaciones() -> Path:
    return biblioteca.ruta_db().parent / "recomendaciones.json"


def recomendaciones_guardadas(max_horas: float = 6) -> list[Seccion] | None:
    try:
        datos = json.loads(_cache_recomendaciones().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - datos.get("fecha", 0) > max_horas * 3600:
        return None
    return [Seccion(s["titulo"], [ResultadoCancion(**c) for c in s["canciones"]], s.get("artistas", []))
            for s in datos.get("secciones", [])]


def recomendaciones(db: biblioteca.Biblioteca, semillas: int = 3) -> list[Seccion]:
    """Arma las secciones de "Para ti" a partir de lo que más escuchas o descargas."""
    vistas: set[str] = set()
    porque: list[Seccion] = []
    for artista, titulo, motivo in db.semillas(semillas):
        base = buscar_id(artista, titulo)
        if base is None:
            continue
        nuevas = []
        for r in radio(base.video_id):
            clave = biblioteca.clave(r.artista, r.titulo)
            if clave in vistas or db.buscar_existente(r.artista, r.titulo, r.duracion):
                continue  # ya la tienes o ya salió en otra sección
            vistas.add(clave)
            nuevas.append(r)
        if nuevas:
            porque.append(Seccion(f"Porque {motivo} {titulo} · {biblioteca.artista_principal(artista)}", nuevas[:14]))

    secciones = []
    if porque:
        # "Para ti": las primeras de cada radio, intercaladas
        mezcla = [s.canciones[i] for i in range(4) for s in porque if i < len(s.canciones)]
        secciones.append(Seccion("Para ti", mezcla[:12]))
        secciones.extend(porque)
    favorito = db.artista_favorito()
    if favorito:
        try:
            parecidos = artistas_parecidos(favorito)
        except Exception:
            parecidos = []
        if parecidos:
            secciones.append(Seccion(f"Artistas parecidos a {favorito}", artistas=parecidos))

    try:
        _cache_recomendaciones().write_text(json.dumps(
            {"fecha": time.time(), "secciones": [asdict(s) for s in secciones]}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return secciones
