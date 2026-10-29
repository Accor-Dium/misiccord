// Cliente de jams: la interfaz habla directo con el servidor del anfitrión (HTTP + eventos SSE).
// El anfitrión usa este mismo cliente contra su propio servidor (127.0.0.1).
import { py } from "./api.js";
import { aviso, mostrarHoja } from "./estado.svelte.js";
import { alternar, preguntarAlReproducirEnJam, rep } from "./reproductor.svelte.js";
import { t } from "./idioma.svelte.js";

export const jam = $state({
  sala: null, // estado que manda el servidor
  conexion: null, // { base, codigo, cliente, rol, nombre, ips, puerto }
  escuchando: true, // reproducir aquí (en modo sincronizado o si eres el anfitrión)
  desfase: 0, // ms que hay que sumarle al reloj local para tener el del anfitrión
  conectado: false,
  invitacion: null, // datos de un link de jam con el que se abrió la app (falta unirse)
});

const audio = new Audio();
audio.preload = "auto";
let eventos = null;

// El audio del jam usa el mismo volumen que el reproductor normal
$effect.root(() => {
  $effect(() => {
    audio.volume = rep.volumen;
    audio.muted = rep.silencio;
  });
});

export const soyAnfitrion = () => jam.conexion?.rol === "anfitrion";
export const pistaActual = () => {
  const s = jam.sala;
  return s && s.indice >= 0 && s.indice < s.cola.length ? s.cola[s.indice] : null;
};

/** URL absoluta de algo del servidor (audio, portada local) con el código incluido. */
export function urlJam(ruta) {
  if (!ruta) return null;
  if (/^https?:\/\//.test(ruta)) return ruta;
  return `${jam.conexion.base}${ruta}?codigo=${jam.conexion.codigo}`;
}

async function pedir(ruta, datos) {
  let r;
  try {
    r = await fetch(jam.conexion.base + ruta, {
      method: datos ? "POST" : "GET",
      headers: { "X-Codigo": jam.conexion.codigo, "Content-Type": "application/json" },
      body: datos ? JSON.stringify({ cliente: jam.conexion.cliente, ...datos }) : undefined,
      // Sin límite, un jam que no se alcanza (otra red, anfitrión apagado) se quedaría "conectando" para siempre
      signal: AbortSignal.timeout(ruta.startsWith("/buscar") ? 30000 : 12000),
    });
  } catch {
    throw new Error(jam.conexion.base.startsWith("https://")
      ? t("No se pudo conectar con el jam. ¿El anfitrión lo sigue teniendo abierto a internet?")
      : t("No se pudo conectar con el jam. Conéctate a la misma red Wi-Fi que el anfitrión."));
  }
  const cuerpo = await r.json();
  if (!r.ok) throw new Error(cuerpo.error || `Error ${r.status}`);
  return cuerpo;
}

/** Estima la diferencia de reloj con el anfitrión (como NTP): se queda con la medición más rápida. */
async function sincronizarReloj() {
  let mejor = null;
  for (let i = 0; i < 5; i++) {
    const t0 = Date.now();
    const { ms } = await pedir("/hora");
    const t1 = Date.now();
    const rtt = t1 - t0;
    if (!mejor || rtt < mejor.rtt) mejor = { rtt, desfase: ms - (t0 + rtt / 2) };
  }
  jam.desfase = mejor.desfase;
}

/** Por internet (túnel de Cloudflare) no pasa SSE: se pregunta "¿algo nuevo?" y el anfitrión contesta al cambiar. */
async function sondear(conexion) {
  while (jam.conexion === conexion) {
    try {
      const v = jam.sala?.version ?? -1;
      const r = await fetch(`${conexion.base}/esperar?codigo=${conexion.codigo}&cliente=${conexion.cliente}&version=${v}`,
                            { signal: AbortSignal.timeout(35000) });
      if (jam.conexion !== conexion) return;
      const d = await r.json();
      jam.conectado = r.ok;
      if (d.evento === "expulsado") return terminar(t("El anfitrión te sacó del jam"));
      if (d.evento === "cerrada") return terminar(t("El anfitrión terminó el jam"));
      if (d.estado) aplicar(d.estado);
      if (!r.ok) await new Promise((ok) => setTimeout(ok, 3000));
    } catch {
      jam.conectado = false;
      await new Promise((ok) => setTimeout(ok, 2000));
    }
  }
}

function escucharEventos() {
  eventos?.close();
  eventos = null;
  if (jam.conexion.base.startsWith("https://")) {
    sondear(jam.conexion);
    return;
  }
  const { base, codigo, cliente } = jam.conexion;
  eventos = new EventSource(`${base}/eventos?codigo=${codigo}&cliente=${cliente}`);
  eventos.onopen = () => (jam.conectado = true);
  eventos.onerror = () => (jam.conectado = false); // EventSource reintenta solo
  eventos.onmessage = (e) => aplicar(JSON.parse(e.data));
  eventos.addEventListener("expulsado", () => terminar(t("El anfitrión te sacó del jam")));
  eventos.addEventListener("cerrada", () => terminar(t("El anfitrión terminó el jam")));
}

async function conectar(conexion) {
  jam.conexion = conexion;
  await sincronizarReloj();
  const r = await pedir("/unirse", { nombre: conexion.nombre });
  jam.conexion.cliente = r.cliente;
  jam.conexion.rol = r.rol;
  aplicar(r.estado);
  escucharEventos();
}

export async function crear(nombre, modo) {
  const r = await py("jam_crear", { nombre, modo });
  await conectar({ base: `http://127.0.0.1:${r.puerto}`, codigo: r.codigo, cliente: r.cliente, nombre,
                   ips: r.ips, puerto: r.puerto, internetDisponible: r.internet_disponible, internet: null });
}

export async function unirse(ip, puerto, codigo, nombre, base = null) {
  await conectar({ base: base || `http://${ip}:${puerto}`, codigo, cliente: null, nombre, ips: [ip], puerto });
}

/** Une con lo que trae un QR o link: si estás en la misma red va directo; si no, por la dirección de internet. */
export async function unirseConDatos(datos, nombre) {
  if (datos.url) {
    const local = await fetch(`http://${datos.ip}:${datos.puerto}/info`, { signal: AbortSignal.timeout(1500) })
      .then((r) => r.ok).catch(() => false);
    if (!local) return unirse(datos.ip, datos.puerto, datos.codigo, nombre, datos.url.replace(/\/$/, ""));
  }
  return unirse(datos.ip, datos.puerto, datos.codigo, nombre);
}

/** Anfitrión: abrir o cerrar el jam a internet (túnel de Cloudflare). Devuelve la dirección pública. */
export async function abrirInternet(activar = true) {
  const { url } = await py("jam_internet", { activar });
  jam.conexion.internet = url;
  return url;
}

export async function buscarCercanos() {
  return (await py("jam_buscar", { segundos: 3 })).jams;
}

function terminar(mensaje) {
  eventos?.close();
  eventos = null;
  audio.pause();
  audio.removeAttribute("src");
  jam.sala = null;
  jam.conexion = null;
  jam.conectado = false;
  if (mensaje) aviso(mensaje);
}

export async function salir() {
  const anfitrion = soyAnfitrion();
  try {
    if (!anfitrion) await pedir("/salir", {});
  } catch {}
  terminar("");
  if (anfitrion) await py("jam_cerrar").catch(() => {});
}

// ---------- Reproducción sincronizada ----------

const posObjetivo = () => (Date.now() + jam.desfase - jam.sala.inicio_ms) / 1000;
const debeSonar = () => jam.escuchando && (jam.sala?.modo === "sincronizado" || soyAnfitrion());

function aplicar(estado) {
  jam.sala = estado;
  actualizarAudio();
}

function actualizarAudio() {
  const p = pistaActual();
  if (!p || !jam.sala.sonando || !debeSonar() || p.estado !== "lista") {
    audio.pause();
    return;
  }
  if (rep.sonando) alternar(); // el reproductor normal se pausa mientras suena el jam
  if (audio.dataset.pid !== p.pid) {
    audio.dataset.pid = p.pid;
    audio.src = urlJam(`/audio/${p.pid}`);
    audio.playbackRate = 1;
  }
  ajustar(true);
  audio.play().catch(() => {});
}

function ajustar(forzar) {
  if (!jam.sala?.sonando || audio.readyState < 1) return;
  const objetivo = posObjetivo();
  const diferencia = audio.currentTime - objetivo;
  if (forzar || Math.abs(diferencia) > 0.3) {
    audio.currentTime = Math.max(0, objetivo);
    audio.playbackRate = 1;
  } else {
    // Diferencias chicas se corrigen acelerando o frenando un poquito, sin brincos audibles
    audio.playbackRate = diferencia > 0.04 ? 0.97 : diferencia < -0.04 ? 1.03 : 1;
  }
}

audio.addEventListener("loadedmetadata", () => ajustar(true));
setInterval(() => {
  if (jam.sala?.sonando && !audio.paused) ajustar(false);
}, 1500);

export function alternarEscuchar() {
  jam.escuchando = !jam.escuchando;
  actualizarAudio();
}

/** Segundos que lleva la pista actual según el reloj del anfitrión. */
export function posicionJam() {
  if (!jam.sala) return 0;
  return jam.sala.sonando ? Math.max(0, posObjetivo()) : jam.sala.posicion;
}

// ---------- Acciones ----------

/** Agrega una canción de TU biblioteca: el anfitrión la lee directo; un invitado se la sube por la red. */
export async function agregarPropia(c) {
  if (soyAnfitrion()) return agregar(c);
  const { base, codigo, cliente } = jam.conexion;
  return py("jam_subir", { base, codigo, cliente, ruta: c.ruta, titulo: c.titulo, artista: c.artista,
                           album: c.album, duracion: c.duracion });
}

/** ¿Puedo meter canciones a la cola? (el anfitrión siempre; los invitados si él lo permite) */
export const puedoAgregar = () => !!jam.sala && (soyAnfitrion() || jam.sala.invitados_agregan);

/** Manda cualquier canción al jam desde cualquier vista: las tuyas se suben, las de YouTube las baja el anfitrión. */
export async function agregarAlJam(c) {
  try {
    if (c.ruta) {
      if (!soyAnfitrion()) aviso(t("Mandando “{titulo}” al jam…", { titulo: c.titulo }));
      await agregarPropia(c);
      aviso(t("“{titulo}” a la cola del jam", { titulo: c.titulo }), "ok");
    } else {
      await agregar(c);
      aviso(t("“{titulo}” a la cola del jam", { titulo: c.titulo }), "ok");
    }
  } catch (err) {
    aviso(err.message || t("No se pudo agregar al jam"), "error");
  }
}

// Tocar una canción para reproducirla estando en un jam: se pregunta en vez de sonar encima del jam.
// El anfitrión que "sale" cierra el jam para todos, así que se le dice.
preguntarAlReproducirEnJam((c, reproducirAqui) => {
  if (!jam.sala) return false;
  const anfitrion = soyAnfitrion();
  const opciones = [];
  if (puedoAgregar()) opciones.push({ texto: t("Mandarla al jam"), icono: "jam", accion: () => agregarAlJam(c) });
  opciones.push({
    texto: anfitrion ? t("Cerrar el jam y escucharla aquí") : t("Salir del jam y escucharla aquí"),
    icono: "play", peligro: anfitrion,
    accion: async () => {
      await salir();
      reproducirAqui();
    },
  });
  opciones.push({ texto: t("Cancelar"), icono: "cerrar", accion: () => {} });
  mostrarHoja({
    titulo: t("Estás en un jam"), subtituloLargo: true, portada: c.portada,
    subtitulo: anfitrion
      ? t("¿Mandas “{titulo}” a la cola del jam o cierras el jam (para todos) y la escuchas aquí?", { titulo: c.titulo })
      : puedoAgregar()
        ? t("¿Mandas “{titulo}” a la cola del jam o sales del jam y la escuchas aquí?", { titulo: c.titulo })
        : t("El anfitrión no deja agregar canciones. ¿Sales del jam para escuchar “{titulo}” aquí?", { titulo: c.titulo }),
    opciones,
  });
  return true;
});

/** QR del jam (SVG) para que otros se unan escaneándolo. */
export async function qrDelJam() {
  const { ips, puerto, codigo, internet } = jam.conexion;
  return py("jam_qr", { ip: ips?.[0], puerto, codigo, nombre: jam.sala?.nombre ?? "", url: internet });
}

export const control = (accion, extra = {}) => pedir("/control", { accion, ...extra });
export const votar = () => pedir("/votar", {});
export const reaccionar = (emoji) => pedir("/reaccion", { emoji });
export const agregar = (cancion) => pedir("/agregar", { cancion });
export const buscarEnAnfitrion = (q) => pedir(`/buscar?q=${encodeURIComponent(q)}`);
export const bibliotecaAnfitrion = (q = "") => pedir(`/biblioteca?q=${encodeURIComponent(q)}`);
