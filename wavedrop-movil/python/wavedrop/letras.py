"""Letras de canciones: archivo .lrc local o búsqueda en LRCLIB (https://lrclib.net).

La letra encontrada se guarda junto a la canción (mismo nombre, extensión .lrc), así la
siguiente vez no hace falta internet y otros reproductores también la usan.
Si quieres poner tu propia letra, basta con dejar un .lrc con el mismo nombre que la canción.
"""
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import mutagen
import requests

API = "https://lrclib.net/api"
CABECERAS = {"User-Agent": "Misiccord/2.1 ( app de escritorio local )"}

_MARCA = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")
_OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\]", re.I)
# Lo que YouTube suele agregar al título y que estorba para buscar la letra
_RUIDO = re.compile(
    r"\s*[\(\[][^\)\]]*(official|oficial|video|vídeo|audio|lyric|letra|visualizer|hd|4k|mv|remaster)[^\)\]]*[\)\]]",
    re.I,
)


@dataclass
class Letra:
    tipo: str  # "sincronizada", "simple", "instrumental" o "ninguna"
    lineas: list[tuple[int | None, str]] = field(default_factory=list)  # (milisegundo, texto)
    fuente: str = ""  # "archivo" o "LRCLIB"


def parsear_lrc(texto: str) -> list[tuple[int | None, str]]:
    """Convierte un LRC en [(ms, línea)]. Si no trae marcas de tiempo, ms es None."""
    desfase = 0
    m = _OFFSET.search(texto)
    if m:
        desfase = int(m.group(1))
    lineas = []
    for cruda in texto.splitlines():
        marcas = _MARCA.findall(cruda)
        contenido = _MARCA.sub("", cruda).strip()
        if marcas:
            for minutos, segundos in marcas:
                ms = int((int(minutos) * 60 + float(segundos.replace(":", "."))) * 1000) - desfase
                lineas.append((max(ms, 0), contenido))
        elif not re.match(r"^\[[a-z]+:.*\]$", cruda.strip(), re.I):  # ignora [ar:], [ti:], etc.
            lineas.append((None, cruda.strip()))
    if any(ms is not None for ms, _ in lineas):
        lineas = sorted((l for l in lineas if l[0] is not None), key=lambda l: l[0])
    else:
        # Letra sin tiempos: quitar líneas vacías del principio y del final
        while lineas and not lineas[0][1]:
            lineas.pop(0)
        while lineas and not lineas[-1][1]:
            lineas.pop()
    return lineas


def _desde_texto(texto: str, fuente: str) -> Letra:
    lineas = parsear_lrc(texto)
    if not lineas:
        return Letra("ninguna")
    return Letra("sincronizada" if lineas[0][0] is not None else "simple", lineas, fuente)


def limpiar_titulo(titulo: str, artista: str) -> str:
    titulo = _RUIDO.sub("", titulo)
    # "Artista - Canción" → "Canción"
    if artista and " - " in titulo and titulo.lower().startswith(artista.split(",")[0].strip().lower()):
        titulo = titulo.split(" - ", 1)[1]
    return re.sub(r"\s+", " ", titulo).strip(" -")


def _pedir(ruta: str, params: dict):
    for intento in range(3):
        try:
            r = requests.get(f"{API}/{ruta}", params=params, headers=CABECERAS, timeout=12)
        except requests.RequestException:
            if intento == 2:
                raise
            time.sleep(1 + intento)
            continue
        if r.status_code == 404:
            return None
        if r.status_code in (429, 503):  # servidor ocupado: esperar y reintentar
            time.sleep(1.5 * (intento + 1))
            continue
        r.raise_for_status()
        return r.json()
    return None


def _de_resultado(d: dict) -> Letra:
    if d.get("instrumental"):
        return Letra("instrumental", fuente="LRCLIB")
    if d.get("syncedLyrics"):
        return _desde_texto(d["syncedLyrics"], "LRCLIB")
    if d.get("plainLyrics"):
        return _desde_texto(d["plainLyrics"], "LRCLIB")
    return Letra("ninguna")


def buscar_en_linea(titulo: str, artista: str, album: str, duracion: float | None) -> tuple[Letra, str]:
    """Devuelve la letra y el texto LRC original (para guardarlo)."""
    pista = limpiar_titulo(titulo, artista)
    principal = artista.split(",")[0].strip()

    if principal and album and duracion:
        d = _pedir("get", {"track_name": pista, "artist_name": principal, "album_name": album,
                           "duration": round(duracion)})
        if d:
            letra = _de_resultado(d)
            if letra.tipo != "ninguna":
                return letra, d.get("syncedLyrics") or d.get("plainLyrics") or ""

    consultas = [{"track_name": pista, "artist_name": principal}] if principal else []
    consultas.append({"q": f"{principal} {pista}".strip()})
    for params in consultas:
        resultados = _pedir("search", params) or []
        if not resultados:
            continue

        def puntaje(x):
            # Preferir letra sincronizada y la duración más parecida a la de la canción
            dif = abs((x.get("duration") or 0) - duracion) if duracion else 0
            return (0 if x.get("syncedLyrics") else 1, dif if dif <= 8 else 100 + dif)

        mejor = min(resultados, key=puntaje)
        if duracion and mejor.get("duration") and abs(mejor["duration"] - duracion) > 15:
            continue  # probablemente es otra canción u otra versión
        letra = _de_resultado(mejor)
        if letra.tipo != "ninguna":
            return letra, mejor.get("syncedLyrics") or mejor.get("plainLyrics") or ""
    return Letra("ninguna"), ""


def duracion_de(ruta: Path) -> float | None:
    try:
        f = mutagen.File(ruta)
        return float(f.info.length) if f and f.info else None
    except Exception:
        return None


def obtener_letra(ruta: Path, titulo: str, artista: str, album: str, duracion: float | None = None) -> Letra:
    """Primero el .lrc junto a la canción; si no hay, LRCLIB (y se guarda el .lrc)."""
    local = ruta.with_suffix(".lrc")
    if local.exists():
        letra = _desde_texto(local.read_text(encoding="utf-8", errors="replace"), "archivo")
        if letra.tipo != "ninguna":
            return letra

    letra, original = buscar_en_linea(titulo, artista, album, duracion or (duracion_de(ruta) if ruta.exists() else None))
    if original and letra.tipo in ("sincronizada", "simple"):
        try:
            local.write_text(original, encoding="utf-8")
        except OSError:
            pass
    return letra
