"""Ver y editar las etiquetas de una canción descargada (y su carátula) con mutagen.

Sirve igual en Windows y Android (no hace falta ffmpeg). Formatos que se pueden editar: mp3 (ID3), m4a/mp4,
flac y ogg/opus. WAV, AIFF, WMA y demás solo se leen.
"""
import base64
from pathlib import Path

import mutagen
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.easymp4 import EasyMP4Tags
from mutagen.mp4 import MP4, MP4Cover

# El m4a sí guarda compositor (©wrt), pero el modo "fácil" de mutagen no lo trae registrado
if "composer" not in EasyMP4Tags.Get:
    EasyMP4Tags.RegisterTextKey("composer", "\xa9wrt")

# Lo que se puede editar: nombre en la interfaz -> etiqueta "fácil" de mutagen (igual en todos los formatos)
CAMPOS = {
    "titulo": "title", "artista": "artist", "album": "album", "artista_album": "albumartist",
    "anio": "date", "pista": "tracknumber", "disco": "discnumber", "genero": "genre", "compositor": "composer",
}
EDITABLES = {".mp3", ".m4a", ".mp4", ".flac", ".ogg", ".oga", ".opus"}
MAX_PORTADA = 8 * 1024 * 1024


def _primero(etiquetas, clave: str) -> str:
    try:
        valor = etiquetas[clave]
    except (KeyError, ValueError, TypeError):
        return ""
    if isinstance(valor, list):
        valor = valor[0] if valor else ""
    return str(valor).strip()


def leer(ruta: Path) -> dict:
    """Etiquetas editables y datos técnicos del archivo."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise RuntimeError("No encuentro el archivo de esta canción")
    campos = dict.fromkeys(CAMPOS, "")
    tecnico: dict = {"formato": ruta.suffix.lstrip(".").upper(), "tamano_mb": round(ruta.stat().st_size / 1e6, 1),
                     "ruta": str(ruta)}
    try:
        facil = mutagen.File(ruta, easy=True)
    except Exception:
        facil = None
    if facil is not None:
        if facil.tags is not None:
            for nombre, clave in CAMPOS.items():
                campos[nombre] = _primero(facil.tags, clave)
        info = facil.info
        tecnico["duracion"] = round(getattr(info, "length", 0) or 0, 1)
        if getattr(info, "bitrate", 0):
            tecnico["kbps"] = round(info.bitrate / 1000)
        if getattr(info, "sample_rate", 0):
            tecnico["hz"] = info.sample_rate
        if getattr(info, "channels", 0):
            tecnico["canales"] = info.channels
        if getattr(info, "bits_per_sample", 0):
            tecnico["bits"] = info.bits_per_sample
        if getattr(info, "codec", ""):
            tecnico["codec"] = info.codec
    return {"campos": campos, "tecnico": tecnico, "editable": ruta.suffix.lower() in EDITABLES}


def escribir(ruta: Path, campos: dict) -> None:
    """Guarda las etiquetas que vengan en `campos` (las vacías se borran del archivo)."""
    ruta = Path(ruta)
    if ruta.suffix.lower() not in EDITABLES:
        raise RuntimeError(f"Las etiquetas de los archivos {ruta.suffix.upper().lstrip('.')} no se pueden editar aquí")
    try:
        f = mutagen.File(ruta, easy=True)
    except Exception as e:
        raise RuntimeError(f"No pude abrir el archivo ({e})") from e
    if f is None:
        raise RuntimeError("No reconozco el formato de este archivo")
    if f.tags is None:
        f.add_tags()
    for nombre, valor in campos.items():
        clave = CAMPOS.get(nombre)
        if not clave:
            continue
        valor = str(valor or "").strip()
        try:
            if valor:
                f.tags[clave] = [valor]
            elif clave in f.tags:
                del f.tags[clave]
        except (KeyError, ValueError):
            pass  # ese formato no tiene esa etiqueta (p. ej. "compositor" en algunos m4a viejos)
    try:
        f.save()
    except PermissionError as e:
        raise RuntimeError("El archivo está en uso o no hay permiso para cambiarlo") from e


def _tipo_imagen(datos: bytes) -> str:
    return "image/png" if datos[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"


def poner_portada(ruta: Path, datos: bytes) -> None:
    """Reemplaza la carátula incrustada en el archivo (JPG o PNG)."""
    ruta = Path(ruta)
    if not datos:
        raise RuntimeError("La imagen está vacía")
    if len(datos) > MAX_PORTADA:
        raise RuntimeError("La imagen pesa demasiado (máximo 8 MB)")
    if datos[:3] != b"\xff\xd8\xff" and datos[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("La carátula tiene que ser JPG o PNG")
    tipo = _tipo_imagen(datos)
    sufijo = ruta.suffix.lower()
    try:
        if sufijo == ".mp3":
            try:
                id3 = ID3(ruta)
            except ID3NoHeaderError:
                id3 = ID3()
            id3.delall("APIC")
            id3.add(APIC(encoding=3, mime=tipo, type=3, desc="Cover", data=datos))
            id3.save(ruta)
        elif sufijo in (".m4a", ".mp4"):
            mp4 = MP4(ruta)
            formato = MP4Cover.FORMAT_PNG if tipo == "image/png" else MP4Cover.FORMAT_JPEG
            mp4["covr"] = [MP4Cover(datos, formato)]
            mp4.save()
        elif sufijo == ".flac":
            flac = FLAC(ruta)
            flac.clear_pictures()
            flac.add_picture(_imagen(datos, tipo))
            flac.save()
        elif sufijo in (".ogg", ".oga", ".opus"):
            f = mutagen.File(ruta)
            if f is None:
                raise RuntimeError("No reconozco el formato de este archivo")
            if f.tags is None:
                f.add_tags()
            f.tags["metadata_block_picture"] = [base64.b64encode(_imagen(datos, tipo).write()).decode("ascii")]
            f.save()
        else:
            raise RuntimeError(f"La carátula de los archivos {sufijo.upper().lstrip('.')} no se puede cambiar aquí")
    except PermissionError as e:
        raise RuntimeError("El archivo está en uso o no hay permiso para cambiarlo") from e


def _imagen(datos: bytes, tipo: str) -> Picture:
    p = Picture()
    p.type = 3  # portada frontal
    p.mime = tipo
    p.data = datos
    return p
