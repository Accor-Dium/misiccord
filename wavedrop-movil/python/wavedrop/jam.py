"""Jams en red local: varias personas escuchan y arman la cola juntas.

Cualquier WaveDrop (Windows o Android) puede ser anfitrión. Este módulo levanta un servidor HTTP
(solo librería estándar) al que se conectan las interfaces de los invitados directamente:

  GET  /info                  nombre de la sala (sin código, para el descubrimiento)
  POST /unirse                {nombre, cliente?}  -> {cliente, rol, estado}
  GET  /eventos               flujo SSE con el estado de la sala cada vez que cambia
  GET  /hora                  reloj del anfitrión (para sincronizar la reproducción)
  GET  /audio/<pid>           el audio de una pista (soporta Range para adelantar)
  GET  /portada/<pid>         portada local de una pista
  GET  /biblioteca?q=         canciones del anfitrión para agregar
  GET  /buscar?q=             búsqueda en YouTube Music hecha por el anfitrión
  POST /agregar               {cliente, cancion}
  POST /votar                 {cliente}  votar para saltar
  POST /reaccion              {cliente, emoji}
  POST /control               {cliente, accion, ...}  solo el anfitrión (play, pausa, siguiente...)
  POST /salir                 {cliente}

Todas menos /info piden el código de 4 dígitos (cabecera X-Codigo o ?codigo=).
El anfitrión anuncia la sala por UDP (puerto 47474) para que los demás la encuentren solos.
"""
import json
import mimetypes
import secrets
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PUERTO_ANUNCIO = 47474
PUERTOS = range(47480, 47490)
REACCIONES = {"🔥", "❤️", "😂", "👏", "🎉", "😮"}


def ahora_ms() -> float:
    return time.time() * 1000


def ips_locales() -> list[str]:
    """IPs de esta máquina en la red local (la principal primero)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no envía nada: solo elige la interfaz de salida
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips or ["127.0.0.1"]


class Sala:
    """Estado de un jam. El reloj del anfitrión manda: inicio_ms es cuándo sonó el segundo 0 de la pista."""

    def __init__(self, nombre: str, modo: str, anfitrion: str, api):
        self.api = api
        self.nombre = nombre
        self.modo = modo  # "anfitrion" (suena solo en el anfitrión) o "sincronizado" (en todos)
        self.codigo = f"{secrets.randbelow(10000):04d}"
        self.anfitrion = secrets.token_hex(8)
        self.participantes = {self.anfitrion: {"nombre": anfitrion, "rol": "anfitrion", "visto": time.time()}}
        self.bloqueados: set[str] = set()
        self.invitados_agregan = True
        self.cola: list[dict] = []
        self.indice = -1
        self.sonando = False
        self.pausada = False  # el anfitrión puso pausa: no arrancar solo aunque lleguen canciones
        self.inicio_ms = 0.0
        self.pausa_pos = 0.0
        self.votos: set[str] = set()
        self.reacciones: list[dict] = []
        self.version = 0
        self.cambio = threading.Condition()
        self.candado = threading.RLock()

    # --- Estado ---

    def posicion(self) -> float:
        if self.sonando:
            return max(0.0, (ahora_ms() - self.inicio_ms) / 1000)
        return self.pausa_pos

    def publico(self) -> dict:
        with self.candado:
            pistas = [{k: v for k, v in p.items() if k not in ("ruta", "portada_local")} for p in self.cola]
            invitados = [{"cliente": c[:6], "nombre": p["nombre"], "rol": p["rol"]}
                         for c, p in self.participantes.items() if time.time() - p["visto"] < 60]
            return {
                "nombre": self.nombre, "modo": self.modo, "cola": pistas, "indice": self.indice,
                "sonando": self.sonando, "inicio_ms": self.inicio_ms, "posicion": self.posicion(),
                "servidor_ms": ahora_ms(), "participantes": invitados, "votos": len(self.votos),
                "votos_necesarios": self.votos_necesarios(), "invitados_agregan": self.invitados_agregan,
                "reacciones": self.reacciones[-12:], "version": self.version,
            }

    def avisar(self):
        with self.cambio:
            self.version += 1
            self.cambio.notify_all()
        self.api.emitir("jam", {"estado": self.publico()})

    def votos_necesarios(self) -> int:
        activos = sum(1 for p in self.participantes.values() if time.time() - p["visto"] < 60)
        return max(1, (activos + 1) // 2)

    # --- Reproducción ---

    def _empezar(self, i: int, pos: float = 0.0):
        self.votos.clear()
        self.pausada = False
        if 0 <= i < len(self.cola) and self.cola[i]["estado"] == "lista":
            self.indice = i
            self.sonando = True
            self.inicio_ms = ahora_ms() - pos * 1000

    def siguiente(self):
        """Pasa a la siguiente pista lista. Si ya no hay, se queda en la última (y arranca sola si llega otra)."""
        with self.candado:
            j = next((k for k in range(self.indice + 1, len(self.cola)) if self.cola[k]["estado"] == "lista"), None)
            if j is not None:
                self._empezar(j)
            else:
                self.sonando = False
                self.pausa_pos = 0.0
                self.votos.clear()
        self.avisar()

    def vigilar(self):
        """Avanza cuando termina la pista y arranca sola si la cola estaba vacía y llega algo (hilo de la sala)."""
        while not getattr(self, "cerrada", False):
            time.sleep(0.5)
            with self.candado:
                actual = self.cola[self.indice] if 0 <= self.indice < len(self.cola) else None
                termino = bool(self.sonando and actual and actual.get("duracion")
                               and self.posicion() >= actual["duracion"] - 0.25)
                espera = (not self.sonando and not self.pausada
                          and any(p["estado"] == "lista" for p in self.cola[self.indice + 1:]))
            if termino or espera:
                self.siguiente()

    # --- Cola ---

    def agregar_pista(self, cancion: dict, quien: str) -> dict:
        from . import biblioteca, explorar

        pid = secrets.token_hex(5)
        pista = {"pid": pid, "titulo": cancion.get("titulo", ""), "artista": cancion.get("artista", ""),
                 "album": cancion.get("album", ""), "duracion": cancion.get("duracion"),
                 "portada": cancion.get("portada") if str(cancion.get("portada") or "").startswith("http") else None,
                 "agregada_por": self.participantes.get(quien, {}).get("nombre", "Alguien"), "estado": "lista"}
        ruta = cancion.get("ruta")
        if not ruta and cancion.get("id"):
            existente = self.api._db().buscar_existente(pista["artista"], pista["titulo"], pista["duracion"])
            ruta = str(existente.ruta) if existente else None
        if ruta and Path(ruta).exists():
            pista["ruta"] = ruta
            pista["portada_local"] = self.api.portada_local(Path(ruta))
            if not pista["duracion"]:
                pista["duracion"] = biblioteca.leer_archivo(Path(ruta))["duracion"]
        elif cancion.get("id"):
            # El anfitrión no la tiene: se descarga y entra a la cola cuando esté lista
            pista["estado"] = "descargando"
            r = explorar.ResultadoCancion(cancion["id"], pista["titulo"], pista["artista"], pista["album"],
                                          pista["duracion"], cancion.get("portada"))
            trabajo = self.api._gestor.agregar(explorar.a_entrada(r), self.nombre)
            threading.Thread(target=self._esperar_descarga, args=(pid, trabajo), daemon=True).start()
        else:
            raise ValueError("Canción sin archivo ni id de YouTube Music")
        if pista.get("portada_local"):
            pista["portada"] = f"/portada/{pid}"
        with self.candado:
            self.cola.append(pista)
        self.avisar()
        return pista

    def _esperar_descarga(self, pid: str, trabajo: dict):
        while trabajo["estado"] not in ("listo", "existe", "error", "cancelado"):
            time.sleep(0.5)
        with self.candado:
            pista = next((p for p in self.cola if p["pid"] == pid), None)
            if pista is None:
                return
            if trabajo.get("ruta"):
                pista["ruta"] = trabajo["ruta"]
                pista["estado"] = "lista"
                pl = self.api.portada_local(Path(trabajo["ruta"]))
                if pl:
                    pista["portada_local"] = pl
                    pista["portada"] = pista["portada"] or f"/portada/{pid}"
                if not pista.get("duracion"):
                    from . import biblioteca
                    pista["duracion"] = biblioteca.leer_archivo(Path(trabajo["ruta"]))["duracion"]
            else:
                pista["estado"] = "error"
            # Si la cola ya pasó de largo mientras se descargaba, entra justo después de la que suena
            i = self.cola.index(pista)
            if pista["estado"] == "lista" and i < self.indice:
                self.cola.pop(i)
                self.indice -= 1
                self.cola.insert(self.indice + 1, pista)
        self.avisar()

    def pista(self, pid: str) -> dict | None:
        with self.candado:
            return next((p for p in self.cola if p["pid"] == pid), None)


class _Manejador(BaseHTTPRequestHandler):
    sala: Sala = None  # se asigna al crear el servidor
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    # --- Utilidades ---

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Codigo, Range")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _consulta(self) -> dict:
        return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}

    def _ruta(self) -> str:
        return urllib.parse.urlparse(self.path).path

    def _cuerpo(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _autorizado(self) -> bool:
        codigo = self.headers.get("X-Codigo") or self._consulta().get("codigo")
        if codigo != self.sala.codigo:
            self._json({"error": "Código incorrecto"}, 403)
            return False
        return True

    def _cliente(self, datos: dict) -> str | None:
        c = datos.get("cliente") or self._consulta().get("cliente")
        if not c or c in self.sala.bloqueados or c not in self.sala.participantes:
            self._json({"error": "No estás en este jam"}, 403)
            return None
        self.sala.participantes[c]["visto"] = time.time()
        return c

    # --- Métodos ---

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        ruta, sala = self._ruta(), self.sala
        try:
            if ruta == "/info":
                anfitrion = sala.participantes[sala.anfitrion]["nombre"]
                return self._json({"wavedrop": 1, "nombre": sala.nombre, "anfitrion": anfitrion, "modo": sala.modo})
            if not self._autorizado():
                return
            if ruta == "/hora":
                return self._json({"ms": ahora_ms()})
            if ruta == "/estado":
                return self._json(sala.publico())
            if ruta == "/eventos":
                return self._eventos()
            if ruta.startswith("/audio/"):
                return self._archivo(sala.pista(ruta.split("/")[2]), "ruta")
            if ruta.startswith("/portada/"):
                return self._archivo(sala.pista(ruta.split("/")[2]), "portada_local")
            if ruta == "/biblioteca":
                q = self._consulta().get("q", "")
                canciones = [sala.api._local(c) for c in sala.api._db().canciones(q)[:200]]
                for c in canciones:
                    c["portada"] = None  # las rutas locales del anfitrión no sirven en otro dispositivo
                return self._json({"canciones": canciones})
            if ruta == "/buscar":
                from . import explorar
                q = self._consulta().get("q", "")
                return self._json({"canciones": [sala.api._en_linea(c) for c in explorar.buscar_canciones(q, 20)]})
            self._json({"error": "No existe"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self._json({"error": str(e)}, 500)
            except OSError:
                pass

    def do_POST(self):
        ruta, sala = self._ruta(), self.sala
        try:
            if not self._autorizado():
                return
            datos = self._cuerpo()
            if ruta == "/unirse":
                cliente = datos.get("cliente")
                if cliente in sala.bloqueados:
                    return self._json({"error": "El anfitrión te sacó de este jam"}, 403)
                if not cliente or cliente not in sala.participantes:
                    cliente = secrets.token_hex(8)
                    sala.participantes[cliente] = {"nombre": (datos.get("nombre") or "Invitado")[:30], "rol": "invitado",
                                                   "visto": time.time()}
                sala.participantes[cliente]["visto"] = time.time()
                sala.avisar()
                return self._json({"cliente": cliente, "rol": sala.participantes[cliente]["rol"], "estado": sala.publico()})
            cliente = self._cliente(datos)
            if not cliente:
                return
            es_anfitrion = cliente == sala.anfitrion
            if ruta == "/agregar":
                if not es_anfitrion and not sala.invitados_agregan:
                    return self._json({"error": "El anfitrión no permite agregar canciones"}, 403)
                return self._json({"pista": sala.agregar_pista(datos["cancion"], cliente)})
            if ruta == "/votar":
                sala.votos.add(cliente)
                if len(sala.votos) >= sala.votos_necesarios():
                    sala.siguiente()
                else:
                    sala.avisar()
                return self._json({"ok": True})
            if ruta == "/reaccion":
                emoji = datos.get("emoji")
                if emoji in REACCIONES:
                    sala.reacciones.append({"emoji": emoji, "nombre": sala.participantes[cliente]["nombre"], "ms": ahora_ms()})
                    sala.reacciones = sala.reacciones[-30:]
                    sala.avisar()
                return self._json({"ok": True})
            if ruta == "/salir":
                sala.participantes.pop(cliente, None)
                sala.avisar()
                return self._json({"ok": True})
            if ruta == "/control":
                if not es_anfitrion:
                    return self._json({"error": "Solo el anfitrión controla la reproducción"}, 403)
                self._control(datos)
                return self._json({"ok": True})
            self._json({"error": "No existe"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self._json({"error": str(e)}, 500)
            except OSError:
                pass

    def _control(self, d: dict):
        sala = self.sala
        accion = d.get("accion")
        with sala.candado:
            if accion == "play" and not sala.sonando:
                sala.pausada = False
                if 0 <= sala.indice < len(sala.cola):
                    sala.sonando = True
                    sala.inicio_ms = ahora_ms() - sala.pausa_pos * 1000
            elif accion == "pausa" and sala.sonando:
                sala.pausa_pos = sala.posicion()
                sala.sonando = False
                sala.pausada = True
            elif accion == "buscar":
                pos = float(d.get("posicion", 0))
                if sala.sonando:
                    sala.inicio_ms = ahora_ms() - pos * 1000
                else:
                    sala.pausa_pos = pos
            elif accion == "saltar_a":
                sala._empezar(int(d["indice"]))
            elif accion == "anterior":
                sala._empezar(max(0, sala.indice - 1))
            elif accion == "quitar":
                i = next((k for k, p in enumerate(sala.cola) if p["pid"] == d.get("pid")), None)
                if i is not None:
                    sala.cola.pop(i)
                    if i < sala.indice:
                        sala.indice -= 1
                    elif i == sala.indice:
                        sala._empezar(sala.indice)
            elif accion == "modo" and d.get("modo") in ("anfitrion", "sincronizado"):
                sala.modo = d["modo"]
            elif accion == "permisos":
                sala.invitados_agregan = bool(d.get("invitados_agregan"))
            elif accion == "expulsar":
                for c in list(sala.participantes):
                    if c.startswith(d.get("cliente_corto", "-")) and c != sala.anfitrion:
                        sala.participantes.pop(c)
                        sala.bloqueados.add(c)
        if accion == "siguiente":
            sala.siguiente()
            return
        sala.avisar()

    def _eventos(self):
        """Server-Sent Events: manda el estado cada vez que cambia (y un latido cada 15 s)."""
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        cliente = self._consulta().get("cliente")
        visto = -1
        while not getattr(self.sala, "cerrada", False):
            if cliente in self.sala.bloqueados:
                self.wfile.write(b"event: expulsado\ndata: {}\n\n")
                self.wfile.flush()
                return
            if cliente in self.sala.participantes:
                self.sala.participantes[cliente]["visto"] = time.time()
            if self.sala.version != visto:
                visto = self.sala.version
                datos = json.dumps(self.sala.publico(), ensure_ascii=False)
                self.wfile.write(f"data: {datos}\n\n".encode())
            else:
                self.wfile.write(b": latido\n\n")
            self.wfile.flush()
            with self.sala.cambio:
                self.sala.cambio.wait(timeout=15)
        self.wfile.write(b"event: cerrada\ndata: {}\n\n")
        self.wfile.flush()

    def _archivo(self, pista: dict | None, clave: str):
        if not pista or not pista.get(clave) or not Path(pista[clave]).exists():
            return self._json({"error": "No disponible"}, 404)
        ruta = Path(pista[clave])
        tamano = ruta.stat().st_size
        inicio, fin = 0, tamano - 1
        rango = self.headers.get("Range")
        if rango and rango.startswith("bytes="):
            a, _, b = rango[6:].partition("-")
            inicio = int(a) if a else max(0, tamano - int(b))
            fin = int(b) if a and b else tamano - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {inicio}-{fin}/{tamano}")
        else:
            self.send_response(200)
        self._cors()
        self.send_header("Content-Type", mimetypes.guess_type(ruta.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fin - inicio + 1))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(ruta, "rb") as f:
            f.seek(inicio)
            restante = fin - inicio + 1
            while restante > 0:
                bloque = f.read(min(256 * 1024, restante))
                if not bloque:
                    break
                self.wfile.write(bloque)
                restante -= len(bloque)


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


_actual: dict = {"sala": None, "servidor": None, "puerto": None}


def crear(nombre_anfitrion: str, modo: str, api) -> dict:
    cerrar()
    sala = Sala(f"Jam de {nombre_anfitrion}", modo, nombre_anfitrion, api)
    manejador = type("Manejador", (_Manejador,), {"sala": sala})
    servidor = None
    for puerto in PUERTOS:
        try:
            servidor = _Servidor(("0.0.0.0", puerto), manejador)
            break
        except OSError:
            continue
    if servidor is None:
        raise RuntimeError("No hay puertos libres para el jam")
    _actual.update(sala=sala, servidor=servidor, puerto=puerto)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    threading.Thread(target=sala.vigilar, daemon=True).start()
    threading.Thread(target=_anunciar, args=(sala, puerto), daemon=True).start()
    return {"puerto": puerto, "codigo": sala.codigo, "cliente": sala.anfitrion, "ips": ips_locales(), "nombre": sala.nombre}


def cerrar() -> None:
    sala, servidor = _actual["sala"], _actual["servidor"]
    if sala:
        sala.cerrada = True
        with sala.cambio:
            sala.cambio.notify_all()
    if servidor:
        threading.Thread(target=servidor.shutdown, daemon=True).start()
        servidor.server_close()
    _actual.update(sala=None, servidor=None, puerto=None)


def _anunciar(sala: Sala, puerto: int) -> None:
    """Grita "aquí hay un jam" por UDP cada 2 s para que los WaveDrop de la red lo encuentren."""
    ips = ips_locales()
    mensaje = json.dumps({"wavedrop_jam": 1, "nombre": sala.nombre, "puerto": puerto, "ips": ips,
                          "anfitrion": sala.participantes[sala.anfitrion]["nombre"]}).encode()
    # Con varias tarjetas de red (Wi-Fi, VPN, máquinas virtuales) Windows manda 255.255.255.255 solo por una:
    # se anuncia desde cada IP hacia el broadcast de su red (/24, lo típico en casa)
    enchufes = []
    for ip in ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind((ip, 0))
            enchufes.append((s, ip.rsplit(".", 1)[0] + ".255"))
        except OSError:
            continue
    general = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    general.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    enchufes.append((general, "255.255.255.255"))
    while not getattr(sala, "cerrada", False):
        for s, destino in enchufes:
            try:
                s.sendto(mensaje, (destino, PUERTO_ANUNCIO))
            except OSError:
                pass
        time.sleep(2)
    for s, _ in enchufes:
        s.close()


def buscar(segundos: float = 3.0) -> list[dict]:
    """Escucha los anuncios de jams en la red local durante unos segundos."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", PUERTO_ANUNCIO))
    except OSError:
        s.close()
        return []
    s.settimeout(0.5)
    encontrados: dict[str, dict] = {}
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            datos, (ip, _p) = s.recvfrom(2048)
        except (socket.timeout, OSError):
            continue
        try:
            m = json.loads(datos)
        except ValueError:
            continue
        if m.get("wavedrop_jam"):
            # De las IPs del anfitrión, la que está en la misma red que este dispositivo
            mias = [x.rsplit(".", 1)[0] for x in ips_locales()]
            ip = next((x for x in m.get("ips", []) if x.rsplit(".", 1)[0] in mias), ip)
            encontrados[f"{m['nombre']}:{m['puerto']}"] = {"ip": ip, "puerto": m["puerto"], "nombre": m["nombre"],
                                                          "anfitrion": m.get("anfitrion", "")}
    s.close()
    return list(encontrados.values())
