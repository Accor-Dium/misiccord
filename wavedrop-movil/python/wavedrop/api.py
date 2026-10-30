"""API de Misiccord para la interfaz (Tauri). Todo entra por despachar() y sale como JSON.

- Android: Kotlin (PythonPlugin) llama a despachar(funcion, datos, contexto, emisor).
- Windows: el servicio local hará lo mismo (siguiente etapa).

Los avisos que llegan después (progreso de descargas, recomendaciones listas) se mandan con
emitir(tipo, datos), que en Android llama a emisor.emitir(json) y llega a la interfaz como evento.
"""
import hashlib
import json
import os
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from . import biblioteca, descargas, etiquetas, explorar, idioma, letras, musicbrainz, plataforma, romanizar, traduccion
from .idioma import t as _t

_estado = {"db": None, "emisor": None, "ajustes": None}
_candado = threading.RLock()

AJUSTES_POR_DEFECTO = {
    "fundido": 6,          # segundos de fundido entre canciones (0 = sin fundido)
    "formato": 2,          # índice en descargas.FORMATOS (solo aplica con ffmpeg, en Windows)
    "musicbrainz": True,   # completar datos al descargar
    "por_artista": True,   # carpetas por artista
    "descargas_simultaneas": 2,
    "carpeta": "",         # dónde guardar las descargas ("" = la carpeta por defecto de cada sistema)
    "video_ver": False,    # mostrar el interruptor de video sobre la carátula del reproductor
    "video_descargar": False,  # bajar también el videoclip (mp4) al descargar una canción
    "letra_traducir_a": "",  # idioma al que se traducen las letras ("" = no traducir)
    "letra_romanizar": True,  # mostrar la romanización de letras en coreano, japonés (kana), ruso…
    "eq_activo": False,    # ecualizador (Web Audio): apagado, el audio va directo como siempre
    "eq_bandas": [0, 0, 0, 0, 0],  # dB de cada banda: 60 Hz, 230 Hz, 910 Hz, 3.6 kHz, 14 kHz
}


# ---------- Trabajo en segundo plano (Android) ----------
# Descargas, la actualización, un jam abierto... se anotan aquí y el resumen sale como evento "fondo".
# En Android ese evento lo lee PythonPlugin.kt (sin pasar por la interfaz, que Android pausa con la pantalla apagada)
# para mantener un servicio en primer plano con una notificación de progreso: sin él, Android duerme la app.
_fondo = {"tareas": {}, "hechas": [], "ultimo": (0, "", "", -1, 0.0)}
_fondo_candado = threading.Lock()


def _fondo_actualizar(clave: str, texto: str | None, pct: int = -1, detalle: str = "", listo: str | None = None) -> None:
    """Anota (o con texto=None quita) un trabajo largo. `listo` dice qué terminó, para el aviso final."""
    if not plataforma.es_android():
        return
    with _fondo_candado:
        if texto is None:
            if _fondo["tareas"].pop(clave, None) is not None and listo:
                _fondo["hechas"].append(listo)
        else:
            _fondo["tareas"][clave] = {"texto": texto, "pct": pct, "detalle": detalle}
        resumen = _resumen_fondo()
        antes = _fondo["ultimo"]
        ahora = time.monotonic()
        # Con una sola tarea con avance, el texto es solo "40%": cambiar de porcentaje no cuenta como otro mensaje
        texto = "" if resumen["activas"] == 1 and resumen["pct"] >= 0 else resumen["texto"]
        igual = (resumen["activas"], resumen["titulo"], texto) == antes[:3]
        # El avance se manda cada 2 puntos o 2 s: la notificación no necesita más
        if igual and not resumen["fin"] and abs(resumen["pct"] - antes[3]) < 2 and ahora - antes[4] < 2:
            return
        _fondo["ultimo"] = (resumen["activas"], resumen["titulo"], texto, resumen["pct"], ahora)
    emitir("fondo", resumen)


def _resumen_fondo() -> dict:
    tareas = list(_fondo["tareas"].values())
    if not tareas:
        return {"activas": 0, "titulo": "", "texto": "", "pct": -1, "fin": _mensaje_fin()}
    conocidos = [t["pct"] for t in tareas if t["pct"] >= 0]
    pct = sum(conocidos) // len(conocidos) if conocidos else -1
    if len(tareas) == 1:
        t = tareas[0]
        return {"activas": 1, "titulo": t["texto"], "texto": t["detalle"] or (f"{t['pct']}%" if t["pct"] >= 0 else _t("En curso…")),
                "pct": pct, "fin": ""}
    nombres = ", ".join(t["texto"] for t in tareas[:2]) + ("…" if len(tareas) > 2 else "")
    return {"activas": len(tareas), "titulo": _t("{n} tareas en segundo plano", n=len(tareas)), "texto": nombres, "pct": pct, "fin": ""}


def _mensaje_fin() -> str:
    """Lo que se avisa al quedar sin trabajo pendiente (y se vacía la cuenta)."""
    hechas, _fondo["hechas"] = _fondo["hechas"], []
    if "actualizacion" in hechas:
        return _t("Actualización lista: ábrela para instalarla")
    canciones = hechas.count("cancion")
    if canciones:
        return _t("1 canción descargada") if canciones == 1 else _t("{n} canciones descargadas", n=canciones)
    return _t("Video descargado") if "video" in hechas else ""


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
    try:
        version = ruta.stat().st_mtime_ns  # cambia al editar la carátula: así la interfaz no se queda con la vieja
    except OSError:
        version = 0
    destino = plataforma.carpeta_cache() / "portadas" / (hashlib.md5(f"{ruta}|{version}".encode()).hexdigest() + ".jpg")
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
            if datos is None and getattr(f, "pictures", None):  # FLAC guarda la carátula aparte de las etiquetas
                datos = f.pictures[0].data
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
            "album": c.album, "artista_album": c.artista_album, "anio": c.anio, "pista": c.pista, "duracion": c.duracion, "agregada": c.agregada,
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
    idioma.poner(d.get("idioma", "es"))
    with _candado:
        _estado["musica_app"] = d["musica"]
        _estado["volumenes"] = d.get("volumenes") or []  # Android: raíz del almacenamiento interno y de cada tarjeta SD
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


def _escanear(visible: bool = False):
    """visible=True (el usuario agregó una carpeta): también se avisa como trabajo en segundo plano."""
    def progreso(n):
        emitir("escaneo", {"revisadas": n})
        if visible:
            _fondo_actualizar("escaneo", _t("Leyendo tu música ({n})", n=n))

    try:
        if visible:
            _fondo_actualizar("escaneo", _t("Leyendo tu música"))
        nuevas, quitadas = _db().escanear(progreso=progreso)
        emitir("biblioteca", {"nuevas": nuevas, "quitadas": quitadas, "total": _db().total()})
    except Exception as e:
        emitir("error", {"donde": "escaneo", "mensaje": str(e)})
    finally:
        if visible:
            _fondo_actualizar("escaneo", None)


def _probar_carpeta(ruta: Path) -> None:
    """Lanza OSError si no se puede crear o escribir en la carpeta."""
    ruta.mkdir(parents=True, exist_ok=True)
    prueba = ruta / ".wavedrop-prueba"
    prueba.write_text("ok", encoding="utf-8")
    prueba.unlink()


def _carpetas_sugeridas() -> list[dict]:
    app = _estado.get("musica_app") or str(plataforma.carpeta_musica())
    if plataforma.es_android():
        opciones = [{"ruta": app, "nombre": "Carpeta de la app", "detalle": "Solo Misiccord la ve; se borra si desinstalas"},
                    {"ruta": f"{INTERNO}/Music/Misiccord", "nombre": "Música del teléfono",
                     "detalle": "Tus otras apps de música también la ven"}]
        for v in volumenes():
            if v["ruta"] == INTERNO:
                continue
            opciones.append({"ruta": f"{v['ruta']}/Music/Misiccord", "nombre": f"Música en la {v['nombre'][0].lower()}{v['nombre'][1:]}",
                             "detalle": "En la tarjeta; tus otras apps de música también la ven"})
            # La carpeta de la app en la tarjeta se puede usar sin el permiso de todos los archivos
            propia = app.replace(INTERNO, v["ruta"], 1)
            if propia != app and os.path.isdir(os.path.dirname(propia)):
                opciones.append({"ruta": propia, "nombre": f"Carpeta de la app en la {v['nombre'][0].lower()}{v['nombre'][1:]}",
                                 "detalle": "No pide permisos; se borra si desinstalas"})
        return opciones
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


def poner_idioma(d: dict) -> dict:
    """La interfaz avisa su idioma ("es", "en") al arrancar y al cambiarlo en Ajustes."""
    idioma.poner(d.get("idioma", "es"))
    return {"idioma": idioma.actual()}


def _seccion_yt(s: dict) -> dict:
    return {**s, "canciones": [_en_linea(c) for c in s["canciones"]]}


def inicio_en_linea(d: dict) -> dict:
    """Lo general de YouTube Music para Inicio: sus secciones y los estados de ánimo (para los chips de arriba)."""
    forzar = bool(d.get("forzar"))
    res: dict = {"secciones": [], "estados": []}
    try:
        res["secciones"] = [_seccion_yt(s) for s in explorar.inicio_yt(forzar)]
    except Exception as e:
        res["error"] = str(e)
    try:
        res["estados"] = explorar.estados(forzar)
    except Exception:
        pass
    return res


def estado_animo(d: dict) -> dict:
    """Playlists de un estado de ánimo o género (los `params` vienen de `inicio_en_linea`)."""
    return {"tarjetas": explorar.playlists_de_estado(d["params"])}


def explorar_(d: dict) -> dict:
    e = explorar.explorar()
    return {**e, "tendencia": [_en_linea(c) for c in e["tendencia"]], "estados": explorar.estados()}


def playlist_yt(d: dict) -> dict:
    p = explorar.playlist(d["id"])
    p["canciones"] = [_en_linea(c) for c in p["canciones"]]
    return {"album": p}


def radio(d: dict) -> dict:
    """Canciones parecidas a una (su "radio" en YouTube Music). Si es tuya y no trae id, se busca por nombre."""
    vid = d.get("id")
    if not vid:
        base = explorar.buscar_id(d.get("artista", ""), d.get("titulo", ""))
        if base is None:
            raise RuntimeError("No encontré esa canción en YouTube Music")
        vid = base.video_id
    return {"canciones": [_en_linea(c) for c in explorar.radio(vid)]}


# ---------- Compartir y exportar (PC) ----------

def destinos_exportar(d: dict) -> dict:
    from . import exportar
    return {"destinos": exportar.destinos()}


def exportar_canciones(d: dict) -> dict:
    """Copia canciones a una USB o carpeta en segundo plano. Avisa el avance con el evento "exportar"."""
    from . import exportar
    grupos, destino = d["grupos"], d["destino"]
    if not Path(destino).is_dir():
        raise RuntimeError("No encuentro esa carpeta o memoria")
    nombre = d.get("nombre") or destino

    def trabajo():
        def avance(hechas, total):
            emitir("exportar", {"estado": "copiando", "hechas": hechas, "total": total, "destino": nombre})
        try:
            r = exportar.copiar(grupos, destino, avance)
            emitir("exportar", {"estado": "listo", "destino": nombre, **r})
        except OSError as e:
            emitir("exportar", {"estado": "error", "destino": nombre, "error": e.strerror or str(e)})

    threading.Thread(target=trabajo, daemon=True).start()
    return {"total": sum(len(g["rutas"]) for g in grupos)}


def copiar_archivos(d: dict) -> dict:
    from . import exportar
    exportar.al_portapapeles(d["rutas"])
    return {}


def mostrar_archivo(d: dict) -> dict:
    from . import exportar
    exportar.mostrar(d["ruta"])
    return {}


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
    carpeta = d.get("carpeta", "")  # "" = toda la biblioteca
    return {
        "canciones": [_local(c) for c in db.canciones(d.get("q", ""), carpeta)],
        "albumes": [_album_local(a) for a in db.albumes(carpeta)],
        "artistas": [{"nombre": n, "canciones": k} for n, k in db.artistas(carpeta)],
        "playlists": [{"id": i, "nombre": n, "canciones": k} for i, n, k in db.playlists()],
        "me_gusta": len(db.lista_me_gusta()),
    }


def carpetas_biblioteca(d: dict) -> dict:
    """Carpetas que Misiccord escucha para armar la biblioteca (con sus subcarpetas)."""
    descargas_ = plataforma.carpeta_musica()
    cuentas = _db().canciones_por_carpeta()
    return {"carpetas": [{"ruta": r, "canciones": n, "existe": Path(r).is_dir(), "descargas": Path(r) == descargas_}
                         for r, n in cuentas.items()],
            "android": plataforma.es_android()}


def agregar_carpeta_biblioteca(d: dict) -> dict:
    """Suma una carpeta de música que ya tienes (solo lectura: no hace falta poder escribir en ella)."""
    ruta = Path(d["ruta"])
    if not ruta.is_dir():
        raise RuntimeError("Esa carpeta no existe")
    try:
        next(os.scandir(ruta), None)
    except OSError as e:
        raise RuntimeError(f"No se puede leer esa carpeta ({e.strerror or e})") from e
    _db().agregar_carpeta(ruta)
    _fondo_actualizar("escaneo", _t("Leyendo tu música"))  # antes de volver: la app sigue en primer plano
    threading.Thread(target=_escanear, kwargs={"visible": True}, daemon=True).start()
    return carpetas_biblioteca({})


def quitar_carpeta_biblioteca(d: dict) -> dict:
    """Deja de escuchar una carpeta: las canciones salen de la biblioteca, los archivos no se tocan."""
    ruta = Path(d["ruta"])
    if ruta == plataforma.carpeta_musica():
        raise RuntimeError("Esa es la carpeta de descargas; cámbiala en Ajustes")
    _db().quitar_carpeta(ruta)
    emitir("biblioteca", {"nuevas": 0, "quitadas": 0, "total": _db().total()})
    return carpetas_biblioteca({})


INTERNO = "/storage/emulated/0"


def volumenes() -> list[dict]:
    """Almacenamientos del teléfono: el interno y cada tarjeta SD (/storage/XXXX-XXXX).

    Kotlin los manda al iniciar (getExternalFilesDirs); además se mira /storage por si alguno no vino.
    """
    rutas = [INTERNO, *(_estado.get("volumenes") or [])]
    try:
        rutas += [f"/storage/{n}" for n in sorted(os.listdir("/storage")) if re.fullmatch(r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}", n)]
    except OSError:
        pass
    vistos, encontrados = set(), []
    for r in rutas:
        r = r.rstrip("/")
        if r in vistos or not os.path.isdir(r):
            continue
        vistos.add(r)
        encontrados.append({"ruta": r, "nombre": "Almacenamiento interno" if r == INTERNO else f"Tarjeta SD ({Path(r).name})"})
    return encontrados


def subcarpetas(d: dict) -> dict:
    """Para el selector de carpetas de Android (el selector del sistema no sirve para rutas reales).

    Sin ruta: los almacenamientos (interno y tarjetas SD); si solo hay uno, se entra directo.
    "padre" es "" para volver a esa lista y None cuando no hay a dónde subir.
    """
    raices = volumenes()
    if not d.get("ruta"):
        if len(raices) != 1:
            return {"ruta": "", "padre": None, "carpetas": raices}
        d = {"ruta": raices[0]["ruta"]}
    ruta = Path(d["ruta"])
    try:
        hijas = sorted((p for p in ruta.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.lower())
    except OSError as e:
        raise RuntimeError(f"No se puede abrir esa carpeta ({e.strerror or e})") from e
    if any(str(ruta) == r["ruta"] for r in raices):
        padre = "" if len(raices) > 1 else None  # de la raíz de un almacenamiento se sube a la lista de almacenamientos
    else:
        padre = str(ruta.parent) if ruta.parent != ruta else None
    return {"ruta": str(ruta), "padre": padre, "carpetas": [{"nombre": p.name, "ruta": str(p)} for p in hijas]}


# ---------- Información y etiquetas de una canción ----------

def info_cancion(d: dict) -> dict:
    """Todo lo que se sabe de una canción. Si está descargada: etiquetas editables, datos técnicos e historial.
    Si es una vista previa: solo lo que trae YouTube Music (no se puede editar)."""
    if d.get("ruta"):
        ruta = Path(d["ruta"])
        r = etiquetas.leer(ruta)
        r["tecnico"].update(_db().historial_de(ruta))
        r["portada"] = portada_local(ruta)
        r["descargada"] = True
        return r
    campos = dict.fromkeys(etiquetas.CAMPOS, "")
    campos.update({"titulo": d.get("titulo", ""), "artista": d.get("artista", ""), "album": d.get("album", ""),
                   "anio": str(d.get("anio") or "")})
    tecnico = {"fuente": "YouTube Music", "duracion": d.get("duracion")}
    if d.get("id"):
        tecnico["enlace"] = f"https://music.youtube.com/watch?v={d['id']}"
    return {"campos": campos, "tecnico": tecnico, "editable": False, "descargada": False, "portada": d.get("portada")}


def _tras_editar(ruta: Path) -> dict:
    _portadas.pop(str(ruta.parent) + "|" + ruta.stem, None)
    _db().indexar(ruta)
    plataforma.archivo_nuevo(ruta)  # Android: que las otras apps de música vean los datos nuevos
    c = _db().cancion_por_ruta(ruta)
    emitir("biblioteca", {"nuevas": 0, "quitadas": 0, "total": _db().total()})
    return {"cancion": _local(c) if c else None}


def guardar_etiquetas(d: dict) -> dict:
    ruta = Path(d["ruta"])
    etiquetas.escribir(ruta, d.get("campos") or {})
    return _tras_editar(ruta)


def cambiar_portada(d: dict) -> dict:
    """Recibe la imagen en base64 (la interfaz la lee con un <input type="file">, que funciona igual en el cel)."""
    import base64
    ruta = Path(d["ruta"])
    texto = d.get("imagen") or ""
    try:
        datos = base64.b64decode(texto.split(",", 1)[-1])  # acepta "data:image/png;base64,..." o solo el base64
    except ValueError as e:
        raise RuntimeError("No pude leer la imagen") from e
    etiquetas.poner_portada(ruta, datos)
    return _tras_editar(ruta)


# ---------- Me gusta ----------

def me_gusta_es(d: dict) -> dict:
    return {"gusta": _db().me_gusta(d.get("artista", ""), d.get("titulo", ""))}


def me_gusta_alternar(d: dict) -> dict:
    """Pone o quita "Me gusta". Sirve igual para canciones descargadas y vistas previas (se guarda su id de YouTube
    Music para poder escucharla o descargarla después aunque no la tengas)."""
    db = _db()
    artista, titulo = d.get("artista", ""), d.get("titulo", "")
    if db.me_gusta(artista, titulo):
        db.quitar_me_gusta(artista, titulo)
        gusta = False
    else:
        # Las vistas previas traen portada de internet; las descargadas, un archivo de la caché que puede cambiar
        portada = d.get("portada") if str(d.get("portada") or "").startswith("http") else None
        db.poner_me_gusta({"titulo": titulo, "artista": artista, "album": d.get("album"), "duracion": d.get("duracion"),
                           "portada": portada, "video_id": d.get("id")})
        gusta = True
        if not d.get("id"):
            # Una canción de tus carpetas: se busca su id en segundo plano, por si algún día borras el archivo
            def completar():
                try:
                    r = explorar.buscar_id(artista, titulo)
                    if r:
                        db._w("UPDATE me_gusta SET video_id = ? WHERE clave = ? AND video_id IS NULL",
                              (r.video_id, biblioteca.clave(artista, titulo)))
                except Exception:
                    pass
            threading.Thread(target=completar, daemon=True).start()
    emitir("me_gusta", {"titulo": titulo, "artista": artista, "gusta": gusta})
    return {"gusta": gusta}


def me_gusta(d: dict) -> dict:
    """Tu lista de Me gusta, la más nueva primero. Las que tienes descargadas suenan desde el archivo; las demás en línea
    (y se pueden descargar). Las que no tienes y no traen id de YouTube Music salen como no disponibles."""
    db = _db()
    canciones = []
    for r in db.lista_me_gusta():
        local = db.buscar_existente(r["artista"] or "", r["titulo"] or "", r["duracion"])
        if local:
            canciones.append(_local(local) | {"id": r["video_id"]})
        else:
            canciones.append({"local": False, "id": r["video_id"], "titulo": r["titulo"], "artista": r["artista"],
                              "album": r["album"] or "", "duracion": r["duracion"], "portada": r["portada"], "ruta": None,
                              "disponible": bool(r["video_id"])})
    return {"canciones": canciones}


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
            c.ruta.with_suffix(".mp4").unlink(missing_ok=True)  # su videoclip descargado, si lo tiene
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
    """Cuenta una reproducción para el historial, las recomendaciones y las estadísticas.
    Las vistas previas (sin archivo) también cuentan, como "yt:<id>"."""
    if d.get("ruta"):
        c = _db().cancion_por_ruta(Path(d["ruta"]))
        _db().registrar("reproduccion", Path(d["ruta"]), c.artista if c else "", c.titulo if c else Path(d["ruta"]).stem,
                        d.get("duracion"))
    elif d.get("id"):
        _db().registrar("reproduccion", f"yt:{d['id']}", d.get("artista", ""), d.get("titulo", ""),
                        d.get("duracion"), d.get("portada"))
    return {}


def estadisticas(d: dict) -> dict:
    """Lo que escuchaste en el último mes (dias=30) o los últimos 3 meses (dias=90), con porcentajes."""
    dias = 90 if int(d.get("dias", 30)) >= 90 else 30
    e = _db().estadisticas(dias)
    for c in e["canciones"]:
        ruta = c.pop("ruta")
        local = _db().cancion_por_ruta(Path(ruta)) if ruta else None
        if local:
            c.update(_local(local))  # con su portada y lista para reproducir
    return e


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


def video(d: dict) -> dict:
    """Imagen del videoclip para verla junto a la canción (sin sonido: el audio sigue siendo el del reproductor).

    Si la canción tiene su video descargado devuelve {"ruta"}; si no, un flujo en vivo {"url"} del clip que se busca
    en YouTube Music (el id de la canción suele ser audio con la portada, no el clip).
    """
    from . import flujo
    if d.get("ruta"):
        descargado = descargas.ruta_video(Path(d["ruta"]))
        if descargado:
            return {"ruta": str(descargado)}
    clip = explorar.buscar_video(d.get("artista", ""), d.get("titulo", ""), d.get("duracion"))
    if not clip:
        raise RuntimeError("No encontré el video de esta canción")
    return {"url": flujo.url(clip, video=True)}


def bajar_video(ruta: Path, titulo: str, artista: str, duracion: float | None,
                cancelado=lambda: False) -> Path:
    """Descarga el videoclip junto a la canción `ruta` (no hace nada si ya está)."""
    existente = descargas.ruta_video(ruta)
    if existente:
        return existente
    clip = explorar.buscar_video(artista, titulo, duracion)
    if not clip:
        raise RuntimeError("No encontré el video de esta canción")
    return descargas.descargar_video(clip, ruta, lambda *a: None, cancelado)


def descargar_video(d: dict) -> dict:
    """Baja el video de una canción que ya tienes. Avisa con el evento "video_descarga" al terminar."""
    ruta = Path(d["ruta"])
    if descargas.ruta_video(ruta):
        return {"estado": "existe"}

    clave = f"video:{ruta}"
    _fondo_actualizar(clave, _t("Video de “{titulo}”", titulo=d.get("titulo", "")))  # antes de volver: la app sigue en primer plano

    def trabajo():
        terminado = None
        try:
            bajar_video(ruta, d.get("titulo", ""), d.get("artista", ""), d.get("duracion"))
            terminado = "video"
            emitir("video_descarga", {"estado": "listo", "titulo": d.get("titulo", ""), "ruta": str(ruta)})
        except Exception as e:
            emitir("video_descarga", {"estado": "error", "titulo": d.get("titulo", ""), "error": str(e) or type(e).__name__})
        finally:
            _fondo_actualizar(clave, None, listo=terminado)

    threading.Thread(target=trabajo, daemon=True).start()
    return {"estado": "descargando"}


def letra(d: dict) -> dict:
    # Las que suenan en línea no tienen archivo: su .lrc se guarda en la caché de previas
    ruta = Path(d["ruta"]) if d.get("ruta") else explorar.carpeta_cache() / f"{d['id']}.letra"
    l = letras.obtener_letra(ruta, d.get("titulo", ""), d.get("artista", ""), d.get("album", ""), d.get("duracion"),
                             d.get("id"))
    textos = [t for _, t in l.lineas]
    cod = romanizar.idioma(textos)
    r = {"tipo": l.tipo, "lineas": l.lineas, "fuente": l.fuente, "idioma": cod, "idioma_nombre": romanizar.NOMBRES.get(cod, "")}
    if cod in romanizar.ROMANIZABLES:
        rom = romanizar.romanizar(textos, cod)
        if any(rom):
            r["romanizacion"] = rom
    return r


def letra_traduccion(d: dict) -> dict:
    """Traducción línea por línea de una letra (MyMemory, con caché)."""
    if not d.get("origen") or d.get("origen") == d.get("destino"):
        return {"traduccion": []}
    return {"traduccion": traduccion.traducir([str(x) for x in d.get("lineas") or []], d["origen"], d["destino"])}


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
        if t["estado"] in ("cola", "buscando", "descargando", "etiquetando"):
            _fondo_actualizar(f"descarga:{tid}", _t("Descargando “{titulo}”", titulo=t["titulo"]), t["pct"] if t["estado"] == "descargando" else -1)
        else:
            _fondo_actualizar(f"descarga:{tid}", None, listo="cancion" if t["estado"] == "listo" else None)

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
            if aj.get("video_descargar"):
                # Se anota antes de dar la canción por lista: así el servicio en segundo plano no se apaga entre las dos
                _fondo_actualizar(f"video:{tid}", _t("Video de “{titulo}”", titulo=entrada.titulo))
            self._avisar(tid, estado="listo", pct=100, ruta=str(ruta), cancion=_local(c) if c else None)
            if aj.get("video_descargar"):
                # La canción ya suena; el video se baja después y avisa aparte (si falla, la canción no se pierde)
                terminado = None
                try:
                    bajar_video(ruta, c.titulo if c else entrada.titulo, c.artista if c else entrada.artista,
                                entrada.duracion, lambda: tid in self.cancelados)
                    terminado = "video"
                    emitir("video_descarga", {"estado": "listo", "titulo": entrada.titulo, "ruta": str(ruta)})
                except descargas.Cancelado:
                    pass
                except Exception as e:
                    emitir("video_descarga", {"estado": "error", "titulo": entrada.titulo, "error": str(e) or type(e).__name__})
                finally:
                    _fondo_actualizar(f"video:{tid}", None, listo=terminado)
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
        return {"coleccion": col.titulo, "trabajos": trabajos, "total": col.total}
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
    r = jam.crear(d.get("nombre") or "Misiccord", d.get("modo", "anfitrion"), sys.modules[__name__])
    _fondo_actualizar("jam", _t("Jam abierto"), detalle=_t("Tus invitados siguen conectados"))
    return r


def jam_cerrar(d: dict) -> dict:
    from . import jam
    jam.cerrar()
    _fondo_actualizar("jam", None)
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
    _fondo_actualizar("actualizacion", _t("Descargando la actualización"), 0)
    terminado = None
    try:
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
                        pct = int(bajado * 100 / total) if total else 0
                        emitir("actualizacion", {"pct": pct})
                        _fondo_actualizar("actualizacion", _t("Descargando la actualización"), pct if total else -1)
        terminado = "actualizacion"
    finally:
        _fondo_actualizar("actualizacion", None, listo=terminado)
    emitir("actualizacion", {"pct": 100})
    return {"ruta": str(destino), "mb": round(destino.stat().st_size / 1e6, 1)}


# ---------- Entrada ----------

FUNCIONES = {
    "iniciar": iniciar, "ajustes": ajustes, "guardar_ajustes": guardar_ajustes,
    "inicio": inicio, "recomendaciones": recomendaciones,
    "buscar": buscar, "album": album, "artista": artista,
    "biblioteca": biblioteca_, "album_local": album_local, "artista_local": artista_local,
    "carpetas_biblioteca": carpetas_biblioteca, "agregar_carpeta_biblioteca": agregar_carpeta_biblioteca,
    "quitar_carpeta_biblioteca": quitar_carpeta_biblioteca, "subcarpetas": subcarpetas,
    "playlist": playlist, "crear_playlist": crear_playlist, "agregar_a_playlist": agregar_a_playlist,
    "quitar_de_playlist": quitar_de_playlist, "borrar_playlist": borrar_playlist,
    "eliminar_canciones": eliminar_canciones, "video": video, "descargar_video": descargar_video,
    "me_gusta": me_gusta, "me_gusta_es": me_gusta_es, "me_gusta_alternar": me_gusta_alternar,
    "info_cancion": info_cancion, "guardar_etiquetas": guardar_etiquetas, "cambiar_portada": cambiar_portada,
    "reproduccion": reproduccion, "estadisticas": estadisticas, "previa": previa, "precargar": precargar, "letra": letra,
    "letra_traduccion": letra_traduccion,
    "descargar": descargar, "descargas": descargas_, "cancelar_descarga": cancelar_descarga,
    "limpiar_descargas": limpiar_descargas,
    "jam_crear": jam_crear, "jam_cerrar": jam_cerrar, "jam_buscar": jam_buscar, "jam_qr": jam_qr,
    "jam_subir": jam_subir, "jam_internet": jam_internet, "actualizacion_descargar": actualizacion_descargar,
    "poner_idioma": poner_idioma, "inicio_en_linea": inicio_en_linea, "estado_animo": estado_animo,
    "explorar": explorar_, "playlist_yt": playlist_yt, "radio": radio,
    "destinos_exportar": destinos_exportar, "exportar_canciones": exportar_canciones,
    "copiar_archivos": copiar_archivos, "mostrar_archivo": mostrar_archivo,
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
