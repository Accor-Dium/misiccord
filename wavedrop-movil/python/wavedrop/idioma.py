"""Idioma de lo que Python le manda a la interfaz (títulos de secciones, avisos en segundo plano).

La interfaz decide el idioma (el del dispositivo o el elegido en Ajustes) y lo avisa con `api.poner_idioma`.
Los textos se escriben en español en el código y aquí está su traducción; lo que no esté se queda en español.
YouTube Music también se pide en ese idioma (títulos de sus secciones y estados de ánimo).
"""

IDIOMAS = ("es", "en")
_actual = "es"

_EN = {
    "Para ti": "For you",
    "Porque {motivo} {titulo} · {artista}": "Because you {motivo} {titulo} · {artista}",
    "escuchas": "listen to",
    "descargaste": "downloaded",
    "tienes": "have",
    "Artistas parecidos a {nombre}": "Artists similar to {nombre}",
    "Leyendo tu música": "Reading your music",
    "Leyendo tu música ({n})": "Reading your music ({n})",
    "Video de “{titulo}”": "Video for “{titulo}”",
    "Descargando “{titulo}”": "Downloading “{titulo}”",
    "Jam abierto": "Jam open",
    "Tus invitados siguen conectados": "Your guests are still connected",
    "Descargando la actualización": "Downloading the update",
    "Copiando a {destino}": "Copying to {destino}",
    "En curso…": "In progress…",
    "{n} tareas en segundo plano": "{n} background tasks",
    "Actualización lista: ábrela para instalarla": "Update ready: open it to install",
    "1 canción descargada": "1 song downloaded",
    "{n} canciones descargadas": "{n} songs downloaded",
    "Video descargado": "Video downloaded",
}


def poner(idioma: str) -> bool:
    """Devuelve True si cambió."""
    global _actual
    nuevo = idioma if idioma in IDIOMAS else "es"
    cambio = nuevo != _actual
    _actual = nuevo
    return cambio


def actual() -> str:
    return _actual


def t(texto: str, **datos) -> str:
    if _actual == "en":
        texto = _EN.get(texto, texto)
    return texto.format(**datos) if datos else texto
