"""Sincronizar tus dispositivos (el cel y la PC) sin cuentas: fase 1, en la misma red Wi-Fi.

Se vinculan una vez (código de 6 dígitos o QR) y de ahí en adelante, cada vez que se ven en la red, se pasan lo que
cambió: Me gusta, playlists, categorías e historial, y se copian las canciones que le falten al otro.

Cómo se ven y se reconocen:
  - Cada Misiccord con dispositivos vinculados levanta un servidor HTTP (puertos 47500–47509) y se anuncia por UDP
    (puerto 47475) cada 5 s. Al oír a uno vinculado, se sincroniza.
  - Al vincular hacen un intercambio Diffie-Hellman (grupo 14 de RFC 3526) autenticado con el código: de ahí sale un
    secreto que nunca viaja por la red. Cada petición y cada respuesta va firmada con HMAC de ese secreto.

Qué cambió se sabe comparando (`refrescar`): cada cosa sincronizable tiene un registro en `sinc_registros` con la huella
de cómo estaba. Si la huella cambió, es un cambio tuyo (mod = ahora); si desapareció, se marca borrada (para que
el otro no te la regrese). Así no hay que tocar cada lugar de la app que edita algo. Gana el cambio más reciente.

Las canciones no se mezclan así: cada quien decide con la lista del otro qué le falta. Borrar una canción en un
dispositivo NO la borra en el otro (fase 1); solo hace que ya no se la vuelva a mandar.

Solo inicia quien llama (I) y el otro (R) responde, así basta con que uno alcance al otro:
  POST /sinc/estado   lo de R que cambió desde la última vez, sus canciones y si acepta canciones
  POST /sinc/aplicar  lo de I que cambió
  PUT  /sinc/cancion  I le manda a R una canción que le falta
  GET  /sinc/archivo  I trae de R una canción que le falta
  POST /sinc/fin      R acomoda lo que dependía de canciones nuevas (playlists, categorías)
"""
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import shutil
import socket
import socketserver
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import biblioteca, plataforma
from .idioma import t as _t
from .jam import ips_locales

PUERTO_ANUNCIO = 47475
PUERTOS = range(47500, 47510)
VINCULAR_MINUTOS = 10
CADA = 120  # s: con un vinculado en línea, cada cuánto se revisa si hay algo nuevo
SESION_INACTIVA = 120  # s sin saber del otro: su sincronización se da por abandonada
LIBRE_MINIMO = 500 * 1024 * 1024  # no llenar el teléfono: se deja de recibir canciones con menos de esto libre

# Grupo 14 de RFC 3526 (primo seguro de 2048 bits, generador 2)
_P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sinc_registros (
    tipo TEXT, clave TEXT,
    mod REAL,       -- cuándo cambió de verdad (decide quién gana)
    cambio REAL,    -- cuándo cambió aquí (decide qué falta mandarle a cada dispositivo)
    borrado INTEGER DEFAULT 0,
    huella TEXT,    -- cómo estaba aquí la última vez que se revisó
    datos TEXT,
    PRIMARY KEY (tipo, clave)
);
CREATE INDEX IF NOT EXISTS idx_sinc_cambio ON sinc_registros(cambio);
-- Canciones recibidas con la clave con que las mandaron: si sus etiquetas dan otra, no se piden otra vez
CREATE TABLE IF NOT EXISTS sinc_recibidas (clave TEXT PRIMARY KEY, ruta TEXT);
"""

_estado: dict = {
    "api": None, "servidor": None, "puerto": None, "anunciando": False, "escuchando": False,
    "buscar_hasta": 0,   # escuchar anuncios hasta esta hora aunque este no se anuncie (Vincular, en el que escribe el código)
    "vinculando": None,  # {codigo, expira, privada, publica, intentos}
    "en_linea": {},      # id -> {ip, puerto, visto}
    "cercanos": {},      # id -> {ip, puerto, nombre, visto}: los que están vinculando
    "sesion": None,      # (id del otro, última vez que pidió algo) mientras alguien se sincroniza con este
    "trabajando": None,  # id con el que este se está sincronizando
    "intentos": {},      # id -> último intento
}
_candado = threading.RLock()
_sesion_candado = threading.Lock()


# ---------- Identidad y dispositivos vinculados ----------

def _ruta_config() -> Path:
    return plataforma.carpeta_datos() / "sincronizacion.json"


def _nombre_dispositivo() -> str:
    if plataforma.es_android():
        try:
            from java import jclass
            build = jclass("android.os.Build")
            modelo = str(build.MODEL)
            marca = str(build.MANUFACTURER).capitalize()
            return modelo if modelo.lower().startswith(marca.lower()) else f"{marca} {modelo}"
        except Exception:
            return "Android"
    return socket.gethostname() or "PC"


def _config() -> dict:
    with _candado:
        if "config" not in _estado:
            try:
                c = json.loads(_ruta_config().read_text(encoding="utf-8"))
            except (OSError, ValueError):
                c = {}
            c.setdefault("id", secrets.token_hex(8))
            c.setdefault("nombre", _nombre_dispositivo())
            c.setdefault("dispositivos", [])
            _estado["config"] = c
            _guardar()
        return _estado["config"]


def _guardar() -> None:
    temporal = _ruta_config().with_suffix(".tmp")
    temporal.write_text(json.dumps(_estado["config"], ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(_ruta_config())


def _dispositivo(did: str) -> dict | None:
    return next((x for x in _config()["dispositivos"] if x["id"] == did), None)


def _avisar() -> None:
    if _estado["api"]:
        _estado["api"].emitir("sincronizacion", resumen())


def resumen() -> dict:
    """Lo que la interfaz muestra en Ajustes → Mis dispositivos."""
    c, ahora = _config(), time.time()
    en_linea = {k for k, v in _estado["en_linea"].items() if ahora - v["visto"] < 15}
    vinc = _estado["vinculando"]
    vinculados = {x["id"] for x in c["dispositivos"]}
    return {
        "id": c["id"], "nombre": c["nombre"],
        "dispositivos": [{"id": x["id"], "nombre": x["nombre"], "en_linea": x["id"] in en_linea, "ultima": x.get("ultima"),
                          "copiar": x.get("copiar", True), "sincronizando": _estado["trabajando"] == x["id"]
                          or (_estado["sesion"] or ("",))[0] == x["id"], "error": x.get("error")}
                         for x in c["dispositivos"]],
        "vinculando": {"codigo": vinc["codigo"], "expira": vinc["expira"]} if vinc and vinc["expira"] > ahora else None,
        "cercanos": [{"id": k, "nombre": v["nombre"], "ip": v["ip"], "puerto": v["puerto"]}
                     for k, v in _estado["cercanos"].items() if ahora - v["visto"] < 12 and k not in vinculados],
        "progreso": _estado.get("progreso"),
    }


# ---------- Firmas ----------

def _huella(cuerpo: bytes) -> str:
    return hashlib.sha256(cuerpo or b"").hexdigest()


def _firma(secreto: str, metodo: str, ruta: str, hora: str, cuerpo: str) -> str:
    texto = f"{metodo}\n{ruta}\n{hora}\n{cuerpo}".encode()
    return hmac.new(bytes.fromhex(secreto), texto, hashlib.sha256).hexdigest()


def _pedir(disp: dict, metodo: str, ruta: str, datos=None, archivo: Path | None = None, timeout: float = 30):
    """Petición firmada a otro dispositivo. Con `archivo` se manda el archivo tal cual (sin hash del cuerpo: es grande)."""
    c = _config()
    hora = str(int(time.time() * 1000))
    if archivo is not None:
        cuerpo, huella = None, "-"
    else:
        cuerpo = json.dumps(datos or {}, ensure_ascii=False).encode()
        huella = _huella(cuerpo)
    url = f"http://{disp['ip']}:{disp['puerto']}{ruta}"
    peticion = urllib.request.Request(url, data=cuerpo, method=metodo)
    peticion.add_header("X-Sinc-Id", c["id"])
    peticion.add_header("X-Sinc-Hora", hora)
    peticion.add_header("X-Sinc-Firma", _firma(disp["secreto"], metodo, ruta, hora, huella))
    if archivo is not None:
        with open(archivo, "rb") as f:
            # Primero el cuerpo y después el largo: asignar `data` borra Content-Length y urllib lo mandaría por pedazos
            peticion.data = f
            peticion.add_header("Content-Length", str(archivo.stat().st_size))
            peticion.add_header("Content-Type", "application/octet-stream")
            with urllib.request.urlopen(peticion, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
    with urllib.request.urlopen(peticion, timeout=timeout) as r:
        cuerpo = r.read()
        if r.headers.get("Content-Type", "").startswith("application/json"):
            # La respuesta también va firmada: si no, cualquiera en la red podría hacerse pasar por el otro
            firma = r.headers.get("X-Sinc-Firma", "")
            esperada = _firma(disp["secreto"], "RESPUESTA", ruta, hora, _huella(cuerpo))
            if not hmac.compare_digest(firma, esperada):
                raise RuntimeError("La respuesta no viene del dispositivo vinculado")
            return json.loads(cuerpo or b"{}")
        return cuerpo


# ---------- Servidor ----------

class _Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _responder(self, datos, codigo=200, disp=None, hora=""):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        if disp:
            self.send_header("X-Sinc-Firma", _firma(disp["secreto"], "RESPUESTA", self.path, hora, _huella(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _autenticar(self, cuerpo: bytes | None) -> tuple[dict, str] | None:
        """El dispositivo vinculado que firmó la petición (o None, ya respondido)."""
        disp = _dispositivo(self.headers.get("X-Sinc-Id", ""))
        hora = self.headers.get("X-Sinc-Hora", "0")
        if not disp:
            self._responder({"error": "No vinculado", "desvinculado": True}, 403)
            return None
        # 10 minutos de margen: el reloj del cel y el de la PC casi nunca están idénticos
        if not hora.isdigit() or abs(int(hora) / 1000 - time.time()) > 600:
            self._responder({"error": "Hora fuera de rango"}, 403)
            return None
        huella = "-" if cuerpo is None else _huella(cuerpo)
        if not hmac.compare_digest(self.headers.get("X-Sinc-Firma", ""), _firma(disp["secreto"], self.command, self.path, hora, huella)):
            self._responder({"error": "Firma inválida"}, 403)
            return None
        disp["ip"] = self.client_address[0]
        with _sesion_candado:
            if _estado["sesion"] and _estado["sesion"][0] == disp["id"]:
                _estado["sesion"] = (disp["id"], time.time())
        return disp, hora

    def _leer(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        ruta = urllib.parse.urlparse(self.path)
        try:
            if ruta.path == "/sinc/hola":
                return self._responder({"misiccord_sinc": 1, "id": _config()["id"], "nombre": _config()["nombre"]})
            if ruta.path == "/sinc/archivo":
                quien = self._autenticar(b"")
                if not quien:
                    return
                clave = urllib.parse.parse_qs(ruta.query).get("clave", [""])[0]
                return self._mandar_archivo(clave)
            self._responder({"error": "No existe"}, 404)
        except (ConnectionError, TimeoutError):
            pass

    def do_POST(self):
        ruta = urllib.parse.urlparse(self.path).path
        try:
            cuerpo = self._leer()
            if ruta == "/sinc/vincular":
                return self._responder(*_aceptar_vinculo(json.loads(cuerpo or b"{}"), self.client_address[0]))
            quien = self._autenticar(cuerpo)
            if not quien:
                return
            disp, hora = quien
            d = json.loads(cuerpo or b"{}")
            if ruta == "/sinc/estado":
                if not _tomar_sesion(disp["id"]):
                    return self._responder({"error": "Ocupado", "ocupado": True}, 409, disp, hora)
                disp["puerto"] = d.get("puerto") or disp.get("puerto")
                return self._responder(_exportar(disp, d.get("desde", 0)), 200, disp, hora)
            if ruta == "/sinc/aplicar":
                fusionar(d.get("registros") or [], _desfase(d.get("hora")))
                return self._responder({"ok": True}, 200, disp, hora)
            if ruta == "/sinc/fin":
                _terminar_recepcion(disp, d)
                return self._responder({"ok": True}, 200, disp, hora)
            if ruta == "/sinc/soltar":  # al otro le falló algo a media sincronización
                _liberar_sesion(disp["id"])
                _avisar()
                return self._responder({"ok": True}, 200, disp, hora)
            if ruta == "/sinc/olvidar":
                _quitar(disp["id"])
                return self._responder({"ok": True}, 200, disp, hora)
            self._responder({"error": "No existe"}, 404)
        except (ConnectionError, TimeoutError):
            pass
        except Exception as e:
            self._responder({"error": str(e)}, 500)

    def do_PUT(self):
        ruta = urllib.parse.urlparse(self.path)
        try:
            if ruta.path != "/sinc/cancion":
                return self._responder({"error": "No existe"}, 404)
            quien = self._autenticar(None)
            if not quien:
                return
            disp, hora = quien
            q = {k: v[0] for k, v in urllib.parse.parse_qs(ruta.query).items()}
            self._responder(*_recibir_cancion(self.rfile, int(self.headers.get("Content-Length") or 0), q), disp, hora)
        except (ConnectionError, TimeoutError):
            pass

    def _mandar_archivo(self, clave: str):
        ruta = _ruta_de(clave)
        if not ruta:
            return self._responder({"error": "No la tengo"}, 404)
        tamano = ruta.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(tamano))
        fila = _db()._q("SELECT artista FROM canciones WHERE ruta = ?", (str(ruta),))
        self.send_header("X-Nombre", urllib.parse.quote(ruta.name))
        self.send_header("X-Artista", urllib.parse.quote(fila[0]["artista"] if fila else ""))
        self.end_headers()
        with open(ruta, "rb") as f:
            shutil.copyfileobj(f, self.wfile, 256 * 1024)


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = sys.platform != "win32"  # igual que el jam: en Windows dos servidores compartirían el puerto

    def server_bind(self):
        # Sin el getfqdn() de HTTPServer: con VPNs o Tailscale en la PC tarda ~12 s en contestar y no se usa para nada
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def iniciar(api) -> None:
    """Al abrir la app. Solo levanta el servidor si hay algo vinculado: si no, nada escucha en la red."""
    _estado["api"] = api
    db = api._db()
    with db.candado:
        db.con.executescript(ESQUEMA)
    if _config()["dispositivos"]:
        _levantar()


def _levantar() -> None:
    with _candado:
        if _estado["servidor"] is None:
            for puerto in PUERTOS:
                try:
                    _estado["servidor"] = _Servidor(("0.0.0.0", puerto), _Manejador)
                    _estado["puerto"] = puerto
                    break
                except OSError:
                    continue
            if _estado["servidor"] is None:
                raise RuntimeError("No hay puertos libres para sincronizar")
            threading.Thread(target=_estado["servidor"].serve_forever, daemon=True).start()
        if not _estado["anunciando"]:
            _estado["anunciando"] = True
            threading.Thread(target=_anunciar, daemon=True).start()
        if not _estado["escuchando"]:
            _estado["escuchando"] = True
            threading.Thread(target=_escuchar, daemon=True).start()


def _apagar_si_sobra() -> None:
    """Sin vinculados ni vinculación abierta, el servidor se apaga (ya no hay a quién esperar)."""
    with _candado:
        if _config()["dispositivos"] or _estado["vinculando"]:
            return
        servidor = _estado["servidor"]
        _estado.update(servidor=None, puerto=None, anunciando=False)
    if servidor:
        threading.Thread(target=servidor.shutdown, daemon=True).start()
        servidor.server_close()


# ---------- Anunciarse y escuchar a los demás (UDP) ----------

def _anunciar() -> None:
    while _estado["anunciando"]:
        c, vinc = _config(), _estado["vinculando"]
        if vinc and vinc["expira"] < time.time():
            _estado["vinculando"] = vinc = None
            _avisar()
        mensaje = {"misiccord_sinc": 1, "id": c["id"], "puerto": _estado["puerto"], "ips": ips_locales()}
        if vinc:
            mensaje.update(vinculando=True, nombre=c["nombre"])  # el nombre solo se anuncia mientras vinculas
        texto = json.dumps(mensaje).encode()
        for ip in mensaje["ips"]:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.bind((ip, 0))
                    s.sendto(texto, (ip.rsplit(".", 1)[0] + ".255", PUERTO_ANUNCIO))
            except OSError:
                pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.sendto(texto, ("255.255.255.255", PUERTO_ANUNCIO))
        except OSError:
            pass
        time.sleep(2 if vinc else 5)


def _escuchar() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", PUERTO_ANUNCIO))
    except OSError:
        _estado["escuchando"] = False
        s.close()
        return
    s.settimeout(1)
    while _estado["anunciando"] or time.time() < _estado["buscar_hasta"]:
        try:
            datos, (ip, _p) = s.recvfrom(2048)
            m = json.loads(datos)
        except (socket.timeout, OSError, ValueError):
            continue
        if not m.get("misiccord_sinc") or m.get("id") == _config()["id"] or not m.get("puerto"):
            continue
        mias = [x.rsplit(".", 1)[0] for x in ips_locales()]
        ip = next((x for x in m.get("ips", []) if x.rsplit(".", 1)[0] in mias), ip)
        _visto(m["id"], ip, int(m["puerto"]), m)
    s.close()
    _estado["escuchando"] = False


def _visto(did: str, ip: str, puerto: int, m: dict) -> None:
    ahora = time.time()
    if m.get("vinculando"):
        nuevo = did not in _estado["cercanos"]
        _estado["cercanos"][did] = {"ip": ip, "puerto": puerto, "nombre": str(m.get("nombre", ""))[:60], "visto": ahora}
        if nuevo:
            _avisar()
    disp = _dispositivo(did)
    if not disp:
        return
    estaba = ahora - _estado["en_linea"].get(did, {}).get("visto", 0) < 15
    _estado["en_linea"][did] = {"ip": ip, "puerto": puerto, "visto": ahora}
    disp["ip"], disp["puerto"] = ip, puerto
    if not estaba:
        _avisar()
    # Al aparecer, o cada CADA segundos mientras siga en línea. Con un poco de azar: si los dos empiezan a la vez,
    # el otro responde "ocupado" y cada quien lo intenta en otro momento
    if ahora - _estado["intentos"].get(did, 0) > CADA + random.uniform(0, 20):
        sincronizar_con(did)


# ---------- Vincular ----------

def abrir_vinculacion() -> dict:
    """Este dispositivo muestra un código (y QR) para que otro se vincule con él."""
    privada = secrets.randbelow(_P - 3) + 2
    vinc = {"codigo": f"{secrets.randbelow(10 ** 6):06d}", "expira": time.time() + VINCULAR_MINUTOS * 60,
            "privada": privada, "publica": pow(2, privada, _P), "intentos": 0}
    _estado["vinculando"] = vinc
    _levantar()
    _avisar()
    c = _config()
    return {"codigo": vinc["codigo"], "id": c["id"], "nombre": c["nombre"], "ips": ips_locales(), "puerto": _estado["puerto"],
            "huella": _huella(_bytes(vinc["publica"]))[:16]}


def cerrar_vinculacion() -> None:
    _estado["vinculando"] = None
    _apagar_si_sobra()
    _avisar()


def buscar_cercanos() -> None:
    """Para ver a los que están vinculando hay que escuchar, aunque este todavía no tenga nada vinculado."""
    with _candado:
        _estado["buscar_hasta"] = time.time() + VINCULAR_MINUTOS * 60
        if not _estado["escuchando"]:
            _estado["escuchando"] = True
            threading.Thread(target=_escuchar, daemon=True).start()


def _bytes(n: int) -> bytes:
    return n.to_bytes(256, "big")


def _mac(codigo: str, *partes: bytes) -> str:
    return hmac.new(codigo.encode(), b"|".join(partes), hashlib.sha256).hexdigest()


def _secreto(compartido: int, id_a: str, id_b: str) -> str:
    return hashlib.sha256(_bytes(compartido) + "|".join(sorted([id_a, id_b])).encode()).hexdigest()


def _aceptar_vinculo(d: dict, ip: str) -> tuple[dict, int]:
    """Lado que mostró el código: el otro manda su llave pública con una firma hecha con el código."""
    vinc = _estado["vinculando"]
    if not vinc or vinc["expira"] < time.time():
        return {"error": "Ese dispositivo ya no está esperando. Toca Vincular otra vez en él."}, 410
    if vinc["intentos"] >= 8:
        cerrar_vinculacion()
        return {"error": "Demasiados intentos. Vuelve a empezar."}, 429
    try:
        publica_b = int(d["publica"], 16)
    except (KeyError, ValueError, TypeError):
        return {"error": "Datos incompletos"}, 400
    if not 1 < publica_b < _P - 1 or not hmac.compare_digest(str(d.get("mac", "")), _mac(vinc["codigo"], b"b", _bytes(publica_b))):
        vinc["intentos"] += 1
        return {"error": "Código incorrecto"}, 403
    c = _config()
    otro_id, otro_nombre = str(d.get("id", ""))[:40], str(d.get("nombre", ""))[:60] or "Dispositivo"
    if not otro_id or otro_id == c["id"]:
        return {"error": "Datos incompletos"}, 400
    _agregar({"id": otro_id, "nombre": otro_nombre, "ip": ip, "puerto": d.get("puerto"),
              "secreto": _secreto(pow(publica_b, vinc["privada"], _P), c["id"], otro_id)})
    respuesta = {"id": c["id"], "nombre": c["nombre"], "publica": format(vinc["publica"], "x"),
                 "mac": _mac(vinc["codigo"], b"a", _bytes(vinc["publica"]), _bytes(publica_b))}
    _estado["vinculando"] = None
    _avisar()
    threading.Timer(2, sincronizar_con, args=(otro_id,)).start()
    return respuesta, 200


def vincular_con(ip: str, puerto: int, codigo: str, huella: str = "", otras: list[str] | None = None) -> dict:
    """Lado que escribe el código (o escanea el QR) del otro. `otras`: más IPs del otro (el QR las trae todas)."""
    codigo = re.sub(r"\D", "", codigo or "")
    if len(codigo) != 6:
        raise RuntimeError("El código tiene 6 números")
    _levantar()  # el otro nos va a buscar en cuanto termine
    try:
        return _vincular_con(_alcanzable([ip, *(otras or [])], puerto), puerto, codigo, huella)
    except Exception:
        _apagar_si_sobra()
        raise


def _alcanzable(ips: list[str], puerto: int) -> str:
    """La primera IP del otro que contesta. La PC suele tener varias (Wi-Fi, VPN, Tailscale…) y solo una es la de tu red."""
    ips = list(dict.fromkeys(x for x in ips if x))
    hallada, sin_permiso = [], []

    def probar(ip):
        try:
            with urllib.request.urlopen(f"http://{ip}:{puerto}/sinc/hola", timeout=4) as r:
                if json.loads(r.read()).get("misiccord_sinc"):
                    hallada.append(ip)
        except PermissionError:
            sin_permiso.append(ip)  # Android 17+ sin el permiso de red local (Dispositivos cercanos)
        except (OSError, ValueError):
            pass

    hilos = [threading.Thread(target=probar, args=(ip,), daemon=True) for ip in ips[:6]]
    for h in hilos:
        h.start()
    limite = time.time() + 5
    while not hallada and any(h.is_alive() for h in hilos) and time.time() < limite:
        time.sleep(0.05)
    if hallada:
        return hallada[0]
    if sin_permiso:
        raise RuntimeError(_t("Misiccord no tiene permiso para buscar dispositivos en tu red. Actívalo en Ajustes del sistema → Apps → Misiccord → Permisos → Dispositivos cercanos."))
    raise RuntimeError(_t("No encontré ese dispositivo en tu red. Revisa que los dos estén conectados a la misma Wi-Fi y que el otro siga en Vincular."))


def _vincular_con(ip: str, puerto: int, codigo: str, huella: str) -> dict:
    c = _config()
    privada = secrets.randbelow(_P - 3) + 2
    publica = pow(2, privada, _P)
    cuerpo = json.dumps({"id": c["id"], "nombre": c["nombre"], "puerto": _estado["puerto"], "publica": format(publica, "x"),
                         "mac": _mac(codigo, b"b", _bytes(publica))}).encode()
    peticion = urllib.request.Request(f"http://{ip}:{puerto}/sinc/vincular", data=cuerpo, method="POST",
                                      headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=15) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            mensaje = json.loads(e.read()).get("error")
        except ValueError:
            mensaje = None
        raise RuntimeError(mensaje or f"No se pudo vincular ({e.code})") from e
    except OSError as e:
        raise RuntimeError(_t("Se perdió la conexión con ese dispositivo. Inténtalo otra vez.")) from e
    publica_a = int(d["publica"], 16)
    if not 1 < publica_a < _P - 1 or not hmac.compare_digest(d.get("mac", ""), _mac(codigo, b"a", _bytes(publica_a), _bytes(publica))):
        raise RuntimeError("La respuesta no coincide con el código: no se vinculó")
    if huella and not _huella(_bytes(publica_a)).startswith(huella):
        raise RuntimeError("El QR no corresponde a ese dispositivo: no se vinculó")
    _agregar({"id": d["id"], "nombre": d.get("nombre") or "Dispositivo", "ip": ip, "puerto": puerto,
              "secreto": _secreto(pow(publica_a, privada, _P), c["id"], d["id"])})
    _estado["cercanos"].pop(d["id"], None)
    _avisar()
    return {"id": d["id"], "nombre": d.get("nombre")}


def _agregar(disp: dict) -> None:
    c = _config()
    with _candado:
        c["dispositivos"] = [x for x in c["dispositivos"] if x["id"] != disp["id"]]
        c["dispositivos"].append({**disp, "copiar": True, "ultima": None, "enviado_hasta": 0, "recibido_hasta": 0})
        _guardar()
    _estado["en_linea"][disp["id"]] = {"ip": disp["ip"], "puerto": disp.get("puerto"), "visto": time.time()}


def _quitar(did: str) -> None:
    c = _config()
    with _candado:
        c["dispositivos"] = [x for x in c["dispositivos"] if x["id"] != did]
        _guardar()
    _estado["en_linea"].pop(did, None)
    _apagar_si_sobra()
    _avisar()


def desvincular(did: str) -> None:
    disp = _dispositivo(did)
    if disp and disp.get("puerto"):
        try:
            _pedir(disp, "POST", "/sinc/olvidar", {}, timeout=5)  # si está en línea, también se olvida de este
        except Exception:
            pass
    _quitar(did)


def ajustar(did: str, cambios: dict) -> None:
    disp = _dispositivo(did)
    if not disp:
        raise RuntimeError("Ese dispositivo ya no está vinculado")
    with _candado:
        if "copiar" in cambios:
            disp["copiar"] = bool(cambios["copiar"])
        _guardar()
    _avisar()


def renombrar_este(nombre: str) -> None:
    with _candado:
        _config()["nombre"] = nombre.strip()[:60] or _nombre_dispositivo()
        _guardar()
    _avisar()


# ---------- Qué cambió aquí ----------

def _sello(datos) -> str:
    return hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _db() -> biblioteca.Biblioteca:
    return _estado["api"]._db()


def _claves_locales() -> dict[str, str]:
    """clave -> ruta de cada canción de la biblioteca (la primera si hay varias iguales)."""
    claves: dict[str, str] = {}
    for r in _db()._q("SELECT clave, ruta FROM canciones WHERE clave IS NOT NULL AND clave != '' ORDER BY id"):
        claves.setdefault(r["clave"], r["ruta"])
    return claves


def _proyeccion() -> dict[tuple[str, str], object]:
    """Cómo está ahora todo lo que se sincroniza, menos el historial (que solo crece: ver `_refrescar_eventos`)."""
    db = _db()
    p: dict[tuple[str, str], object] = {}
    for r in db._q("SELECT * FROM me_gusta"):
        portada = r["portada"] if (r["portada"] or "").startswith("http") else None
        p[("me_gusta", r["clave"])] = {"titulo": r["titulo"], "artista": r["artista"], "album": r["album"],
                                       "duracion": r["duracion"], "video_id": r["video_id"], "portada": portada, "fecha": r["fecha"]}
    claves_por_id = {r["id"]: r["clave"] for r in db._q("SELECT id, clave FROM canciones")}
    canciones: dict[int, list[str]] = {}
    for r in db._q("SELECT playlist_id, cancion_id FROM playlist_canciones ORDER BY playlist_id, posicion"):
        if claves_por_id.get(r["cancion_id"]):
            canciones.setdefault(r["playlist_id"], []).append(claves_por_id[r["cancion_id"]])
    for r in db._q("SELECT id, uid, nombre FROM playlists"):
        p[("playlist", r["uid"])] = {"nombre": r["nombre"], "canciones": canciones.get(r["id"], [])}
    for r in db._q("SELECT * FROM categorias"):
        p[("categoria", r["id"])] = {"nombre": r["nombre"], "generos": json.loads(r["generos"] or "[]"), "oculta": bool(r["oculta"])}
    for r in db._q("SELECT * FROM categorias_albumes"):
        p[("cat_album", json.dumps([r["album"], r["grupo"]], ensure_ascii=False))] = json.loads(r["categorias"])
    for r in db._q("SELECT cancion_id, categorias FROM categorias_canciones"):
        if claves_por_id.get(r["cancion_id"]):
            p.setdefault(("cat_cancion", claves_por_id[r["cancion_id"]]), json.loads(r["categorias"]))
    for clave in set(claves_por_id.values()):
        if clave:
            p[("cancion", clave)] = 1
    return p


def _uids_playlists() -> None:
    db = _db()
    with db.candado:
        if "uid" not in {r[1] for r in db.con.execute("PRAGMA table_info(playlists)")}:
            db.con.execute("ALTER TABLE playlists ADD COLUMN uid TEXT")
        for r in db.con.execute("SELECT id FROM playlists WHERE uid IS NULL").fetchall():
            db.con.execute("UPDATE playlists SET uid = ? WHERE id = ?", (secrets.token_hex(8), r["id"]))
        db.con.commit()


def refrescar() -> None:
    """Compara cómo está todo con cómo estaba: lo distinto es un cambio de aquí (gana sobre lo de antes)."""
    _uids_playlists()
    db, ahora = _db(), time.time()
    actual = _proyeccion()
    presentes = {k[1] for k in actual if k[0] == "cancion"}
    with db.candado:
        guardados = {(r["tipo"], r["clave"]): (r["huella"], r["borrado"])
                     for r in db.con.execute("SELECT tipo, clave, huella, borrado FROM sinc_registros WHERE tipo NOT IN ('evento', 'evento_ultimo')")}
        cambios = []
        for k, datos in actual.items():
            sello = _sello(datos)
            antes = guardados.get(k)
            if antes is None or antes[0] != sello or antes[1]:
                cambios.append((k[0], k[1], ahora, ahora, 0, sello, json.dumps(datos, ensure_ascii=False)))
        for k, (huella, borrado) in guardados.items():
            if borrado or k in actual:
                continue
            # La categoría de una canción que todavía no llega no está "borrada": está esperando su canción
            if k[0] == "cat_cancion" and k[1] not in presentes:
                continue
            cambios.append((k[0], k[1], ahora, ahora, 1, None, None))
        db.con.executemany("""INSERT INTO sinc_registros(tipo, clave, mod, cambio, borrado, huella, datos) VALUES (?,?,?,?,?,?,?)
                              ON CONFLICT(tipo, clave) DO UPDATE SET mod=excluded.mod, cambio=excluded.cambio,
                              borrado=excluded.borrado, huella=excluded.huella,
                              datos=COALESCE(excluded.datos, CASE WHEN excluded.borrado THEN NULL ELSE datos END)""", cambios)
        db.con.commit()
    _refrescar_eventos()


def _refrescar_eventos() -> None:
    db = _db()
    with db.candado:
        ultimo = db.con.execute("SELECT COALESCE(MAX(CAST(datos AS INTEGER)), 0) FROM sinc_registros WHERE tipo = 'evento_ultimo'").fetchone()[0]
        filas = db.con.execute("SELECT * FROM eventos WHERE id > ? ORDER BY id", (ultimo,)).fetchall()
        if not filas:
            return
        ahora = time.time()
        nuevos = []
        for r in filas:
            datos = _evento(r)
            if datos:
                nuevos.append(("evento", _clave_evento(datos), datos["fecha"], ahora, 0, None, json.dumps(datos, ensure_ascii=False)))
        db.con.executemany("INSERT OR IGNORE INTO sinc_registros(tipo, clave, mod, cambio, borrado, huella, datos) VALUES (?,?,?,?,?,?,?)", nuevos)
        db.con.execute("INSERT OR REPLACE INTO sinc_registros(tipo, clave, datos) VALUES ('evento_ultimo', '', ?)", (str(filas[-1]["id"]),))
        db.con.commit()


def _evento(r) -> dict | None:
    ruta = r["ruta"] or ""
    if not r["titulo"] or not r["fecha"]:
        return None
    portada = r["portada"] if (r["portada"] or "").startswith("http") else None
    return {"tipo": r["tipo"], "artista": r["artista"] or "", "titulo": r["titulo"], "fecha": round(r["fecha"], 3),
            "duracion": r["duracion"], "portada": portada, "yt": ruta[3:] if ruta.startswith("yt:") else None}


def _clave_evento(e: dict) -> str:
    return hashlib.sha1(f"{e['tipo']}|{biblioteca.clave(e['artista'], e['titulo'])}|{e['fecha']:.3f}".encode()).hexdigest()


def _exportar(disp: dict, desde: float) -> dict:
    """Lo que este le manda al otro: sus cambios desde `desde` (hora de aquí) y qué canciones tiene."""
    refrescar()
    db = _db()
    registros = [{"tipo": r["tipo"], "clave": r["clave"], "mod": r["mod"], "borrado": r["borrado"],
                  "datos": json.loads(r["datos"]) if r["datos"] else None}
                 for r in db._q("""SELECT * FROM sinc_registros WHERE cambio > ? AND tipo NOT IN ('cancion', 'evento_ultimo')""", (desde,))]
    canciones = [r["clave"] for r in db._q("SELECT clave FROM sinc_registros WHERE tipo = 'cancion' AND borrado = 0")]
    canciones += [r["clave"] for r in db._q("SELECT r.clave FROM sinc_recibidas r JOIN canciones c ON c.ruta = r.ruta")]
    tumbas = [r["clave"] for r in db._q("SELECT clave FROM sinc_registros WHERE tipo = 'cancion' AND borrado = 1")]
    return {"hora": time.time(), "registros": registros, "canciones": sorted(set(canciones)), "tumbas": tumbas,
            "acepta": disp.get("copiar", True), "libre": _libre()}


def _libre() -> int:
    try:
        return shutil.disk_usage(plataforma.carpeta_musica()).free
    except OSError:
        return 0


def _desfase(hora_otro) -> float:
    """Cuánto va adelantado el reloj del otro (para comparar sus fechas con las de aquí)."""
    try:
        return float(hora_otro) - time.time()
    except (TypeError, ValueError):
        return 0.0


# ---------- Aplicar lo del otro ----------

def fusionar(registros: list[dict], desfase: float = 0.0) -> int:
    """Aplica lo que el otro cambió si es más reciente que lo de aquí. Devuelve cuántos se aplicaron."""
    if not registros:
        return 0
    refrescar()  # lo que cambiaste aquí y no se ha anotado debe competir con su fecha real
    db, ahora, aplicados, tocados = _db(), time.time(), 0, []
    for r in registros:
        tipo, clave = r["tipo"], r["clave"]
        if tipo not in _APLICAR:
            continue
        mod = float(r["mod"]) - desfase
        aqui = db._q("SELECT mod, borrado FROM sinc_registros WHERE tipo = ? AND clave = ?", (tipo, clave))
        if tipo == "evento":
            if aqui:
                continue
        elif aqui and aqui[0]["mod"] >= mod:
            continue
        try:
            adoptada = _APLICAR[tipo](clave, None if r["borrado"] else r["datos"])
        except Exception as e:  # una cosa que no se pudo aplicar no detiene las demás
            print(f"[sinc] {tipo} {clave[:30]}: {e}", file=sys.stderr)
            continue
        aplicados += 1
        if adoptada:
            # Se juntó con algo de aquí (una playlist con el mismo nombre): el resultado es un cambio nuevo para los dos
            mod, datos = ahora, adoptada
        else:
            datos = None if r["borrado"] else r["datos"]
        db._w("""INSERT OR REPLACE INTO sinc_registros(tipo, clave, mod, cambio, borrado, huella, datos) VALUES (?,?,?,?,?,?,?)""",
              (tipo, clave, mod, ahora, 1 if r["borrado"] else 0, None, json.dumps(datos, ensure_ascii=False) if datos is not None else None))
        if tipo != "evento":
            tocados.append((tipo, clave))
    _poner_huellas(tocados)
    if aplicados:
        _estado["api"].emitir("biblioteca", {"nuevas": 0, "quitadas": 0, "total": db.total()})
    return aplicados


def _poner_huellas(claves: list[tuple[str, str]]) -> None:
    """Anota cómo quedó aquí lo que se aplicó: así el siguiente `refrescar` no lo toma por un cambio tuyo."""
    if not claves:
        return
    actual, db = _proyeccion(), _db()
    with db.candado:
        db.con.executemany("UPDATE sinc_registros SET huella = ? WHERE tipo = ? AND clave = ?",
                           [(_sello(actual.get(k)), k[0], k[1]) for k in claves])
        db.con.commit()


def _ids_de(clave: str) -> list[int]:
    return [r["id"] for r in _db()._q("SELECT id FROM canciones WHERE clave = ?", (clave,))]


def _aplicar_me_gusta(clave, d):
    db = _db()
    if d is None:
        return db._w("DELETE FROM me_gusta WHERE clave = ?", (clave,)) and None
    db._w("""INSERT OR REPLACE INTO me_gusta(clave, titulo, artista, album, duracion, portada, video_id, fecha)
             VALUES (?,?,?,?,?,?,?,?)""", (clave, d["titulo"], d["artista"], d.get("album"), d.get("duracion"),
                                          d.get("portada"), d.get("video_id"), d.get("fecha") or time.time()))


def _aplicar_playlist(uid, d):
    db = _db()
    fila = db._q("SELECT id FROM playlists WHERE uid = ?", (uid,))
    if d is None:
        if fila:
            _estado["api"].borrar_playlist({"id": fila[0]["id"]})  # también quita su carátula
        return None
    adoptada = None
    with db.candado:
        if fila:
            pid = fila[0]["id"]
        else:
            # Ya había una con el mismo nombre (la hiciste en los dos antes de vincular): se vuelve la misma
            igual = db.con.execute("SELECT id, uid FROM playlists WHERE nombre = ?", (d["nombre"],)).fetchone()
            if igual:
                pid = igual["id"]
                db.con.execute("UPDATE playlists SET uid = ? WHERE id = ?", (uid, pid))
                suyas = [db.con.execute("SELECT clave FROM canciones WHERE id = ?", (r["cancion_id"],)).fetchone()["clave"]
                         for r in db.con.execute("SELECT cancion_id FROM playlist_canciones WHERE playlist_id = ? ORDER BY posicion", (pid,))]
                db.con.execute("DELETE FROM sinc_registros WHERE tipo = 'playlist' AND clave = ?", (igual["uid"],))
                d = {**d, "canciones": d["canciones"] + [c for c in suyas if c and c not in d["canciones"]]}
                adoptada = d
            else:
                pid = db.con.execute("INSERT INTO playlists(nombre, creada, uid) VALUES (?, ?, ?)",
                                     (_nombre_libre(d["nombre"], None), time.time(), uid)).lastrowid
        db.con.execute("UPDATE playlists SET nombre = ? WHERE id = ?", (_nombre_libre(d["nombre"], pid), pid))
        db.con.execute("DELETE FROM playlist_canciones WHERE playlist_id = ?", (pid,))
        vistos, pos = set(), 0
        for clave in d["canciones"]:
            ids = [r["id"] for r in db.con.execute("SELECT id FROM canciones WHERE clave = ? ORDER BY id LIMIT 1", (clave,))]
            if ids and ids[0] not in vistos:
                pos += 1
                vistos.add(ids[0])
                db.con.execute("INSERT INTO playlist_canciones(playlist_id, cancion_id, posicion) VALUES (?,?,?)", (pid, ids[0], pos))
        db.con.commit()
    return adoptada


def _nombre_libre(nombre: str, pid: int | None) -> str:
    """El nombre es único: si ya hay otra playlist que se llama igual, se le agrega (2), (3)…"""
    db, base, n = _db(), nombre, 1
    while db._q("SELECT 1 FROM playlists WHERE nombre = ? AND id IS NOT ?", (nombre, pid)):
        n += 1
        nombre = f"{base} ({n})"
    return nombre


def _aplicar_categoria(cid, d):
    if d is None:
        return _db().borrar_categoria(cid)
    _db().guardar_categoria(cid, d["nombre"], d.get("generos") or [], bool(d.get("oculta")))


def _aplicar_cat_album(clave, d):
    album, grupo = json.loads(clave)
    db = _db()
    if d is None:
        db._w("DELETE FROM categorias_albumes WHERE album = ? AND grupo = ?", (album, grupo))
    else:
        db.poner_categorias_album(album, grupo, d)


def _aplicar_cat_cancion(clave, d):
    ids = _ids_de(clave)
    if d is None:
        for i in ids:
            _db()._w("DELETE FROM categorias_canciones WHERE cancion_id = ?", (i,))
    elif ids:
        _db().mover_a_categorias([{"id": i, "categorias": d} for i in ids])


def _aplicar_evento(clave, d):
    if d is None:
        return
    c = biblioteca.clave(d["artista"], d["titulo"])
    if _db()._q("SELECT 1 FROM sinc_registros WHERE tipo = 'cancion' AND clave = ? AND borrado = 1", (c,)):
        return  # la borraste aquí: su historial se fue con ella
    ruta = f"yt:{d['yt']}" if d.get("yt") else (_claves_locales_una(c) or f"sinc:{c}")
    _db()._w("INSERT INTO eventos(tipo, ruta, artista, titulo, fecha, duracion, portada) VALUES (?,?,?,?,?,?,?)",
             (d["tipo"], ruta, d["artista"], d["titulo"], d["fecha"], d.get("duracion"), d.get("portada")))


def _claves_locales_una(clave: str) -> str | None:
    fila = _db()._q("SELECT ruta FROM canciones WHERE clave = ? ORDER BY id LIMIT 1", (clave,))
    return fila[0]["ruta"] if fila else None


_APLICAR = {"me_gusta": _aplicar_me_gusta, "playlist": _aplicar_playlist, "categoria": _aplicar_categoria,
            "cat_album": _aplicar_cat_album, "cat_cancion": _aplicar_cat_cancion, "evento": _aplicar_evento}


def _reaplicar_pendientes() -> None:
    """Llegaron canciones: las playlists y categorías que las esperaban ya pueden tenerlas, y su historial también."""
    db, actual, tocados = _db(), _proyeccion(), []
    for r in db._q("SELECT tipo, clave, datos FROM sinc_registros WHERE tipo IN ('playlist', 'cat_cancion') AND borrado = 0"):
        datos = json.loads(r["datos"]) if r["datos"] else None
        if datos is None or _sello(actual.get((r["tipo"], r["clave"]))) == _sello(datos):
            continue
        try:
            _APLICAR[r["tipo"]](r["clave"], datos)
            tocados.append((r["tipo"], r["clave"]))
        except Exception as e:
            print(f"[sinc] reaplicar {r['tipo']}: {e}", file=sys.stderr)
    _poner_huellas(tocados)
    with db.candado:
        for r in db.con.execute("SELECT DISTINCT ruta FROM eventos WHERE ruta LIKE 'sinc:%'").fetchall():
            local = _claves_locales_una(r["ruta"][5:])
            if local:
                db.con.execute("UPDATE eventos SET ruta = ? WHERE ruta = ?", (local, r["ruta"]))
        db.con.commit()


# ---------- Canciones ----------

def _ruta_de(clave: str) -> Path | None:
    for r in _db()._q("""SELECT ruta FROM canciones WHERE clave = ?
                         UNION ALL SELECT ruta FROM sinc_recibidas WHERE clave = ?""", (clave, clave)):
        if Path(r["ruta"]).exists():
            return Path(r["ruta"])
    return None


def _seguro(texto: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto or "").strip(" .")[:120] or "Desconocido"


def _guardar_cancion(origen, tamano: int, clave: str, nombre: str, artista: str) -> Path:
    """Escribe la canción que llega en la carpeta de descargas (por artista) y la agrega a la biblioteca."""
    if _libre() - tamano < LIBRE_MINIMO:
        raise OSError("Sin espacio")
    carpeta = plataforma.carpeta_musica() / _seguro(biblioteca.artista_principal(artista))
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = _seguro(nombre)
    destino = carpeta / nombre
    n = 1
    while destino.exists():
        n += 1
        destino = carpeta / f"{Path(nombre).stem} ({n}){Path(nombre).suffix}"
    temporal = destino.with_name(destino.name + ".parte")
    restante = tamano
    with open(temporal, "wb") as f:
        while restante > 0:
            bloque = origen.read(min(256 * 1024, restante))
            if not bloque:
                break
            f.write(bloque)
            restante -= len(bloque)
    if restante:
        temporal.unlink(missing_ok=True)
        raise OSError("Se cortó la conexión")
    temporal.replace(destino)
    _estado["api"]._indexar(destino)
    _db()._w("INSERT OR REPLACE INTO sinc_recibidas(clave, ruta) VALUES (?, ?)", (clave, str(destino)))
    plataforma.archivo_nuevo(destino)
    return destino


def _recibir_cancion(origen, tamano: int, q: dict) -> tuple[dict, int]:
    clave = q.get("clave", "")
    if not clave or tamano <= 0:
        return {"error": "Datos incompletos"}, 400
    if _ruta_de(clave):
        origen.read(tamano)  # ya la tenía (llegó por otro lado mientras tanto)
        return {"ok": True, "ya": True}, 200
    try:
        _guardar_cancion(origen, tamano, clave, q.get("nombre", "cancion"), q.get("artista", ""))
    except OSError as e:
        return {"error": str(e), "sin_espacio": "espacio" in str(e)}, 507
    return {"ok": True}, 200


def _terminar_recepcion(disp: dict, d: dict) -> None:
    _reaplicar_pendientes()
    _liberar_sesion(disp["id"])
    disp["ultima"] = time.time()
    disp.pop("error", None)
    with _candado:
        _guardar()
    _estado["api"].emitir("biblioteca", {"nuevas": d.get("recibidas", 0), "quitadas": 0, "total": _db().total()})
    _avisar()


# ---------- Sesión (quién se está sincronizando con quién) ----------

def _tomar_sesion(did: str) -> bool:
    with _sesion_candado:
        actual = _estado["sesion"]
        # Si el otro dejó de pedir cosas hace rato, se fue a media sincronización: su sesión ya no cuenta
        if (actual and actual[0] != did and time.time() - actual[1] < SESION_INACTIVA) or (_estado["trabajando"] and _estado["trabajando"] != did):
            return False
        _estado["sesion"] = (did, time.time())
    _avisar()
    return True


def _liberar_sesion(did: str) -> None:
    with _sesion_candado:
        if _estado["sesion"] and _estado["sesion"][0] == did:
            _estado["sesion"] = None


def sincronizar_con(did: str) -> bool:
    """Empieza a sincronizarse con un vinculado en segundo plano. False si ya había algo en curso."""
    with _sesion_candado:
        if _estado["trabajando"] or (_estado["sesion"] and time.time() - _estado["sesion"][1] < SESION_INACTIVA):
            return False
        _estado["trabajando"] = did
    _estado["intentos"][did] = time.time()
    threading.Thread(target=_sincronizar, args=(did,), daemon=True).start()
    return True


def _progreso(did: str, texto: str | None, hechas: int = 0, total: int = 0) -> None:
    _estado["progreso"] = {"id": did, "texto": texto, "hechas": hechas, "total": total} if texto else None
    api = _estado["api"]
    api._fondo_actualizar("sincronizacion", texto, int(hechas * 100 / total) if total else -1)
    _avisar()


def _sincronizar(did: str) -> None:
    disp = _dispositivo(did)
    api = _estado["api"]
    recibidas, empezada = 0, False
    try:
        if not disp or not disp.get("puerto"):
            return
        _progreso(did, api._t("Sincronizando con {nombre}", nombre=disp["nombre"]))
        refrescar()
        inicio = time.time()
        r = _pedir(disp, "POST", "/sinc/estado", {"desde": disp.get("recibido_hasta", 0), "puerto": _estado["puerto"]})
        empezada = True
        desfase = r["hora"] - (inicio + time.time()) / 2
        fusionar(r["registros"], desfase)
        db = _db()
        mios = [{"tipo": x["tipo"], "clave": x["clave"], "mod": x["mod"], "borrado": x["borrado"],
                 "datos": json.loads(x["datos"]) if x["datos"] else None}
                for x in db._q("SELECT * FROM sinc_registros WHERE cambio > ? AND tipo NOT IN ('cancion', 'evento_ultimo')",
                               (disp.get("enviado_hasta", 0),))]
        hora_envio = time.time()
        for i in range(0, len(mios), 2000):
            _pedir(disp, "POST", "/sinc/aplicar", {"registros": mios[i:i + 2000], "hora": time.time()}, timeout=120)

        # Canciones: las que le faltan a cada uno, menos las que cada quien borró
        locales = _claves_locales()
        mis_tumbas = {x["clave"] for x in db._q("SELECT clave FROM sinc_registros WHERE tipo = 'cancion' AND borrado = 1")}
        recibidas_antes = {x["clave"] for x in db._q("SELECT clave FROM sinc_recibidas")}
        suyas = set(r["canciones"])
        mandar = [c for c in locales if c not in suyas and c not in set(r["tumbas"])] if r.get("acepta") else []
        traer = [c for c in suyas if c not in locales and c not in mis_tumbas and c not in recibidas_antes] if disp.get("copiar", True) else []
        total, hechas, sin_espacio_alla = len(mandar) + len(traer), 0, False
        for clave in mandar:
            ruta = _ruta_de(clave)
            if not ruta:
                continue
            _progreso(did, api._t("Copiando canciones a {nombre}", nombre=disp["nombre"]), hechas, total)
            fila = db._q("SELECT artista FROM canciones WHERE ruta = ?", (str(ruta),))
            consulta = urllib.parse.urlencode({"clave": clave, "nombre": ruta.name, "artista": fila[0]["artista"] if fila else ""})
            try:
                _pedir(disp, "PUT", f"/sinc/cancion?{consulta}", archivo=ruta, timeout=300)
            except urllib.error.HTTPError as e:
                if e.code == 507:
                    sin_espacio_alla = True
                    break
            hechas += 1
        for clave in traer:
            _progreso(did, api._t("Copiando canciones de {nombre}", nombre=disp["nombre"]), hechas, total)
            if _libre() < LIBRE_MINIMO:
                disp["error"] = api._t("Sin espacio en este dispositivo")
                break
            try:
                _traer(disp, clave)
                recibidas += 1
            except (OSError, RuntimeError) as e:
                print(f"[sinc] traer {clave[:30]}: {e}", file=sys.stderr)
            hechas += 1
        if recibidas:
            _reaplicar_pendientes()
        _pedir(disp, "POST", "/sinc/fin", {"recibidas": len(mandar) if not sin_espacio_alla else 0})
        empezada = False
        disp["recibido_hasta"] = r["hora"] - 5  # 5 s de margen por si algo cambió mientras se armaba la respuesta
        disp["enviado_hasta"] = hora_envio - 5
        disp["ultima"] = time.time()
        if sin_espacio_alla:
            disp["error"] = api._t("{nombre} se quedó sin espacio", nombre=disp["nombre"])
        elif "error" in disp and disp["error"] != api._t("Sin espacio en este dispositivo"):
            disp.pop("error", None)
    except urllib.error.HTTPError as e:
        try:
            cuerpo = json.loads(e.read())
        except ValueError:
            cuerpo = {}
        if cuerpo.get("desvinculado"):
            _quitar(did)  # el otro ya no te tiene: no tiene caso seguir intentando
            return
        if not cuerpo.get("ocupado") and disp:
            disp["error"] = cuerpo.get("error") or f"HTTP {e.code}"
    except (OSError, RuntimeError, ValueError, KeyError) as e:
        if disp:
            disp["error"] = str(e) if isinstance(e, RuntimeError) else api._t("No se pudo conectar")
        print(f"[sinc] {e}", file=sys.stderr)
    finally:
        if empezada and disp:
            try:
                _pedir(disp, "POST", "/sinc/soltar", {}, timeout=5)
            except Exception:
                pass
        with _sesion_candado:
            _estado["trabajando"] = None
        with _candado:
            if _dispositivo(did):
                _guardar()
        _progreso(did, None)
        if recibidas:
            api.emitir("biblioteca", {"nuevas": recibidas, "quitadas": 0, "total": _db().total()})


def _traer(disp: dict, clave: str) -> None:
    hora = str(int(time.time() * 1000))
    ruta = f"/sinc/archivo?{urllib.parse.urlencode({'clave': clave})}"
    peticion = urllib.request.Request(f"http://{disp['ip']}:{disp['puerto']}{ruta}")
    peticion.add_header("X-Sinc-Id", _config()["id"])
    peticion.add_header("X-Sinc-Hora", hora)
    peticion.add_header("X-Sinc-Firma", _firma(disp["secreto"], "GET", ruta, hora, _huella(b"")))
    with urllib.request.urlopen(peticion, timeout=300) as r:
        nombre = urllib.parse.unquote(r.headers.get("X-Nombre") or "cancion")
        artista = urllib.parse.unquote(r.headers.get("X-Artista") or "") or clave.split("|", 1)[0]
        _guardar_cancion(r, int(r.headers.get("Content-Length") or 0), clave, nombre, artista)
