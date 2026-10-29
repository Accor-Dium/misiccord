"""Servicio de Misiccord para escritorio: la app de Tauri lo arranca y le habla por stdin/stdout.

Protocolo (una línea JSON por mensaje):
  entrada  {"id": 7, "funcion": "buscar", "datos": "{...}"}
  salida   {"id": 7, "resultado": "{...}"}     respuesta a una llamada
  salida   {"evento": "{...}"}                  aviso de Python (progreso, recomendaciones...)

Cada llamada corre en su propio hilo para que una búsqueda lenta no bloquee a las demás.
"""
import io
import json
import os
import sys
import threading
from pathlib import Path

# Al empaquetarlo (PyInstaller) el paquete wavedrop va adentro; en desarrollo está junto a este archivo
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wavedrop import api  # noqa: E402

_salida = threading.Lock()
# El protocolo siempre va en UTF-8, sin importar la configuración regional de Windows
_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
_stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
# Cualquier print() de una librería iría a stdout y rompería el protocolo: se manda a stderr
sys.stdout = sys.stderr


def escribir(mensaje: dict) -> None:
    linea = json.dumps(mensaje, ensure_ascii=False) + "\n"
    with _salida:
        _stdout.write(linea)
        _stdout.flush()


class Emisor:
    def emitir(self, texto: str) -> None:
        escribir({"evento": texto})


def contexto() -> dict:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WaveDrop"
    musica = os.environ.get("WAVEDROP_MUSICA") or str(Path.home() / "Music" / "Misiccord")
    return {"datos": str(local), "musica": musica, "cache": str(local / "cache")}


def atender(peticion: dict, emisor: Emisor, ctx: str) -> None:
    resultado = api.despachar(peticion["funcion"], peticion.get("datos", "{}"), ctx, emisor)
    escribir({"id": peticion["id"], "resultado": resultado})


def main() -> None:
    emisor = Emisor()
    ctx = json.dumps(contexto())
    for linea in _stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            peticion = json.loads(linea)
        except ValueError:
            continue
        threading.Thread(target=atender, args=(peticion, emisor, ctx), daemon=True).start()


if __name__ == "__main__":
    main()
