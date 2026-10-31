// Escritorio: lo que suena, fuera de la ventana principal.
// - La burbuja flotante (componentes/Burbuja.svelte, otra ventana que Rust muestra al minimizar; ajuste `burbuja`).
// - Windows: la vista previa de la barra de tareas (título con la canción y botones anterior/reproducir/siguiente, src-tauri/src/barra.rs).
// Las dos solo muestran y mandan órdenes: la música sigue en esta ventana.
import { invoke } from "@tauri-apps/api/core";
import { emitTo, listen } from "@tauri-apps/api/event";
import { src } from "./api.js";
import { t } from "./idioma.svelte.js";
import { alternar, alternarSilencio, anterior, ponerVolumen, rep, siguiente } from "./reproductor.svelte.js";

const esEscritorio = !/Android/i.test(navigator.userAgent);
let iniciado = false;
let burbujaActiva = false;

function estado() {
  const c = rep.actual;
  return {
    hay: !!c, titulo: c?.titulo ?? "", artista: c?.artista ?? "", portada: c?.portada ? src(c.portada) : null,
    sonando: rep.sonando, pos: rep.pos, dur: rep.dur || c?.duracion || 0, volumen: rep.volumen, silencio: rep.silencio,
  };
}

const mandarBurbuja = () => burbujaActiva && emitTo("burbuja", "burbuja-estado", estado()).catch(() => {});

function obedecer({ payload }) {
  if (payload.accion === "alternar") alternar();
  else if (payload.accion === "siguiente") siguiente();
  else if (payload.accion === "anterior") anterior();
  else if (payload.accion === "volumen") ponerVolumen(payload.valor);
  else if (payload.accion === "silencio") alternarSilencio();
  mandarBurbuja(); // "listo": la burbuja acaba de abrirse y no sabe qué suena
}

function iniciar() {
  if (iniciado || !esEscritorio) return;
  iniciado = true;
  listen("burbuja-control", obedecer);
  listen("barra-control", obedecer);
  $effect.root(() => {
    // La barra de tareas solo cambia con la canción o la pausa (no con cada segundo)
    $effect(() => {
      const c = rep.actual;
      invoke("barra_tareas", {
        titulo: c?.titulo ?? "", artista: c?.artista ?? "", hay: !!c, sonando: rep.sonando,
        textos: [t("Anterior"), t("Reproducir"), t("Pausar"), t("Siguiente")],
      }).catch(() => {});
    });
    $effect(() => {
      rep.actual;
      rep.sonando;
      rep.dur;
      rep.volumen;
      rep.silencio;
      mandarBurbuja();
    });
  });
  // El avance de la burbuja, cada segundo mientras suena
  setInterval(() => rep.sonando && mandarBurbuja(), 1000);
}

/** Arranque y Ajustes: prende o apaga la burbuja (y engancha la barra de tareas la primera vez). En el cel no hace nada. */
export function aplicarAjusteBurbuja(activa) {
  if (!esEscritorio) return;
  iniciar();
  burbujaActiva = !!activa;
  invoke("burbuja", { accion: "activar", activa: burbujaActiva }).catch(() => {});
}
