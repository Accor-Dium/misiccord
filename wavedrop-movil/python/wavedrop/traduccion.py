"""Traducción de letras con MyMemory (https://mymemory.translated.net): gratis y sin clave.

Tiene un límite diario (unos 5000 caracteres por IP sin registrarse, 3 o 4 canciones), así que:
cada traducción se guarda en la caché, las líneas repetidas (el coro) se piden una sola vez y se juntan
varias líneas por pedido (MyMemory respeta los saltos de línea; acepta hasta 500 bytes).
"""
import hashlib
import html
import json

import requests

from . import plataforma

API = "https://api.mymemory.translated.net/get"
CODIGOS = {"zh": "zh-CN"}  # MyMemory pide la variante del chino
MAX_BYTES = 450


def _cache():
    carpeta = plataforma.carpeta_cache() / "traducciones"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _pedir(texto: str, origen: str, destino: str) -> str:
    par = f"{CODIGOS.get(origen, origen)}|{CODIGOS.get(destino, destino)}"
    try:
        r = requests.get(API, params={"q": texto, "langpair": par}, timeout=20)
        d = r.json()
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError("No se pudo traducir: ¿hay conexión a internet?") from e
    if r.status_code == 429 or d.get("quotaFinished") or str(d.get("responseStatus")) == "429":
        raise RuntimeError("Se acabaron las traducciones gratis de hoy (MyMemory). Mañana vuelven.")
    if str(d.get("responseStatus")) != "200":
        raise RuntimeError(f"No se pudo traducir ({d.get('responseDetails') or r.status_code})")
    return html.unescape((d.get("responseData") or {}).get("translatedText") or "")


def _recortar(texto: str) -> str:
    """Una línea sola más larga que el límite se corta (pasa con letras sin saltos de línea)."""
    return texto.encode("utf-8")[:MAX_BYTES].decode("utf-8", "ignore")


def _grupos(lineas: list[str]) -> list[list[str]]:
    grupos, actual, tam = [], [], 0
    for l in lineas:
        n = len(l.encode("utf-8")) + 1
        if actual and tam + n > MAX_BYTES:
            grupos.append(actual)
            actual, tam = [], 0
        actual.append(l)
        tam += n
    if actual:
        grupos.append(actual)
    return grupos


def _traducir_grupo(grupo: list[str], origen: str, destino: str) -> list[str]:
    partes = _pedir(_recortar("\n".join(grupo)), origen, destino).split("\n")
    if len(partes) == len(grupo):
        return [p.strip() for p in partes]
    # Se juntaron o partieron líneas: entonces una por una para que cada traducción quede en su línea
    return [_pedir(_recortar(l), origen, destino).strip() for l in grupo]


def traducir(lineas: list[str], origen: str, destino: str) -> list[str]:
    """Una traducción por línea (vacía donde la línea está vacía)."""
    clave = hashlib.md5(json.dumps([origen, destino, lineas], ensure_ascii=False).encode()).hexdigest()
    archivo = _cache() / f"{clave}.json"
    if archivo.exists():
        try:
            return json.loads(archivo.read_text(encoding="utf-8"))
        except ValueError:
            pass
    unicas = list(dict.fromkeys(l.strip() for l in lineas if l.strip()))
    hechas: dict[str, str] = {}
    for grupo in _grupos(unicas):
        hechas.update(zip(grupo, _traducir_grupo(grupo, origen, destino)))
    resultado = [hechas.get(l.strip(), "") if l.strip() else "" for l in lineas]
    archivo.write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
    return resultado
