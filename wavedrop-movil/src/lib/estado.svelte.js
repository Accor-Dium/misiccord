// Estado global de la interfaz: navegación, avisos, hojas de opciones y descargas.
import { flushSync } from "svelte";
import { alEvento, py } from "./api.js";
import { t } from "./idioma.svelte.js";

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
  info: null, // canción abierta en la ventana de información y etiquetas (InfoCancion.svelte)
  letra: { traducirA: "", romanizar: true }, // ajustes de las letras (se cargan al iniciar y desde Ajustes)
});

export function aplicarAjustesLetra(aj) {
  ui.letra = { traducirA: aj.letra_traducir_a || "", romanizar: aj.letra_romanizar !== false };
}

/** Abre la ventana de información de una canción (en descargadas también se editan etiquetas y carátula). */
export function verInfo(c) {
  ui.info = c;
}

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

/** Pone o quita "Me gusta" (descargada o vista previa). Devuelve si quedó con Me gusta. */
export async function alternarMeGusta(c) {
  try {
    const { gusta } = await py("me_gusta_alternar", {
      titulo: c.titulo, artista: c.artista, album: c.album, duracion: c.duracion, portada: c.portada, id: c.id,
    });
    aviso(t(gusta ? "“{titulo}” está en tus Me gusta" : "Se quitó “{titulo}” de tus Me gusta", { titulo: c.titulo }), gusta ? "ok" : "info");
    return gusta;
  } catch (e) {
    aviso(e.message, "error");
    return null;
  }
}

/** El álbum de una canción: el de tu biblioteca si la tienes, si no el de YouTube Music (por id o buscándolo). */
export function abrirAlbumDe(c) {
  if (!c?.album) return;
  if (c.album_id) return abrir("album", { id: c.album_id });
  if (c.db_id) {
    // Así agrupa la biblioteca: nombre del álbum + "artista del álbum" tal cual viene en el archivo ("" si no trae)
    return abrir("album", { local: { nombre: c.album, artista: c.artista_album || c.artista, grupo: c.artista_album || "", portada: c.portada } });
  }
  abrir("album", { buscar: `${c.album} ${c.artista.split(",")[0]}`, nombre: c.album });
}

/** Abre una tarjeta de YouTube Music (álbum, playlist o artista) de Inicio o Explorar. */
export function abrirTarjeta(x) {
  if (x.tipo === "album") abrir("album", { id: x.id });
  else if (x.tipo === "playlist") abrir("album", { playlist: x.id, nombre: x.titulo });
  else if (x.tipo === "artista") abrir("artista", { id: x.id, nombre: x.titulo });
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

const relojes = {};

/**
 * Aviso flotante (componentes/Avisos.svelte). tipo: "info" | "ok" | "error".
 * extra.id: un aviso con el mismo id se reemplaza en su lugar (p. ej. el avance de una copia).
 * extra.duracion: ms en pantalla (0 = hasta que se reemplace o se toque). extra.accion: { texto, f }.
 * extra.avance: 0–1 para una barrita de progreso.
 */
export function aviso(texto, tipo = "info", extra = {}) {
  const id = extra.id ?? Math.random().toString(36).slice(2);
  const duracion = extra.duracion ?? (extra.accion ? 5000 : tipo === "error" ? 4500 : 3000);
  const nuevo = { id, texto, tipo, accion: extra.accion ?? null, avance: extra.avance ?? null };
  const i = ui.avisos.findIndex((a) => a.id === id);
  if (i >= 0) ui.avisos[i] = nuevo;
  else {
    ui.avisos.push(nuevo);
    if (ui.avisos.length > 3) quitarAviso(ui.avisos[0].id); // no se apilan más de 3
  }
  clearTimeout(relojes[id]);
  if (duracion) relojes[id] = setTimeout(() => quitarAviso(id), duracion);
  return id;
}

export function quitarAviso(id) {
  clearTimeout(relojes[id]);
  delete relojes[id];
  ui.avisos = ui.avisos.filter((a) => a.id !== id);
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
    aviso(t("“{titulo}” ya está en tu biblioteca", { titulo: trabajo.titulo }), "ok");
  } else if (trabajo.estado === "error") {
    aviso(t("No se pudo descargar “{titulo}”", { titulo: trabajo.titulo }), "error");
  }
});
alEvento("video_descarga", (d) => {
  if (d.estado === "listo") aviso(t("Video de “{titulo}” descargado", d), "ok");
  else if (d.estado === "error") aviso(t("No se pudo bajar el video de “{titulo}”: {error}", d), "error");
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
  aviso(lista.length === 1 ? t("Descargando “{titulo}”", { titulo: lista[0].titulo }) : t("{n} canciones en la cola", { n: lista.length }));
}

export async function descargarLink(url) {
  await pedirAvisosUnaVez();
  const r = await py("descargar", { url });
  for (const t of r.trabajos) descargas.trabajos[t.id] = t;
  aviso(t("{n} canciones de “{coleccion}” en la cola", { n: r.trabajos.length, coleccion: r.coleccion }));
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
