// Cliente de jams: la interfaz habla directo con el servidor del anfitrión (HTTP + eventos SSE).
// El anfitrión usa este mismo cliente contra su propio servidor (127.0.0.1).
import { py } from "./api.js";
import { aviso } from "./estado.svelte.js";
import { alternar, rep } from "./reproductor.svelte.js";

export const jam = $state({
  sala: null, // estado que manda el servidor
  conexion: null, // { base, codigo, cliente, rol, nombre, ips, puerto }
  escuchando: true, // reproducir aquí (en modo sincronizado o si eres el anfitrión)
  desfase: 0, // ms que hay que sumarle al reloj local para tener el del anfitrión
  conectado: false,
});

const audio = new Audio();
audio.preload = "auto";
let eventos = null;

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
  const r = await fetch(jam.conexion.base + ruta, {
    method: datos ? "POST" : "GET",
    headers: { "X-Codigo": jam.conexion.codigo, "Content-Type": "application/json" },
    body: datos ? JSON.stringify({ cliente: jam.conexion.cliente, ...datos }) : undefined,
  });
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

function escucharEventos() {
  eventos?.close();
  const { base, codigo, cliente } = jam.conexion;
  eventos = new EventSource(`${base}/eventos?codigo=${codigo}&cliente=${cliente}`);
  eventos.onopen = () => (jam.conectado = true);
  eventos.onerror = () => (jam.conectado = false); // EventSource reintenta solo
  eventos.onmessage = (e) => aplicar(JSON.parse(e.data));
  eventos.addEventListener("expulsado", () => terminar("El anfitrión te sacó del jam"));
  eventos.addEventListener("cerrada", () => terminar("El anfitrión terminó el jam"));
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
                   ips: r.ips, puerto: r.puerto });
}

export async function unirse(ip, puerto, codigo, nombre) {
  await conectar({ base: `http://${ip}:${puerto}`, codigo, cliente: null, nombre, ips: [ip], puerto });
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

export const control = (accion, extra = {}) => pedir("/control", { accion, ...extra });
export const votar = () => pedir("/votar", {});
export const reaccionar = (emoji) => pedir("/reaccion", { emoji });
export const agregar = (cancion) => pedir("/agregar", { cancion });
export const buscarEnAnfitrion = (q) => pedir(`/buscar?q=${encodeURIComponent(q)}`);
export const bibliotecaAnfitrion = (q = "") => pedir(`/biblioteca?q=${encodeURIComponent(q)}`);
