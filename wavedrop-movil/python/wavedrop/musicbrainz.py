"""Completa la metadata de las canciones con MusicBrainz (https://musicbrainz.org) y las portadas
con Cover Art Archive (https://coverartarchive.org).

MusicBrainz pide como máximo 1 consulta por segundo y un User-Agent que identifique a la app;
si quieres, pon tu correo o tu página en CONTACTO para que puedan avisarte si algo falla.
"""
import base64
import difflib
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import mutagen
import requests
from mutagen.flac import Picture
from mutagen.id3 import APIC, ID3
from mutagen.mp4 import MP4, MP4Cover

from .biblioteca import artista_principal, normalizar, separar_titulo

CONTACTO = "app de escritorio local"
CABECERAS = {"User-Agent": f"Misiccord/2.1 ( {CONTACTO} )", "Accept": "application/json"}
API = "https://musicbrainz.org/ws/2"

_candado = threading.Lock()
_ultima = 0.0


def _get(url: str, params: dict | None = None, timeout: int = 15) -> requests.Response:
    """GET respetando el límite de MusicBrainz (1 por segundo), compartido entre hilos."""
    global _ultima
    for intento in range(3):
        with _candado:
            espera = 1.1 - (time.monotonic() - _ultima)
            if espera > 0:
                time.sleep(espera)
            _ultima = time.monotonic()
        try:
            r = requests.get(url, params=params, headers=CABECERAS, timeout=timeout)
        except requests.RequestException as e:
            if intento == 2:
                raise RuntimeError("No pude conectar con MusicBrainz. ¿Hay internet?") from e
            time.sleep(1 + intento)
            continue
        if r.status_code == 503:  # demasiadas consultas: esperar y reintentar
            time.sleep(2 * (intento + 1))
            continue
        return r
    return r


@dataclass
class Datos:
    titulo: str
    artista: str
    album: str
    artista_album: str
    anio: str
    pista: int | None
    total_pistas: int | None
    genero: str
    mbid: str
    mbid_album: str
    mbid_grupo: str
    puntaje: int


def _creditos(ac: list | None) -> str:
    return "".join(c.get("name", "") + c.get("joinphrase", "") for c in ac or []).strip()


def _esc(texto: str) -> str:
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r"\\\1", texto)


def _valor_release(rel: dict, album_pista: str) -> tuple:
    """Menor = mejor. Prefiere el álbum que ya traía la canción, oficial, de estudio y más antiguo."""
    grupo = rel.get("release-group") or {}
    secundarios = grupo.get("secondary-types") or []
    tipo = grupo.get("primary-type") or ""
    coincide = bool(album_pista) and normalizar(rel.get("title", "")) == normalizar(album_pista)
    return (
        0 if coincide else 1,
        0 if rel.get("status") == "Official" else 1,
        0 if not secundarios else 1,  # sin "Compilation", "Soundtrack", "Live"...
        {"Album": 0, "EP": 1, "Single": 2}.get(tipo, 3),
        rel.get("date") or "9999",
    )


def buscar(titulo: str, artista: str, duracion: float | None = None, album: str = "") -> Datos | None:
    artista, titulo = separar_titulo(titulo, artista)
    titulo_limpio = re.sub(r"\s*[\(\[][^\)\]]*(official|video|audio|lyric|letra|visualizer|hd|4k)[^\)\]]*[\)\]]",
                           "", titulo, flags=re.I).strip()
    principal = artista_principal(artista)
    consulta = f'recording:"{_esc(titulo_limpio)}"'
    if principal:
        consulta += f' AND artist:"{_esc(principal)}"'
    grabaciones = []
    # Si la canción ya trae álbum (p. ej. de Spotify), primero se busca dentro de ese álbum
    for q in ([f'{consulta} AND release:"{_esc(album)}"'] if album else []) + [consulta]:
        r = _get(f"{API}/recording", {"query": q, "fmt": "json", "limit": 15})
        if not r.ok:
            raise RuntimeError(f"MusicBrainz respondió {r.status_code}")
        grabaciones = r.json().get("recordings", [])
        if any(normalizar(rel.get("title", "")) == normalizar(album)
               for g in grabaciones for rel in g.get("releases") or []) or not album:
            break

    mejores = []
    for rec in grabaciones:
        puntaje = rec.get("score", 0)
        if puntaje < 80:
            continue
        largo = (rec.get("length") or 0) / 1000
        if duracion and largo and abs(largo - duracion) > 8:
            continue
        if normalizar(rec.get("title", "")) != normalizar(titulo_limpio) and puntaje < 95:
            continue
        for rel in rec.get("releases") or []:
            mejores.append((_valor_release(rel, album), -puntaje, rec, rel))
    if not mejores:
        return None
    mejores.sort(key=lambda x: (x[0], x[1]))
    _, menos_puntaje, rec, rel = mejores[0]

    pista = total = None
    medio = (rel.get("media") or [{}])[0]
    if medio.get("track"):
        numero = str(medio["track"][0].get("number", ""))
        pista = int(numero) if numero.isdigit() else None
    total = medio.get("track-count") or rel.get("track-count")
    etiquetas = sorted(rec.get("tags") or [], key=lambda t: -t.get("count", 0))
    grupo = rel.get("release-group") or {}
    if album and normalizar(rel.get("title", "")) != normalizar(album) and (
            grupo.get("secondary-types") or rel.get("status") != "Official"):
        # Solo hay recopilatorios o piratas: mejor conservar el álbum que ya tenía la canción
        return Datos(rec.get("title") or titulo_limpio, _creditos(rec.get("artist-credit")) or artista, "", "",
                     (rec.get("first-release-date") or "")[:4], None, None,
                     etiquetas[0]["name"].title() if etiquetas else "", rec.get("id", ""), "", "", -menos_puntaje)
    return Datos(
        titulo=rec.get("title") or titulo_limpio,
        artista=_creditos(rec.get("artist-credit")) or artista,
        album=rel.get("title", ""),
        artista_album=_creditos(rel.get("artist-credit")) or _creditos(rec.get("artist-credit")),
        anio=(rel.get("date") or rec.get("first-release-date") or "")[:4],
        pista=pista,
        total_pistas=total,
        genero=etiquetas[0]["name"].title() if etiquetas else "",
        mbid=rec.get("id", ""),
        mbid_album=rel.get("id", ""),
        mbid_grupo=grupo.get("id", ""),
        puntaje=-menos_puntaje,
    )


def opciones(titulo: str, artista: str, duracion: float | None = None, album: str = "", limite: int = 40) -> list[dict]:
    """Todas las ediciones en las que sale la canción, para que elijas (como Picard): Thriller, Thriller 25, HIStory...

    Primero las que mejor le quedan (la que ya traía, oficiales, de estudio y más antiguas). Se quita lo repetido:
    la misma edición sale muchas veces, una por país o formato.
    """
    artista, titulo = separar_titulo(titulo, artista)
    limpio = re.sub(r"\s*[\(\[][^\)\]]*(official|video|audio|lyric|letra|visualizer|hd|4k)[^\)\]]*[\)\]]",
                    "", titulo, flags=re.I).strip()
    principal = artista_principal(artista)
    consulta = f'recording:"{_esc(limpio)}"' + (f' AND artist:"{_esc(principal)}"' if principal else "")
    r = _get(f"{API}/recording", {"query": consulta, "fmt": "json", "limit": 100})
    if not r.ok:
        raise RuntimeError(f"MusicBrainz respondió {r.status_code}")
    objetivo = normalizar(limpio)
    candidatas = []
    for rec in r.json().get("recordings", []):
        puntaje = rec.get("score", 0)
        largo = (rec.get("length") or 0) / 1000
        if puntaje < 70 or (duracion and largo and abs(largo - duracion) > 15):
            continue
        # Mismo nombre primero: las mezclas y versiones ("… (live)") se quedan al final
        distinta = 0 if normalizar(rec.get("title", "")) == objetivo else 1
        for rel in rec.get("releases") or []:
            candidatas.append(((distinta, *_valor_release(rel, album)), -puntaje, rec, rel))
    candidatas.sort(key=lambda x: (x[0], x[1]))

    # Una por álbum (grupo de MusicBrainz): el orden ya deja primero su edición más antigua, así Thriller sale de 1982 y
    # no de una reedición; Thriller 25 y HIStory son otros grupos y salen aparte
    vistas, salida = set(), []
    for _, _, rec, rel in candidatas:
        grupo = rel.get("release-group") or {}
        clave = grupo.get("id") or normalizar(rel.get("title", ""))
        if clave in vistas:
            continue
        vistas.add(clave)
        medio = (rel.get("media") or [{}])[0]
        numero = str((medio.get("track") or [{}])[0].get("number", ""))
        etiquetas = sorted(rec.get("tags") or [], key=lambda t: -t.get("count", 0))
        secundarios = grupo.get("secondary-types") or []
        salida.append({
            "titulo": rec.get("title") or limpio,
            "artista": _creditos(rec.get("artist-credit")) or artista,
            "album": rel.get("title", ""),
            "artista_album": _creditos(rel.get("artist-credit")) or _creditos(rec.get("artist-credit")),
            "anio": (rel.get("date") or rec.get("first-release-date") or "")[:4],
            "pista": int(numero) if numero.isdigit() else None,
            "total_pistas": medio.get("track-count") or rel.get("track-count"),
            "genero": etiquetas[0]["name"].title() if etiquetas else "",
            "mbid": rec.get("id", ""),
            "mbid_album": rel.get("id", ""),
            "mbid_grupo": grupo.get("id", ""),
            "puntaje": rec.get("score", 0),
            "tipo": secundarios[0] if secundarios else grupo.get("primary-type") or "",
            "pais": rel.get("country") or "",
            "miniatura": f"https://coverartarchive.org/release/{rel.get('id')}/front-250" if rel.get("id") else None,
        })
        if len(salida) >= limite:
            break
    return salida


def buscar_albumes(nombre: str, artista: str = "", limite: int = 25) -> list[dict]:
    """Las ediciones de un álbum para elegir la tuya. Van por edición y no por álbum: la normal y la de lujo traen otras pistas."""
    principal = artista_principal(artista)
    sin_extra = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]\s*$", "", nombre).strip() or nombre  # "Tour Fantasía Pop [Live]"
    intentos = []
    for titulo in dict.fromkeys((nombre, sin_extra)):
        if principal:
            intentos.append(f'release:"{_esc(titulo)}" AND artist:"{_esc(principal)}"')
        intentos.append(f'release:"{_esc(titulo)}"')
    candidatas = []
    for consulta in intentos:
        r = _get(f"{API}/release", {"query": consulta, "fmt": "json", "limit": 50})
        if not r.ok:
            raise RuntimeError(f"MusicBrainz respondió {r.status_code}")
        candidatas = [x for x in r.json().get("releases", []) if x.get("score", 0) >= 60]
        if candidatas:
            break
    objetivo = normalizar(sin_extra)
    candidatas.sort(key=lambda x: (0 if normalizar(x.get("title", "")) == objetivo else 1, _valor_release(x, nombre), -x.get("score", 0)))

    vistas, salida = set(), []
    for rel in candidatas:
        grupo = rel.get("release-group") or {}
        clave = (grupo.get("id") or normalizar(rel.get("title", "")), rel.get("track-count"))
        if clave in vistas:
            continue
        vistas.add(clave)
        secundarios = grupo.get("secondary-types") or []
        salida.append({
            "mbid_album": rel.get("id", ""), "mbid_grupo": grupo.get("id", ""), "album": rel.get("title", ""),
            "artista_album": _creditos(rel.get("artist-credit")), "anio": (rel.get("date") or "")[:4],
            "tipo": secundarios[0] if secundarios else grupo.get("primary-type") or "", "pais": rel.get("country") or "",
            "pistas": rel.get("track-count") or 0,
            "miniatura": f"https://coverartarchive.org/release/{rel.get('id')}/front-250" if rel.get("id") else None,
        })
        if len(salida) >= limite:
            break
    return salida


def album_detalle(mbid: str) -> dict:
    """Una edición con todas sus pistas."""
    r = _get(f"{API}/release/{mbid}", {"inc": "recordings artist-credits release-groups genres tags", "fmt": "json"})
    if not r.ok:
        raise RuntimeError(f"MusicBrainz respondió {r.status_code}")
    rel = r.json()
    grupo = rel.get("release-group") or {}
    pistas = []
    for medio in rel.get("media") or []:
        for t in medio.get("tracks") or []:
            rec = t.get("recording") or {}
            largo = t.get("length") or rec.get("length")
            pistas.append({
                "disco": medio.get("position") or 1, "pista": t.get("position") or 0, "titulo": t.get("title") or rec.get("title") or "",
                "artista": _creditos(t.get("artist-credit") or rec.get("artist-credit")) or _creditos(rel.get("artist-credit")),
                "duracion": largo / 1000 if largo else None, "mbid": rec.get("id", ""),
            })
    etiquetas = rel.get("genres") or grupo.get("genres") or rel.get("tags") or grupo.get("tags") or []
    etiquetas = sorted(etiquetas, key=lambda x: -x.get("count", 0))
    return {
        "mbid_album": rel.get("id", ""), "mbid_grupo": grupo.get("id", ""), "album": rel.get("title", ""),
        "artista_album": _creditos(rel.get("artist-credit")), "anio": (rel.get("date") or grupo.get("first-release-date") or "")[:4],
        "genero": etiquetas[0]["name"].title() if etiquetas else "", "pistas": pistas,
        "discos": len(rel.get("media") or []) or 1,
        "miniatura": f"https://coverartarchive.org/release/{rel.get('id')}/front-500",
    }


def _letras(texto: str) -> str:
    """Solo letras y números, sin acentos: "Cada Que..." y "Cada que…" son iguales, "Rosa (en vivo)" y "Rosa" no."""
    plano = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", plano)


def emparejar(canciones: list[dict], pistas: list[dict]) -> list[dict]:
    """A cada canción tuya, la pista del álbum que le toca: {"pista": índice o None, "estado": exacta|parecida|ninguna}.

    Se reparten de la mejor pareja a la peor y cada pista se usa una sola vez. Si la duración se parece, ayuda a decidir.
    """
    parejas = []
    for i, c in enumerate(canciones):
        a = normalizar(c.get("titulo", ""))
        for j, p in enumerate(pistas):
            b = normalizar(p.get("titulo", ""))
            if not a or not b:
                continue
            # normalizar() quita lo que va entre paréntesis: sirve para encontrar la pareja, pero "(en vivo)" no es exacta
            if _letras(c.get("titulo")) == _letras(p.get("titulo")):
                parecido = 1.0
            elif a == b:
                parecido = 0.95
            else:
                parecido = difflib.SequenceMatcher(None, a, b).ratio()
                if a in b or b in a:
                    parecido = max(parecido, 0.9)
            if parecido < 0.55:
                continue
            ajuste = 0.0
            if c.get("duracion") and p.get("duracion"):
                dif = abs(c["duracion"] - p["duracion"])
                ajuste = 0.05 if dif <= 3 else -0.1 if dif > 20 else 0.0
            parejas.append((parecido + ajuste, parecido, i, j))
    parejas.sort(key=lambda x: (-x[0], x[2], x[3]))
    resultado = [{"pista": None, "estado": "ninguna"} for _ in canciones]
    usadas: set[int] = set()
    for _, parecido, i, j in parejas:
        if resultado[i]["pista"] is None and j not in usadas:
            usadas.add(j)
            resultado[i] = {"pista": j, "estado": "exacta" if parecido >= 0.97 else "parecida"}
    return resultado


def portada_de(mbid_album: str, mbid_grupo: str = "", tam: int = 500) -> bytes | None:
    for tipo, mbid in (("release", mbid_album), ("release-group", mbid_grupo)):
        if not mbid:
            continue
        url = f"https://coverartarchive.org/{tipo}/{mbid}/front-{tam}"
        try:
            r = requests.get(url, headers=CABECERAS, timeout=20)
        except requests.RequestException:
            continue
        if r.ok and r.headers.get("content-type", "").startswith("image/"):
            return r.content
    return None


def portada(datos: Datos, tam: int = 500) -> bytes | None:
    return portada_de(datos.mbid_album, datos.mbid_grupo, tam)


def escribir(ruta: Path, datos: Datos, imagen: bytes | None) -> None:
    """Guarda las etiquetas (y la portada, si hay) dentro del archivo de audio."""
    pista = f"{datos.pista}/{datos.total_pistas}" if datos.pista and datos.total_pistas else str(datos.pista or "")
    valores = {
        "title": datos.titulo, "artist": datos.artista, "album": datos.album, "albumartist": datos.artista_album,
        "date": datos.anio, "tracknumber": pista, "genre": datos.genero,
        "musicbrainz_trackid": datos.mbid, "musicbrainz_albumid": datos.mbid_album,
    }
    f = mutagen.File(ruta, easy=True)
    if f is None:
        raise RuntimeError("Formato de audio no soportado para etiquetas")
    if f.tags is None:
        f.add_tags()
    for clave, valor in valores.items():
        if not valor:
            continue
        try:
            f.tags[clave] = [valor]
        except (KeyError, ValueError, TypeError):
            pass  # este formato no tiene esa etiqueta
    f.save()

    if not imagen:
        return
    mime = "image/png" if imagen[:4] == b"\x89PNG" else "image/jpeg"
    ext = ruta.suffix.lower()
    if ext == ".mp3":
        id3 = ID3(ruta)
        id3.delall("APIC")
        id3.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=imagen))
        id3.save()
    elif ext in (".m4a", ".mp4", ".aac", ".alac"):
        mp4 = MP4(ruta)
        mp4["covr"] = [MP4Cover(imagen, MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG)]
        mp4.save()
    else:
        archivo = mutagen.File(ruta)
        pic = Picture()
        pic.type, pic.mime, pic.desc, pic.data = 3, mime, "Cover", imagen
        if hasattr(archivo, "add_picture"):  # FLAC
            archivo.clear_pictures()
            archivo.add_picture(pic)
        else:  # Ogg/Opus
            archivo["metadata_block_picture"] = [base64.b64encode(pic.write()).decode("ascii")]
        archivo.save()


def completar(ruta: Path, titulo: str, artista: str, duracion: float | None, album: str = "") -> Datos | None:
    """Busca, descarga la portada y escribe todo en el archivo. Devuelve lo encontrado (o None)."""
    datos = buscar(titulo, artista, duracion, album)
    if datos is None:
        return None
    escribir(ruta, datos, portada(datos))
    return datos
