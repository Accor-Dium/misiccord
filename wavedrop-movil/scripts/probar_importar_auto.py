"""Revisa importar playlist (orden, actualizar con el mismo link compartido de otra forma) y el árbol de Android Auto.

Sin internet ni la app: crea canciones de 2 s con ffmpeg en una carpeta temporal y finge las descargas.
    python scripts/probar_importar_auto.py
"""
import subprocess, sys, tempfile, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))
from wavedrop import api, descargas

tmp = Path(tempfile.mkdtemp())
musica = tmp / "musica"
r = api.iniciar({"datos": str(tmp / "datos"), "musica": str(musica), "cache": str(tmp / "cache"), "idioma": "en"})
api._ajustes()["musicbrainz"] = False

def mp3(nombre, titulo, artista, album):
    ruta = musica / artista / f"{nombre}.mp3"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", "2",
                    "-metadata", f"title={titulo}", "-metadata", f"artist={artista}", "-metadata", f"album={album}",
                    str(ruta)], check=True)
    return ruta

for n, (t, a, al) in enumerate([("Uno", "Queen", "A Night"), ("Dos", "Queen", "A Night"), ("Tres", "Abba", "Gold")]):
    api._indexar(mp3(f"c{n}", t, a, al))

E = lambda i, t, a: descargas.Entrada(indice=i, id=f"id{i}", titulo=t, artista=a, url="", fuente="spotify", duracion=2)
col = descargas.Coleccion("Mi lista", "spotify", None, [E(1, "Tres", "Abba"), E(2, "Uno", "Queen"), E(3, "Nueva", "Muse"), E(4, "Dos", "Queen")])
descargas.obtener_coleccion = lambda url: col

class Falso:  # "descarga" creando el archivo
    def __init__(self, *a): pass
    def descargar(self, e, prog, canc):
        return types.SimpleNamespace(ruta=str(mp3(e.titulo, e.titulo, e.artista, "Origin")))
descargas.Descargador = Falso
class Ya:  # el pool corre todo en el momento
    def submit(self, f, *a): f(*a)
api._gestor.pool = Ya()
api.plataforma.archivo_nuevo = lambda r: None

orden = lambda pid: [c["titulo"] for c in api.playlist({"id": pid})["canciones"]]
x = api.descargar({"url": "https://open.spotify.com/playlist/ABC?si=123", "playlist": True})
pid = x["playlist"]["id"]
assert x["playlist"]["nombre"] == "Mi lista", x
assert orden(pid) == ["Tres", "Uno", "Nueva", "Dos"], orden(pid)

# Agregas una tuya, el original cambia de orden y suma otra: mismo link compartido distinto -> misma playlist
api._indexar(mp3("extra", "Extra", "Otro", "X"))
extra = next(c for c in api.biblioteca_({})["canciones"] if c["titulo"] == "Extra")
api.agregar_a_playlist({"id": pid, "db_ids": [extra["db_id"]]})
col.entradas = [E(4, "Dos", "Queen"), E(1, "Tres", "Abba"), E(2, "Uno", "Queen"), E(3, "Nueva", "Muse")]
y = api.descargar({"url": "https://open.spotify.com/intl-es/playlist/ABC/?si=999", "playlist": True})
assert y["playlist"]["id"] == pid, y
assert orden(pid) == ["Dos", "Tres", "Uno", "Nueva", "Extra"], orden(pid)
assert len(api._db().playlists()) == 1
# Sin "playlist" no crea nada (descargar como antes)
api.descargar({"url": "https://www.youtube.com/playlist?list=PLx"})
assert len(api._db().playlists()) == 1
# Otro link con el mismo nombre: playlist nueva con otro nombre
z = api.descargar({"url": "https://music.youtube.com/playlist?list=PLy", "playlist": True})
assert z["playlist"]["nombre"] == "Mi lista (2)", z
assert api._origen("https://www.youtube.com/watch?v=abc&list=PLy") == api._origen("https://music.youtube.com/playlist?list=PLy")

# "Agregar a playlist" desde una vista previa: se baja y entra al final; si ya la tienes, entra de una vez
antes = orden(pid)
w = api.descargar({"canciones": [{"id": "yt1", "titulo": "Previa", "artista": "Muse", "duracion": 2}], "a_playlist": pid})
assert w["ya"] == 0 and orden(pid) == antes + ["Previa"], orden(pid)
uno = next(c for c in api.biblioteca_({})["canciones"] if c["titulo"] == "Uno")
api.quitar_de_playlist({"id": pid, "db_ids": [uno["db_id"]]})
w = api.descargar({"canciones": [{"id": "yt2", "titulo": "Uno", "artista": "Queen", "ruta": uno["ruta"]}], "a_playlist": pid})
assert w["ya"] == 1 and w["trabajos"] == [] and orden(pid)[-1] == "Uno", (w, orden(pid))

# Android Auto
raiz = api.auto({})["elementos"]
assert [e["id"] for e in raiz] == ["recientes", "me_gusta", "playlists", "biblioteca"] and raiz[0]["titulo"] == "Recent", raiz
pl = api.auto({"id": "playlists"})["elementos"]
assert {e["titulo"] for e in pl} == {"Mi lista", "Mi lista (2)"} and all(e["carpeta"] for e in pl)
dentro = api.auto({"id": f"playlist:{pid}"})
assert dentro["titulo"] == "Mi lista" and [e["id"] for e in dentro["elementos"]][:2] == [f"playlist:{pid}#0", f"playlist:{pid}#1"]
assert dentro["elementos"][1]["cancion"]["titulo"] == "Tres"
albumes = api.auto({"id": "albumes"})["elementos"]
a_night = next(e for e in albumes if e["titulo"] == "A Night")
assert {e["titulo"] for e in api.auto({"id": a_night["id"]})["elementos"]} == {"Uno", "Dos"}
artistas = api.auto({"id": "artistas"})["elementos"]
assert len(api.auto({"id": next(e["id"] for e in artistas if e["titulo"] == "Queen")})["elementos"]) == 2
assert [e["titulo"] for e in api.auto({"id": "buscar:tres"})["elementos"]] == ["Tres"]
assert api.auto({"id": "me_gusta"})["elementos"] == []
print("todo bien")
