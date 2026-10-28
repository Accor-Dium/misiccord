"""API de WaveDrop para la interfaz (Tauri). Todo entra por despachar() y sale como JSON.

- Android: Kotlin (PythonPlugin) llama a despachar(funcion, datos, contexto, emisor).
- Windows: el servicio local hará lo mismo (siguiente etapa).

Los avisos que llegan después (progreso de descargas, recomendaciones listas) se mandan con
emitir(tipo, datos), que en Android llama a emisor.emitir(json) y llega a la interfaz como evento.
"""
import hashlib
import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from . import biblioteca, descargas, explorar, letras, musicbrainz, plataforma

_estado = {"db": None, "emisor": None, "ajustes": None}
_candado = threading.RLock()

AJUSTES_POR_DEFECTO = {
    "fundido": 6,          # segundos de fundido entre canciones (0 = sin fundido)
    "formato": 2,          # índice en descargas.FORMATOS (solo aplica con ffmpeg, en Windows)
    "musicbrainz": True,   # completar datos al descargar
    "por_artista": True,   # carpetas por artista
    "descargas_simultaneas": 2,
}


# ---------- Utilidades ----------

def emitir(tipo: str, datos: dict) -> None:
    emisor = _estado["emisor"]
    texto = json.dumps({"tipo": tipo, **datos}, ensure_ascii=False)
    if emisor is None:
        print(texto, flush=True)  # modo servicio (Windows): una línea JSON por evento
        return
    try:
        emisor.emitir(texto)
    except Exception:
        pass


def _db() -> biblioteca.Biblioteca:
    if _estado["db"] is None:
        raise RuntimeError("Llama primero a iniciar()")
    return _estado["db"]


def _ruta_ajustes() -> Path:
    return plataforma.carpeta_datos() / "ajustes.json"


def _ajustes() -> dict:
    if _estado["ajustes"] is None:
        try:
            guardados = json.loads(_ruta_ajustes().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            guardados = {}
        _estado["ajustes"] = AJUSTES_POR_DEFECTO | guardados
    return _estado["ajustes"]


_portadas: dict[str, str | None] = {}


def portada_local(ruta: Path) -> str | None:
    """Extrae la portada incrustada a la caché (una vez por álbum) y devuelve la ruta del archivo."""
    import base64
    import mutagen
    clave = str(ruta.parent) + "|" + ruta.stem
    if clave in _portadas:
        return _portadas[clave]
    destino = plataforma.carpeta_cache() / "portadas" / (hashlib.md5(str(ruta).encode()).hexdigest() + ".jpg")
    resultado = None
    if destino.exists():
        resultado = str(destino)
    else:
        try:
            f = mutagen.File(ruta)
            datos = None
            if f is not None and f.tags is not None:
                for k in f.tags.keys():
                    if k.startswith("APIC"):
                        datos = f.tags[k].data
                        break
                if datos is None and "covr" in f.tags:
                    datos = bytes(f.tags["covr"][0])
                if datos is None and "metadata_block_picture" in f.tags:
                    from mutagen.flac import Picture
                    datos = Picture(base64.b64decode(f.tags["metadata_block_picture"][0])).data
            if datos:
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(datos)
                resultado = str(destino)
        except Exception:
            resultado = None
    _portadas[clave] = resultado
    return resultado


def _local(c: biblioteca.Cancion) -> dict:
    return {"local": True, "ruta": str(c.ruta), "db_id": c.id, "titulo": c.titulo, "artista": c.artista,
            "album": c.album, "anio": c.anio, "pista": c.pista, "duracion": c.duracion,
            "portada": portada_local(c.ruta)}


def _en_linea(r: explorar.ResultadoCancion) -> dict:
    existente = _db().buscar_existente(r.artista, r.titulo, r.duracion)
    return {"local": False, "id": r.video_id, "titulo": r.titulo, "artista": r.artista, "album": r.album,
            "duracion": r.duracion, "portada": r.miniatura, "anio": r.anio,
            "ruta": str(existente.ruta) if existente else None}


def _album_local(a: biblioteca.Album) -> dict:
    return {"nombre": a.nombre, "artista": a.artista, "grupo": a.grupo, "anio": a.anio,
            "canciones": a.canciones, "portada": portada_local(a.ruta_portada)}


# ---------- Arranque y ajustes ----------

def iniciar(d: dict) -> dict:
    with _candado:
        plataforma.configurar(d["datos"], d["musica"], d["cache"], d.get("libs"))
        if _estado["db"] is None:
            _estado["db"] = biblioteca.Biblioteca()
        _db().agregar_carpeta(Path(d["musica"]))
    threading.Thread(target=_escanear, daemon=True).start()
    return {"ajustes": _ajustes(), "android": plataforma.es_android(), "ffmpeg": plataforma.hay_ffmpeg(),
            "js": list(plataforma.js_runtimes().keys()), "total": _db().total()}


def _escanear():
    try:
        nuevas, quitadas = _db().escanear()
        emitir("biblioteca", {"nuevas": nuevas, "quitadas": quitadas, "total": _db().total()})
    except Exception as e:
        emitir("error", {"donde": "escaneo", "mensaje": str(e)})


def ajustes(d: dict) -> dict:
    return {"ajustes": _ajustes()}


def guardar_ajustes(d: dict) -> dict:
    _ajustes().update({k: v for k, v in d.items() if k in AJUSTES_POR_DEFECTO})
    _ruta_ajustes().write_text(json.dumps(_ajustes(), ensure_ascii=False), encoding="utf-8")
    return {"ajustes": _ajustes()}


# ---------- Inicio y recomendaciones ----------

_recs = {"cargando": False}


def inicio(d: dict) -> dict:
    db = _db()
    guardadas = explorar.recomendaciones_guardadas()
    if guardadas is None:
        recomendaciones({})
    return {
        "recientes": [_local(c) for c in db.recientes(12)],
        "mas_escuchadas": [_local(c) for c, _n in db.mas_escuchadas(12)],
        "albumes": [_album_local(a) for a in db.albumes()[:12]],
        "secciones": _secciones(guardadas) if guardadas is not None else None,
        "total": db.total(),
    }


def _secciones(secciones: list) -> list[dict]:
    return [{"titulo": s.titulo, "canciones": [_en_linea(c) for c in s.canciones], "artistas": s.artistas}
            for s in secciones]


def recomendaciones(d: dict) -> dict:
    """Genera recomendaciones en segundo plano y avisa con el evento "recomendaciones"."""
    if _recs["cargando"]:
        return {"cargando": True}
    _recs["cargando"] = True

    def trabajo():
        try:
            secciones = explorar.recomendaciones(_db()) if _db().semillas(1) else []
            emitir("recomendaciones", {"secciones": _secciones(secciones)})
        except Exception as e:
            emitir("recomendaciones", {"secciones": [], "error": str(e)})
        finally:
            _recs["cargando"] = False

    threading.Thread(target=trabajo, daemon=True).start()
    return {"cargando": True}


# ---------- Buscar, álbum y artista (YouTube Music) ----------

def buscar(d: dict) -> dict:
    q, tipo = d["q"].strip(), d.get("tipo", "todo")
    res: dict = {}
    if tipo in ("todo", "canciones"):
        res["canciones"] = [_en_linea(c) for c in explorar.buscar_canciones(q, 30 if tipo == "canciones" else 12)]
    if tipo in ("todo", "albumes"):
        res["albumes"] = [asdict(a) for a in explorar.buscar_albumes(q, 20 if tipo == "albumes" else 8)]
    if tipo in ("todo", "artistas"):
        res["artistas"] = explorar.buscar_artistas(q, 20 if tipo == "artistas" else 8)
    return res


def album(d: dict) -> dict:
    a = explorar.album(d["browse_id"])
    a["canciones"] = [_en_linea(c) for c in a["canciones"]]
    return {"album": a}


def artista(d: dict) -> dict:
    a = explorar.artista(d["browse_id"])
    a["canciones"] = [_en_linea(c) for c in a["canciones"]]
    a["albumes"] = [asdict(x) for x in a["albumes"]]
    return {"artista": a}


# ---------- Biblioteca y playlists ----------

def biblioteca_(d: dict) -> dict:
    db = _db()
    return {
        "canciones": [_local(c) for c in db.canciones(d.get("q", ""))],
        "albumes": [_album_local(a) for a in db.albumes()],
        "artistas": [{"nombre": n, "canciones": k} for n, k in db.artistas()],
        "playlists": [{"id": i, "nombre": n, "canciones": k} for i, n, k in db.playlists()],
    }


def album_local(d: dict) -> dict:
    a = biblioteca.Album(d["nombre"], d.get("artista", ""), "", 0, Path(), d.get("grupo", ""))
    return {"canciones": [_local(c) for c in _db().canciones_de_album(a)]}


def artista_local(d: dict) -> dict:
    return {"canciones": [_local(c) for c in _db().canciones_de_artista(d["nombre"])]}


def playlist(d: dict) -> dict:
    return {"canciones": [_local(c) for c in _db().canciones_de_playlist(int(d["id"]))]}


def crear_playlist(d: dict) -> dict:
    pid = _db().crear_playlist(d["nombre"])
    if d.get("db_ids"):
        _db().agregar_a_playlist(pid, [int(i) for i in d["db_ids"]])
    return {"id": pid}


def agregar_a_playlist(d: dict) -> dict:
    return {"agregadas": _db().agregar_a_playlist(int(d["id"]), [int(i) for i in d["db_ids"]])}


def quitar_de_playlist(d: dict) -> dict:
    _db().quitar_de_playlist(int(d["id"]), [int(i) for i in d["db_ids"]])
    return {}


def borrar_playlist(d: dict) -> dict:
    _db().borrar_playlist(int(d["id"]))
    return {}


def reproduccion(d: dict) -> dict:
    c = _db().cancion_por_ruta(Path(d["ruta"]))
    _db().registrar("reproduccion", Path(d["ruta"]), c.artista if c else "", c.titulo if c else Path(d["ruta"]).stem)
    return {}


def previa(d: dict) -> dict:
    return {"ruta": str(explorar.previa(d["id"]))}


def letra(d: dict) -> dict:
    l = letras.obtener_letra(Path(d["ruta"]), d.get("titulo", ""), d.get("artista", ""), d.get("album", ""))
    return {"tipo": l.tipo, "lineas": l.lineas, "fuente": l.fuente}


# ---------- Descargas ----------

class _Gestor:
    """Cola de descargas con varios hilos. Cada cambio se avisa con el evento "descarga"."""

    def __init__(self):
        self.trabajos: dict[str, dict] = {}
        self.pool: ThreadPoolExecutor | None = None
        self.cancelados: set[str] = set()

    def _pool(self) -> ThreadPoolExecutor:
        if self.pool is None:
            self.pool = ThreadPoolExecutor(max_workers=int(_ajustes().get("descargas_simultaneas", 2)))
        return self.pool

    def _avisar(self, tid: str, **cambios):
        t = self.trabajos[tid]
        t.update(cambios)
        emitir("descarga", {"trabajo": t})

    def agregar(self, entrada: descargas.Entrada, coleccion: str) -> dict:
        tid = uuid.uuid4().hex[:10]
        self.trabajos[tid] = {"id": tid, "titulo": entrada.titulo, "artista": entrada.artista,
                              "portada": entrada.miniatura, "estado": "cola", "pct": 0, "creado": time.time()}
        existente = _db().buscar_existente(entrada.artista, entrada.titulo, entrada.duracion)
        if existente:
            self._avisar(tid, estado="existe", ruta=str(existente.ruta))
            return self.trabajos[tid]
        self._pool().submit(self._bajar, tid, entrada, coleccion)
        emitir("descarga", {"trabajo": self.trabajos[tid]})
        return self.trabajos[tid]

    def _bajar(self, tid: str, entrada: descargas.Entrada, coleccion: str):
        aj = _ajustes()
        formato = descargas.FORMATOS[min(int(aj.get("formato", 2)), len(descargas.FORMATOS) - 1)]
        d = descargas.Descargador(str(plataforma.carpeta_musica()), formato, not aj.get("por_artista", True), coleccion)
        ultimo = [0.0]

        def progreso(estado, pct, vel, eta):
            if time.monotonic() - ultimo[0] > 0.4 or pct >= 100:  # no saturar la interfaz
                ultimo[0] = time.monotonic()
                self._avisar(tid, estado="descargando" if estado == "Descargando" else "buscando", pct=pct,
                             velocidad=vel or 0)

        try:
            res = d.descargar(entrada, progreso, lambda: tid in self.cancelados)
            ruta = Path(res.ruta)
            if aj.get("musicbrainz", True):
                self._avisar(tid, estado="etiquetando", pct=100)
                datos = biblioteca.leer_archivo(ruta)
                try:
                    musicbrainz.completar(ruta, datos["titulo"], datos["artista"], datos["duracion"], datos["album"])
                except Exception:
                    pass
            _db().indexar(ruta)
            c = _db().cancion_por_ruta(ruta)
            if c:
                _db().registrar("descarga", ruta, c.artista, c.titulo)
            self._avisar(tid, estado="listo", pct=100, ruta=str(ruta), cancion=_local(c) if c else None)
        except descargas.Cancelado:
            self._avisar(tid, estado="cancelado")
        except Exception as e:
            self._avisar(tid, estado="error", error=str(e) or type(e).__name__)


_gestor = _Gestor()


def descargar(d: dict) -> dict:
    """Recibe canciones de YouTube Music ({"canciones": [...]}) o un link de playlist/álbum ({"url": ...})."""
    if d.get("url"):
        col = descargas.obtener_coleccion(d["url"])
        trabajos = [_gestor.agregar(e, col.titulo) for e in col.entradas]
        return {"coleccion": col.titulo, "trabajos": trabajos}
    trabajos = []
    for i, c in enumerate(d.get("canciones", []), start=1):
        r = explorar.ResultadoCancion(c["id"], c["titulo"], c["artista"], c.get("album", ""),
                                      c.get("duracion"), c.get("portada"))
        trabajos.append(_gestor.agregar(explorar.a_entrada(r, i), d.get("coleccion") or "YouTube Music"))
    return {"trabajos": trabajos}


def descargas_(d: dict) -> dict:
    return {"trabajos": sorted(_gestor.trabajos.values(), key=lambda t: -t["creado"])}


def cancelar_descarga(d: dict) -> dict:
    _gestor.cancelados.add(d["id"])
    return {}


def limpiar_descargas(d: dict) -> dict:
    for tid in [t for t, v in _gestor.trabajos.items() if v["estado"] in ("listo", "existe", "error", "cancelado")]:
        del _gestor.trabajos[tid]
    return {}


# ---------- Jams ----------

def jam_crear(d: dict) -> dict:
    """Abre un jam en esta máquina; devuelve puerto, código y el cliente del anfitrión."""
    import sys
    from . import jam
    return jam.crear(d.get("nombre") or "WaveDrop", d.get("modo", "anfitrion"), sys.modules[__name__])


def jam_cerrar(d: dict) -> dict:
    from . import jam
    jam.cerrar()
    return {}


def jam_buscar(d: dict) -> dict:
    """Busca jams anunciados en la red local (tarda unos segundos)."""
    from . import jam
    return {"jams": jam.buscar(float(d.get("segundos", 3)))}


# ---------- Entrada ----------

FUNCIONES = {
    "iniciar": iniciar, "ajustes": ajustes, "guardar_ajustes": guardar_ajustes,
    "inicio": inicio, "recomendaciones": recomendaciones,
    "buscar": buscar, "album": album, "artista": artista,
    "biblioteca": biblioteca_, "album_local": album_local, "artista_local": artista_local,
    "playlist": playlist, "crear_playlist": crear_playlist, "agregar_a_playlist": agregar_a_playlist,
    "quitar_de_playlist": quitar_de_playlist, "borrar_playlist": borrar_playlist,
    "reproduccion": reproduccion, "previa": previa, "letra": letra,
    "descargar": descargar, "descargas": descargas_, "cancelar_descarga": cancelar_descarga,
    "limpiar_descargas": limpiar_descargas,
    "jam_crear": jam_crear, "jam_cerrar": jam_cerrar, "jam_buscar": jam_buscar,
}


def despachar(funcion: str, datos_json: str, contexto_json: str = "{}", emisor=None) -> str:
    if emisor is not None:
        _estado["emisor"] = emisor
    try:
        datos = json.loads(datos_json or "{}")
        if funcion == "iniciar":
            datos = json.loads(contexto_json or "{}") | datos
        return json.dumps({"ok": True, **FUNCIONES[funcion](datos)}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e) or type(e).__name__,
                           "detalle": traceback.format_exc()[-2000:]}, ensure_ascii=False)
