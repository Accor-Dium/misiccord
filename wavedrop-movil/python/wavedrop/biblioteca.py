"""Biblioteca de música: base de datos SQLite con las canciones de tus carpetas, álbumes y playlists.

Se guarda en %LOCALAPPDATA%\\WaveDrop\\biblioteca.db. Las canciones se leen de las carpetas que
elijas (más la de descargas) y se agrupan por las etiquetas de cada archivo.
"""
import os
import re
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import mutagen

EXTENSIONES = {".mp3", ".m4a", ".opus", ".ogg", ".oga", ".flac", ".wav", ".aac", ".wma", ".alac", ".aiff", ".aif"}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS canciones (
    id INTEGER PRIMARY KEY,
    ruta TEXT UNIQUE NOT NULL,
    titulo TEXT, artista TEXT, artista_ppal TEXT, album TEXT, artista_album TEXT,
    anio TEXT, pista INTEGER, genero TEXT, duracion REAL,
    mbid TEXT, clave TEXT, mtime REAL, agregada REAL
);
CREATE INDEX IF NOT EXISTS idx_clave ON canciones(clave);
CREATE INDEX IF NOT EXISTS idx_album ON canciones(album, artista_album);
CREATE TABLE IF NOT EXISTS carpetas (ruta TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS playlists (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL, creada REAL);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,  -- "reproduccion" o "descarga"
    ruta TEXT, artista TEXT, titulo TEXT, fecha REAL
);
CREATE INDEX IF NOT EXISTS idx_eventos ON eventos(tipo, fecha);
CREATE TABLE IF NOT EXISTS playlist_canciones (
    playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    cancion_id INTEGER REFERENCES canciones(id) ON DELETE CASCADE,
    posicion INTEGER,
    PRIMARY KEY (playlist_id, cancion_id)
);
"""


@dataclass
class Cancion:
    id: int
    ruta: Path
    titulo: str
    artista: str
    album: str
    artista_album: str
    anio: str
    pista: int | None
    genero: str
    duracion: float | None
    mbid: str


@dataclass
class Album:
    nombre: str
    artista: str
    anio: str
    canciones: int
    ruta_portada: Path  # una canción del álbum, para sacar la portada
    grupo: str = ""  # artista del álbum tal como viene en las etiquetas ("" si no trae)


# ---------- Comparar canciones ----------

_ENTRE_PARENTESIS = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_FEAT = re.compile(r"\s+(feat\.?|ft\.?|featuring|con)\s+.*$", re.I)


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, sin "(Official Video)", "feat. X" ni signos."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    texto = _ENTRE_PARENTESIS.sub(" ", texto.lower())
    texto = _FEAT.sub("", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def artista_principal(artista: str) -> str:
    return re.split(r",|&| x | y | and |;|/", artista or "", maxsplit=1)[0].strip()


def separar_titulo(titulo: str, artista: str) -> tuple[str, str]:
    """YouTube suele titular "Artista - Canción": devuelve (artista, canción)."""
    if " - " in titulo:
        izq, der = titulo.split(" - ", 1)
        if not artista or normalizar(artista_principal(artista)) in normalizar(izq) or "topic" in artista.lower():
            return izq.strip(), der.strip()
    return artista, titulo


def clave(artista: str, titulo: str) -> str:
    artista, titulo = separar_titulo(titulo, artista)
    return f"{normalizar(artista_principal(artista))}|{normalizar(titulo)}"


# ---------- Leer etiquetas ----------

def _primero(tags, *nombres) -> str:
    for n in nombres:
        v = tags.get(n) if tags else None
        if v:
            return str(v[0]).strip()
    return ""


def leer_archivo(ruta: Path) -> dict:
    datos = {"titulo": ruta.stem, "artista": "", "artista_ppal": "", "album": "", "artista_album": "", "anio": "",
             "pista": None, "genero": "", "duracion": None, "mbid": ""}
    try:
        f = mutagen.File(ruta, easy=True)
    except Exception:
        f = None
    if f is not None:
        if f.info and getattr(f.info, "length", None):
            datos["duracion"] = float(f.info.length)
        t = f.tags
        datos["titulo"] = _primero(t, "title") or ruta.stem
        datos["artista"] = _primero(t, "artist")
        datos["album"] = _primero(t, "album")
        datos["artista_album"] = _primero(t, "albumartist")
        datos["anio"] = _primero(t, "date", "year")[:4]
        genero = _primero(t, "genre")
        datos["genero"] = "" if genero.lower() == "music" else genero  # "Music" lo pone YouTube a todo
        datos["mbid"] = _primero(t, "musicbrainz_trackid")
        pista = _primero(t, "tracknumber").split("/")[0]
        datos["pista"] = int(pista) if pista.isdigit() else None
    if not datos["artista"]:
        # Sin etiquetas: "Artista - Canción.mp3" o la carpeta de arriba
        artista, titulo = separar_titulo(datos["titulo"], "")
        datos["artista"], datos["titulo"] = (artista, titulo) if artista else (ruta.parent.name, datos["titulo"])
    # artista_album queda vacío si el archivo no lo trae: así las pistas de un mismo álbum con distintos
    # intérpretes se agrupan juntas por nombre de álbum
    datos["artista_ppal"] = artista_principal(datos["artista"])
    return datos


# ---------- Base de datos ----------

def ruta_db() -> Path:
    from . import plataforma
    return plataforma.carpeta_datos() / "biblioteca.db"


class Biblioteca:
    def __init__(self, ruta: Path | None = None):
        self.con = sqlite3.connect(str(ruta or ruta_db()), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)
        columnas = {r["name"] for r in self.con.execute("PRAGMA table_info(canciones)")}
        if "artista_ppal" not in columnas:  # bases creadas por una versión anterior
            self.con.execute("ALTER TABLE canciones ADD COLUMN artista_ppal TEXT")
            self.con.execute("UPDATE canciones SET mtime = 0")  # forzar relectura en el próximo escaneo
            self.con.commit()
        self.candado = threading.RLock()

    def _q(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self.candado:
            return self.con.execute(sql, params).fetchall()

    def _w(self, sql: str, params=()) -> int:
        with self.candado:
            cur = self.con.execute(sql, params)
            self.con.commit()
            return cur.lastrowid

    @staticmethod
    def _cancion(r: sqlite3.Row) -> Cancion:
        return Cancion(r["id"], Path(r["ruta"]), r["titulo"] or "", r["artista"] or "", r["album"] or "",
                       r["artista_album"] or "", r["anio"] or "", r["pista"], r["genero"] or "", r["duracion"],
                       r["mbid"] or "")

    # --- Carpetas ---

    def carpetas(self) -> list[Path]:
        return [Path(r["ruta"]) for r in self._q("SELECT ruta FROM carpetas ORDER BY ruta")]

    def agregar_carpeta(self, ruta: Path):
        self._w("INSERT OR IGNORE INTO carpetas(ruta) VALUES (?)", (str(Path(ruta)),))

    def quitar_carpeta(self, ruta: Path):
        prefijo = str(Path(ruta)).rstrip("\\/") + os.sep
        with self.candado:
            self.con.execute("DELETE FROM carpetas WHERE ruta = ?", (str(Path(ruta)),))
            otras = [str(c).rstrip("\\/") + os.sep for c in self.carpetas()]
            for r in self.con.execute("SELECT id, ruta FROM canciones").fetchall():
                if r["ruta"].startswith(prefijo) and not any(r["ruta"].startswith(o) for o in otras):
                    self.con.execute("DELETE FROM canciones WHERE id = ?", (r["id"],))
            self.con.commit()

    # --- Canciones ---

    def indexar(self, ruta: Path) -> None:
        """Agrega o actualiza un archivo leyendo sus etiquetas."""
        ruta = Path(ruta)
        if not ruta.exists():
            return
        d = leer_archivo(ruta)
        self._w(
            """INSERT INTO canciones(ruta, titulo, artista, artista_ppal, album, artista_album, anio, pista, genero,
                                     duracion, mbid, clave, mtime, agregada)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(ruta) DO UPDATE SET titulo=excluded.titulo, artista=excluded.artista,
                 artista_ppal=excluded.artista_ppal, album=excluded.album, artista_album=excluded.artista_album,
                 anio=excluded.anio, pista=excluded.pista, genero=excluded.genero, duracion=excluded.duracion,
                 mbid=excluded.mbid, clave=excluded.clave, mtime=excluded.mtime""",
            (str(ruta), d["titulo"], d["artista"], d["artista_ppal"], d["album"], d["artista_album"], d["anio"],
             d["pista"], d["genero"], d["duracion"], d["mbid"], clave(d["artista"], d["titulo"]),
             ruta.stat().st_mtime, time.time()),
        )

    def escanear(self, progreso: Callable[[int], None] | None = None,
                 cancelado: Callable[[], bool] = lambda: False) -> tuple[int, int]:
        """Revisa todas las carpetas: agrega lo nuevo o cambiado y quita lo que ya no existe."""
        conocidas = {r["ruta"]: r["mtime"] for r in self._q("SELECT ruta, mtime FROM canciones")}
        vistas: set[str] = set()
        nuevas = revisadas = 0
        for carpeta in self.carpetas():
            if not carpeta.is_dir():
                continue
            for raiz, _dirs, archivos in os.walk(carpeta):
                for nombre in archivos:
                    if cancelado():
                        return nuevas, 0
                    if Path(nombre).suffix.lower() not in EXTENSIONES:
                        continue
                    ruta = os.path.join(raiz, nombre)
                    vistas.add(ruta)
                    revisadas += 1
                    try:
                        mtime = os.path.getmtime(ruta)
                    except OSError:
                        continue
                    if conocidas.get(ruta) != mtime:
                        self.indexar(Path(ruta))
                        nuevas += ruta not in conocidas
                    if progreso and revisadas % 50 == 0:
                        progreso(revisadas)
        quitadas = [r for r in conocidas if r not in vistas and not os.path.exists(r)]
        with self.candado:
            self.con.executemany("DELETE FROM canciones WHERE ruta = ?", [(r,) for r in quitadas])
            self.con.commit()
        return nuevas, len(quitadas)

    def canciones(self, texto: str = "") -> list[Cancion]:
        sql = "SELECT * FROM canciones"
        params: tuple = ()
        if texto:
            sql += " WHERE titulo LIKE ? OR artista LIKE ? OR album LIKE ?"
            params = (f"%{texto}%",) * 3
        sql += " ORDER BY artista COLLATE NOCASE, album COLLATE NOCASE, pista, titulo COLLATE NOCASE"
        return [self._cancion(r) for r in self._q(sql, params)]

    def cancion_por_ruta(self, ruta: Path) -> Cancion | None:
        filas = self._q("SELECT * FROM canciones WHERE ruta = ?", (str(ruta),))
        return self._cancion(filas[0]) if filas else None

    def total(self) -> int:
        return self._q("SELECT COUNT(*) AS n FROM canciones")[0]["n"]

    def buscar_existente(self, artista: str, titulo: str, duracion: float | None = None) -> Cancion | None:
        """¿Ya tienes esta canción en alguna carpeta? Compara artista+título normalizados (y duración)."""
        # Se prueban dos lecturas: la tal cual y "Artista - Canción" dentro del título (típico de YouTube)
        lecturas = [(artista, titulo)]
        if " - " in titulo:
            lecturas.append(tuple(p.strip() for p in titulo.split(" - ", 1)))
        candidatos: list[Cancion] = []
        for a, t in lecturas:
            art, tit = normalizar(artista_principal(a)), normalizar(t)
            if not art or not tit:
                continue
            candidatos += [self._cancion(r) for r in self._q("SELECT * FROM canciones WHERE clave = ?",
                                                              (f"{art}|{tit}",))]
            # Mismo título y el artista de uno contiene al del otro ("Daft Punk" vs "Daft Punk, Pharrell")
            for r in self._q("SELECT * FROM canciones WHERE clave LIKE ?", (f"%|{tit}",)):
                a2 = r["clave"].split("|", 1)[0]
                if a2 and a2 != art and (a2 in art or art in a2):
                    candidatos.append(self._cancion(r))
        for c in candidatos:
            if not duracion or not c.duracion or abs(c.duracion - duracion) <= 10:
                return c
        return None

    # --- Álbumes y artistas ---

    def albumes(self) -> list[Album]:
        """Agrupa por álbum + artista del álbum (si el archivo no lo trae, solo por nombre de álbum)."""
        filas = self._q(
            """SELECT album, COALESCE(artista_album, '') AS grupo, MIN(artista_ppal) AS ppal, MAX(anio) AS anio,
                      COUNT(*) AS n, MIN(ruta) AS ruta
               FROM canciones WHERE album != ''
               GROUP BY album COLLATE NOCASE, COALESCE(artista_album, '') COLLATE NOCASE
               ORDER BY COALESCE(NULLIF(artista_album, ''), MIN(artista_ppal)) COLLATE NOCASE, anio,
                        album COLLATE NOCASE""")
        return [Album(r["album"], r["grupo"] or r["ppal"] or "", r["anio"] or "", r["n"], Path(r["ruta"]), r["grupo"])
                for r in filas]

    def canciones_de_album(self, album: "Album") -> list[Cancion]:
        return [self._cancion(r) for r in self._q(
            """SELECT * FROM canciones WHERE album = ? COLLATE NOCASE AND COALESCE(artista_album, '') = ? COLLATE NOCASE
               ORDER BY pista, titulo COLLATE NOCASE""", (album.nombre, album.grupo))]

    def artistas(self) -> list[tuple[str, int]]:
        return [(r["a"], r["n"]) for r in self._q(
            """SELECT artista_ppal AS a, COUNT(*) AS n FROM canciones WHERE artista_ppal != ''
               GROUP BY artista_ppal COLLATE NOCASE ORDER BY artista_ppal COLLATE NOCASE""")]

    def canciones_de_artista(self, artista: str) -> list[Cancion]:
        return [self._cancion(r) for r in self._q(
            """SELECT * FROM canciones WHERE artista_ppal = ? COLLATE NOCASE
               ORDER BY album COLLATE NOCASE, pista, titulo COLLATE NOCASE""", (artista,))]

    # --- Historial (para recomendaciones) ---

    def registrar(self, tipo: str, ruta: Path, artista: str, titulo: str):
        self._w("INSERT INTO eventos(tipo, ruta, artista, titulo, fecha) VALUES (?,?,?,?,?)",
                (tipo, str(ruta), artista, titulo, time.time()))

    def semillas(self, n: int = 3, dias: int = 60) -> list[tuple[str, str, str]]:
        """Canciones base para recomendar: (artista, título, motivo). Una por artista.

        Una descarga pesa más que una reproducción. Sin historial, usa las canciones más nuevas de la biblioteca.
        """
        desde = time.time() - dias * 86400
        filas = self._q(
            """SELECT artista, titulo,
                      SUM(CASE tipo WHEN 'descarga' THEN 3 ELSE 1 END) AS peso,
                      SUM(tipo = 'reproduccion') AS veces
               FROM eventos WHERE fecha >= ? AND artista != '' GROUP BY artista, titulo
               ORDER BY peso DESC, MAX(fecha) DESC""", (desde,))
        elegidas, artistas = [], set()
        for r in filas:
            ppal = normalizar(artista_principal(r["artista"]))
            if ppal in artistas:
                continue
            artistas.add(ppal)
            elegidas.append((r["artista"], r["titulo"], "escuchas" if r["veces"] else "descargaste"))
            if len(elegidas) == n:
                return elegidas
        for r in self._q("SELECT artista, titulo FROM canciones ORDER BY agregada DESC LIMIT 50"):
            ppal = normalizar(artista_principal(r["artista"]))
            if ppal and ppal not in artistas:
                artistas.add(ppal)
                elegidas.append((r["artista"], r["titulo"], "tienes"))
                if len(elegidas) == n:
                    break
        return elegidas

    def artista_favorito(self) -> str | None:
        filas = self._q(
            """SELECT c.artista_ppal AS a, COUNT(*) AS n FROM eventos e JOIN canciones c ON c.ruta = e.ruta
               WHERE e.tipo = 'reproduccion' AND c.artista_ppal != '' GROUP BY c.artista_ppal ORDER BY n DESC LIMIT 1""")
        if not filas:
            filas = self._q("""SELECT artista_ppal AS a, COUNT(*) AS n FROM canciones WHERE artista_ppal != ''
                               GROUP BY artista_ppal ORDER BY n DESC LIMIT 1""")
        return filas[0]["a"] if filas else None

    def mas_escuchadas(self, n: int = 12) -> list[tuple[Cancion, int]]:
        return [(self._cancion(r), r["veces"]) for r in self._q(
            """SELECT c.*, COUNT(*) AS veces FROM eventos e JOIN canciones c ON c.ruta = e.ruta
               WHERE e.tipo = 'reproduccion' GROUP BY c.id ORDER BY veces DESC, MAX(e.fecha) DESC LIMIT ?""", (n,))]

    def recientes(self, n: int = 12) -> list[Cancion]:
        return [self._cancion(r) for r in self._q(
            """SELECT c.* FROM eventos e JOIN canciones c ON c.ruta = e.ruta
               WHERE e.tipo = 'reproduccion' GROUP BY c.id ORDER BY MAX(e.fecha) DESC LIMIT ?""", (n,))]

    # --- Playlists ---

    def playlists(self) -> list[tuple[int, str, int]]:
        return [(r["id"], r["nombre"], r["n"]) for r in self._q(
            """SELECT p.id, p.nombre, COUNT(pc.cancion_id) AS n FROM playlists p
               LEFT JOIN playlist_canciones pc ON pc.playlist_id = p.id
               GROUP BY p.id ORDER BY p.nombre COLLATE NOCASE""")]

    def crear_playlist(self, nombre: str) -> int:
        return self._w("INSERT INTO playlists(nombre, creada) VALUES (?, ?)", (nombre.strip(), time.time()))

    def renombrar_playlist(self, pid: int, nombre: str):
        self._w("UPDATE playlists SET nombre = ? WHERE id = ?", (nombre.strip(), pid))

    def borrar_playlist(self, pid: int):
        self._w("DELETE FROM playlists WHERE id = ?", (pid,))

    def agregar_a_playlist(self, pid: int, ids: list[int]) -> int:
        with self.candado:
            pos = self.con.execute("SELECT COALESCE(MAX(posicion), 0) FROM playlist_canciones WHERE playlist_id = ?",
                                   (pid,)).fetchone()[0]
            agregadas = 0
            for cid in ids:
                pos += 1
                cur = self.con.execute(
                    "INSERT OR IGNORE INTO playlist_canciones(playlist_id, cancion_id, posicion) VALUES (?,?,?)",
                    (pid, cid, pos))
                agregadas += cur.rowcount
            self.con.commit()
            return agregadas

    def quitar_de_playlist(self, pid: int, ids: list[int]):
        with self.candado:
            self.con.executemany("DELETE FROM playlist_canciones WHERE playlist_id = ? AND cancion_id = ?",
                                 [(pid, i) for i in ids])
            self.con.commit()

    def mover_en_playlist(self, pid: int, cid: int, paso: int):
        """Sube (-1) o baja (+1) una canción dentro de la playlist."""
        with self.candado:
            orden = [r[0] for r in self.con.execute(
                "SELECT cancion_id FROM playlist_canciones WHERE playlist_id = ? ORDER BY posicion", (pid,))]
            if cid not in orden:
                return
            i = orden.index(cid)
            j = min(max(i + paso, 0), len(orden) - 1)
            orden.insert(j, orden.pop(i))
            self.con.executemany("UPDATE playlist_canciones SET posicion = ? WHERE playlist_id = ? AND cancion_id = ?",
                                 [(n, pid, c) for n, c in enumerate(orden)])
            self.con.commit()

    def canciones_de_playlist(self, pid: int) -> list[Cancion]:
        return [self._cancion(r) for r in self._q(
            """SELECT c.* FROM playlist_canciones pc JOIN canciones c ON c.id = pc.cancion_id
               WHERE pc.playlist_id = ? ORDER BY pc.posicion""", (pid,))]
