"""API de Misiccord para la interfaz (Tauri). Todo entra por despachar() y sale como JSON.

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
    "carpeta": "",         # dónde guardar las descargas ("" = la carpeta por defecto de cada sistema)
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
        _estado["musica_app"] = d["musica"]
        plataforma.configurar(d["datos"], d["musica"], d["cache"], d.get("libs"))
        elegida = _ajustes().get("carpeta")
        if elegida:
            try:
                _probar_carpeta(Path(elegida))
                plataforma.configurar(d["datos"], elegida, d["cache"], d.get("libs"))
            except OSError:
                pass  # la carpeta elegida ya no existe o no se puede escribir: se usa la de siempre
        if _estado["db"] is None:
            _estado["db"] = biblioteca.Biblioteca()
        _db().agregar_carpeta(plataforma.carpeta_musica())
    threading.Thread(target=_escanear, daemon=True).start()
    return {"ajustes": _ajustes(), "android": plataforma.es_android(), "ffmpeg": plataforma.hay_ffmpeg(),
            "js": list(plataforma.js_runtimes().keys()), "total": _db().total()}


def _escanear():
    try:
        nuevas, quitadas = _db().escanear()
        emitir("biblioteca", {"nuevas": nuevas, "quitadas": quitadas, "total": _db().total()})
    except Exception as e:
        emitir("error", {"donde": "escaneo", "mensaje": str(e)})


def _probar_carpeta(ruta: Path) -> None:
    """Lanza OSError si no se puede crear o escribir en la carpeta."""
    ruta.mkdir(parents=True, exist_ok=True)
    prueba = ruta / ".wavedrop-prueba"
    prueba.write_text("ok", encoding="utf-8")
    prueba.unlink()


def _carpetas_sugeridas() -> list[dict]:
    app = _estado.get("musica_app") or str(plataforma.carpeta_musica())
    if plataforma.es_android():
        return [{"ruta": app, "nombre": "Carpeta de la app", "detalle": "Solo Misiccord la ve; se borra si desinstalas"},
                {"ruta": "/storage/emulated/0/Music/Misiccord", "nombre": "Música del teléfono",
                 "detalle": "Tus otras apps de música también la ven"}]
    return [{"ruta": app, "nombre": "Música / Misiccord", "detalle": "La carpeta por defecto"}]


def ajustes(d: dict) -> dict:
    return {"ajustes": _ajustes(), "carpeta_actual": str(plataforma.carpeta_musica()),
            "carpetas": _carpetas_sugeridas(), "android": plataforma.es_android()}


def guardar_ajustes(d: dict) -> dict:
    if "carpeta" in d and d["carpeta"]:
        nueva = Path(d["carpeta"])
        try:
            _probar_carpeta(nueva)
        except OSError as e:
            raise RuntimeError(f"No se puede guardar en esa carpeta ({e.strerror or e})") from e
        plataforma._config["musica"] = str(nueva)
        _db().agregar_carpeta(nueva)
        threading.Thread(target=_escanear, daemon=True).start()
    _ajustes().update({k: v for k, v in d.items() if k in AJUSTES_POR_DEFECTO})
    _ruta_ajustes().write_text(json.dumps(_ajustes(), ensure_ascii=False), encoding="utf-8")
    return ajustes({})


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


def eliminar_canciones(d: dict) -> dict:
    """Borra canciones del dispositivo y de todos lados: biblioteca, playlists, historial, jam y Android.

    Recibe {"db_ids": [...]}, {"album": {nombre, grupo}} o {"artista": nombre}.
    """
    db = _db()
    if d.get("album"):
        al = d["album"]
        canciones = db.canciones_de_album(biblioteca.Album(al["nombre"], al.get("artista", ""), "", 0, Path(), al.get("grupo", "")))
    elif d.get("artista"):
        canciones = db.canciones_de_artista(d["artista"])
    else:
        canciones = db.canciones_por_ids([int(i) for i in d.get("db_ids") or []])
    if not canciones:
        return {"eliminadas": 0, "rutas": [], "fallidas": []}

    raiz = plataforma.carpeta_musica().resolve()
    borradas, fallidas = [], []
    for c in canciones:
        try:
            c.ruta.unlink(missing_ok=True)
            borradas.append(c)
        except OSError as e:
            fallidas.append({"titulo": c.titulo, "error": str(e)})
            continue
        plataforma.archivo_nuevo(c.ruta)  # Android: escanear una ruta que ya no existe la quita de MediaStore
        # Carpetas de artista/álbum que quedaron vacías (solo dentro de la carpeta de música de la app)
        carpeta = c.ruta.parent.resolve()
        while raiz in carpeta.parents:
            try:
                restos = [p for p in carpeta.iterdir() if p.name.lower() not in ("cover.jpg", "folder.jpg", "desktop.ini")]
                if restos:
                    break
                for p in carpeta.iterdir():
                    p.unlink()
                carpeta.rmdir()
            except OSError:
                break
            carpeta = carpeta.parent

    db.olvidar(borradas)
    rutas = [str(c.ruta) for c in borradas]
    from . import jam
    jam.olvidar_rutas(set(rutas))
    emitir("biblioteca", {"nuevas": 0, "quitadas": len(borradas), "total": db.total()})
    return {"eliminadas": len(borradas), "rutas": rutas, "fallidas": fallidas}


def reproduccion(d: dict) -> dict:
    c = _db().cancion_por_ruta(Path(d["ruta"]))
    _db().registrar("reproduccion", Path(d["ruta"]), c.artista if c else "", c.titulo if c else Path(d["ruta"]).stem)
    return {}


def previa(d: dict) -> dict:
    """Audio de una canción que no tienes: de la caché si ya sonó completa; si no, un flujo que suena al instante.
    Con completa=True se baja entera primero (respaldo si el flujo falla)."""
    from . import flujo
    cache = explorar.carpeta_cache()
    guardada = next((p for p in sorted(cache.glob(f"{d['id']}.*")) if p.suffix.lower() in (".m4a", ".webm", ".opus", ".mp3")), None)
    if guardada:
        guardada.touch()
        return {"ruta": str(guardada)}
    if d.get("completa"):
        return {"ruta": str(explorar.previa(d["id"]))}
    return {"url": flujo.url(d["id"])}


def precargar(d: dict) -> dict:
    """Deja listas en segundo plano las canciones en pantalla para que al tocarlas suenen al instante."""
    from . import flujo
    flujo.precargar([str(i) for i in d.get("ids") or []][:10])
    return {}


def letra(d: dict) -> dict:
    # Las que suenan en línea no tienen archivo: su .lrc se guarda en la caché de previas
    ruta = Path(d["ruta"]) if d.get("ruta") else explorar.carpeta_cache() / f"{d['id']}.letra"
    l = letras.obtener_letra(ruta, d.get("titulo", ""), d.get("artista", ""), d.get("album", ""), d.get("duracion"))
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
            plataforma.archivo_nuevo(ruta)
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
    return jam.crear(d.get("nombre") or "Misiccord", d.get("modo", "anfitrion"), sys.modules[__name__])


def jam_cerrar(d: dict) -> dict:
    from . import jam
    jam.cerrar()
    return {}


def jam_subir(d: dict) -> dict:
    """Invitado: sube al anfitrión una canción que tiene en su dispositivo para que entre a la cola."""
    import urllib.parse
    import requests
    ruta = Path(d["ruta"])
    if not ruta.exists():
        raise RuntimeError("No encontré el archivo de esa canción")
    meta = {"titulo": d.get("titulo") or ruta.stem, "artista": d.get("artista", ""), "album": d.get("album", ""),
            "duracion": d.get("duracion"), "ext": ruta.suffix.lower()}
    with open(ruta, "rb") as f:
        r = requests.post(f"{d['base']}/subir", data=f, timeout=180, headers={
            "X-Codigo": d["codigo"], "X-Cliente": d["cliente"], "Content-Type": "application/octet-stream",
            "Content-Length": str(ruta.stat().st_size), "X-Meta": urllib.parse.quote(json.dumps(meta))})
    cuerpo = r.json()
    if not r.ok:
        raise RuntimeError(cuerpo.get("error") or f"El anfitrión respondió {r.status_code}")
    return cuerpo


def jam_internet(d: dict) -> dict:
    """Anfitrión: abre (activar=True) o cierra el jam a internet con un túnel de Cloudflare."""
    from . import jam, tunel
    if not d.get("activar"):
        tunel.cerrar()
        return {"url": None}
    if not tunel.disponible():
        raise RuntimeError("Este dispositivo no puede abrir el jam a internet (actualiza Misiccord)")
    puerto = jam._actual["puerto"]
    if not puerto:
        raise RuntimeError("No hay un jam abierto")
    return {"url": tunel.abrir(puerto, lambda pct: emitir("jam_internet", {"pct": pct}))}


def jam_qr(d: dict) -> dict:
    """QR (SVG) y link para unirse. Es una página que abre Misiccord sola (misiccord://jam?...), así que
    funciona igual al escanearlo con la cámara del teléfono, desde la app o al tocarlo en un chat.
    Los datos van después de "#": el navegador no se los manda al servidor de la página."""
    import urllib.parse
    import qrcode
    import qrcode.image.svg
    datos = {"ip": d["ip"], "puerto": d["puerto"], "codigo": d["codigo"], "nombre": d.get("nombre", "")}
    if d.get("url"):
        datos["url"] = d["url"]  # por internet: los de fuera usan esta; los de la red pueden seguir con la IP
    texto = "https://accor-dium.github.io/misiccord/jam/#" + urllib.parse.urlencode(datos)
    imagen = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return {"svg": imagen.to_string(encoding="unicode"), "texto": texto}


def jam_buscar(d: dict) -> dict:
    """Busca jams anunciados en la red local (tarda unos segundos)."""
    from . import jam
    return {"jams": jam.buscar(float(d.get("segundos", 3)))}


# ---------- Actualizaciones (Android) ----------

def actualizacion_descargar(d: dict) -> dict:
    """Baja el APK de una versión nueva a la caché, avisando el avance con el evento "actualizacion"."""
    import requests
    destino = plataforma.carpeta_cache() / "actualizacion" / "Misiccord.apk"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(d["url"], stream=True, timeout=60, allow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        bajado, ultimo = 0, 0.0
        with open(destino, "wb") as f:
            for bloque in r.iter_content(256 * 1024):
                f.write(bloque)
                bajado += len(bloque)
                if time.monotonic() - ultimo > 0.4:
                    ultimo = time.monotonic()
                    emitir("actualizacion", {"pct": int(bajado * 100 / total) if total else 0})
    emitir("actualizacion", {"pct": 100})
    return {"ruta": str(destino), "mb": round(destino.stat().st_size / 1e6, 1)}


# ---------- Entrada ----------

FUNCIONES = {
    "iniciar": iniciar, "ajustes": ajustes, "guardar_ajustes": guardar_ajustes,
    "inicio": inicio, "recomendaciones": recomendaciones,
    "buscar": buscar, "album": album, "artista": artista,
    "biblioteca": biblioteca_, "album_local": album_local, "artista_local": artista_local,
    "playlist": playlist, "crear_playlist": crear_playlist, "agregar_a_playlist": agregar_a_playlist,
    "quitar_de_playlist": quitar_de_playlist, "borrar_playlist": borrar_playlist,
    "eliminar_canciones": eliminar_canciones,
    "reproduccion": reproduccion, "previa": previa, "precargar": precargar, "letra": letra,
    "descargar": descargar, "descargas": descargas_, "cancelar_descarga": cancelar_descarga,
    "limpiar_descargas": limpiar_descargas,
    "jam_crear": jam_crear, "jam_cerrar": jam_cerrar, "jam_buscar": jam_buscar, "jam_qr": jam_qr,
    "jam_subir": jam_subir, "jam_internet": jam_internet, "actualizacion_descargar": actualizacion_descargar,
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
