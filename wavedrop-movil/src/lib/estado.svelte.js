// Estado global de la interfaz: navegación, avisos, hojas de opciones y descargas.
import { flushSync } from "svelte";
import { alEvento, py } from "./api.js";

/** Pila de vistas por pestaña. Cada entrada: { vista: "album", ...parámetros }. */
export const nav = $state({ pestana: "inicio", pila: [{ vista: "inicio" }] });

const pantallaAmplia = window.matchMedia("(min-width: 900px)");

export const ui = $state({
  amplio: pantallaAmplia.matches, // escritorio o tablet: barra lateral y reproductor en dos columnas
  reproductorAbierto: false,
  hoja: null, // { titulo, subtitulo, portada, opciones: [{ texto, icono, accion }] }
  avisos: [],
  version: 0, // sube cuando cambia la biblioteca, para que las vistas recarguen
  alAtras: null, // qué hacer con el próximo "atrás" (p. ej. cerrar la cámara del QR)
});

pantallaAmplia.addEventListener("change", (e) => (ui.amplio = e.matches));

export const descargas = $state({ trabajos: {} });

/** Cambia el DOM con una animación suave (View Transitions); si el navegador no la tiene, sin animación. */
function transicion(cambio, direccion) {
  document.documentElement.dataset.dir = direccion;
  if (!document.startViewTransition) {
    cambio();
    return;
  }
  document.startViewTransition(() => flushSync(cambio));
}

export function irPestana(pestana) {
  if (nav.pestana === pestana && nav.pila.length === 1) {
    document.querySelector("main")?.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  transicion(() => {
    nav.pestana = pestana;
    nav.pila = [{ vista: pestana }];
  }, "lado");
}

export function abrir(vista, parametros = {}) {
  transicion(() => nav.pila.push({ vista, ...parametros }), "adelante");
  history.pushState({ wavedrop: true }, "");
}

export function atras() {
  if (nav.pila.length > 1) transicion(() => nav.pila.pop(), "atras");
}

export function abrirReproductor() {
  ui.reproductorAbierto = true;
  history.pushState({ wavedrop: "reproductor" }, "");
}

export function cerrarReproductor() {
  if (ui.reproductorAbierto) history.back();
}

// El botón/gesto "atrás" de Android cierra primero la hoja o el reproductor y luego regresa de vista
// (alAtras: algo nativo encima de la app, como la cámara del QR, que se cierra con "atrás")
window.addEventListener("popstate", () => {
  if (ui.alAtras) {
    const f = ui.alAtras;
    ui.alAtras = null;
    f();
  } else if (ui.hoja) ui.hoja = null;
  else if (ui.reproductorAbierto) ui.reproductorAbierto = false;
  else atras();
});

export function aviso(texto, tipo = "info") {
  const id = Math.random().toString(36).slice(2);
  ui.avisos.push({ id, texto, tipo });
  setTimeout(() => (ui.avisos = ui.avisos.filter((a) => a.id !== id)), 3200);
}

export function mostrarHoja(hoja) {
  ui.hoja = hoja;
  history.pushState({ wavedrop: "hoja" }, "");
}

export function cerrarHoja() {
  if (ui.hoja) history.back();
}

// ---------- Descargas ----------

alEvento("descarga", ({ trabajo }) => {
  descargas.trabajos[trabajo.id] = trabajo;
  if (trabajo.estado === "listo") {
    ui.version++;
    aviso(`“${trabajo.titulo}” ya está en tu biblioteca`, "ok");
  } else if (trabajo.estado === "error") {
    aviso(`No se pudo descargar “${trabajo.titulo}”`, "error");
  }
});
alEvento("video_descarga", (d) => {
  if (d.estado === "listo") aviso(`Video de “${d.titulo}” descargado`, "ok");
  else if (d.estado === "error") aviso(`No se pudo bajar el video de “${d.titulo}”: ${d.error}`, "error");
});
alEvento("biblioteca", () => ui.version++);

/**
 * Android: la primera vez que se baja algo se pide permiso para mostrar la notificación de avance (Android 13+).
 * Sin ella igual sigue trabajando en segundo plano, pero sin que se vea. Después solo se pide desde Ajustes.
 */
export async function pedirAvisosUnaVez() {
  if (!/Android/i.test(navigator.userAgent)) return;
  try {
    if (localStorage.getItem("misiccord_pidio_avisos")) return;
    localStorage.setItem("misiccord_pidio_avisos", "1");
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("segundo_plano", { pedir: "notificaciones" });
  } catch {}
}

export async function descargar(canciones, coleccion = "") {
  const lista = canciones.filter((c) => !c.local && !c.ruta && c.id);
  if (!lista.length) return;
  await pedirAvisosUnaVez();
  const r = await py("descargar", { canciones: lista, coleccion });
  for (const t of r.trabajos) descargas.trabajos[t.id] = t;
  aviso(lista.length === 1 ? `Descargando “${lista[0].titulo}”` : `${lista.length} canciones en la cola`);
}

export async function descargarLink(url) {
  await pedirAvisosUnaVez();
  const r = await py("descargar", { url });
  for (const t of r.trabajos) descargas.trabajos[t.id] = t;
  aviso(`${r.trabajos.length} canciones de “${r.coleccion}” en la cola`);
}

/** Estado de descarga de una canción de YouTube Music, buscándola por título y artista. */
export function estadoDescarga(c) {
  if (c.local || c.ruta) return { estado: "listo" };
  for (const t of Object.values(descargas.trabajos)) {
    if (t.titulo === c.titulo && t.artista === c.artista) return t;
  }
  return null;
}

export const activas = () =>
  Object.values(descargas.trabajos).filter((t) => ["cola", "buscando", "descargando", "etiquetando"].includes(t.estado)).length;
