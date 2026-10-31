// Fotos de los artistas de tu biblioteca: mientras no haya, cada uno se ve con una carátula suya (ya está en el cel y no usa red).
// Las fotos se piden de una en una y solo de los que están en pantalla: fotoDe() la llama cada fila que se dibuja y la lista
// virtual solo dibuja las que se ven. Nunca compiten con la música: se detienen con una canción en línea sonando,
// con la app en segundo plano y, en el cel, fuera de Wi-Fi.
import { py } from "./api.js";
import { rep } from "./reproductor.svelte.js";

const PENDIENTES_MAX = 12; // si bajas rápido, las de arriba ya no se ven: se quedan fuera y se vuelven a pedir al regresar
const ENTRE_FOTOS = 1500; // ms
const SIN_RED = 300000; // ms: sin internet no tiene caso que cada fila vuelva a intentarlo

const esAndroid = /Android/i.test(navigator.userAgent);
const fotos = $state({}); // nombre → ruta de lo que llegó en esta sesión (la lista de Python ya no la trae hasta recargar)
const pendientes = [];
const pedidas = new Set();
let trabajando = false;
let sinRedHasta = 0;

const pausa = (ms) => new Promise((r) => setTimeout(r, ms));

function sePuede() {
  if (document.hidden || (rep.sonando && rep.actual && !rep.actual.ruta)) return false;
  return !esAndroid || navigator.connection?.type === "wifi";
}

async function trabajar() {
  if (trabajando) return;
  trabajando = true;
  while (pendientes.length) {
    if (!sePuede()) {
      await pausa(5000);
      continue;
    }
    const nombre = pendientes.pop(); // la última que se dibujó es la que estás viendo
    try {
      const { foto } = await py("artista_foto", { nombre });
      if (foto) fotos[nombre] = foto;
      await pausa(ENTRE_FOTOS);
    } catch {
      sinRedHasta = Date.now() + SIN_RED;
      pendientes.length = 0;
      pedidas.clear();
    }
  }
  trabajando = false;
}

/** Qué imagen ponerle a un artista de la biblioteca. */
export function fotoDe(a) {
  if (a.foto) return a.foto;
  if (fotos[a.nombre]) return fotos[a.nombre];
  if (!a.revisada && !pedidas.has(a.nombre) && Date.now() > sinRedHasta) {
    pedidas.add(a.nombre);
    pendientes.push(a.nombre);
    if (pendientes.length > PENDIENTES_MAX) pedidas.delete(pendientes.shift());
    queueMicrotask(trabajar); // fuera del dibujo: si no, esa fila dependería de `rep`
  }
  return a.portada;
}
