// Controles del sistema: notificación de música, pantalla bloqueada, relojes y audífonos.
//
// - Android: se le pasa el estado al ServicioMedios (MediaSession nativa). Los relojes con Wear OS y
//   Galaxy Watch muestran esos controles solos; sus botones regresan como evento "medios".
// - Windows: Media Session API de WebView2 (el panel de música de Windows y las teclas multimedia).
//
// En un jam los controles manejan el jam: el anfitrión pausa y cambia; un invitado vota para saltar.
import { invoke } from "@tauri-apps/api/core";
import { untrack } from "svelte";
import { alEvento } from "./api.js";
import { control, jam, pistaActual, posicionJam, soyAnfitrion, urlJam, votar } from "./jam.svelte.js";
import { alternar, anterior, irA, rep, siguiente } from "./reproductor.svelte.js";

const esAndroid = /Android/i.test(navigator.userAgent);
const web = "mediaSession" in navigator ? navigator.mediaSession : null;

/** Qué suena ahora (del jam si estás en uno, si no del reproductor). */
function ahora() {
  if (jam.sala) {
    const p = pistaActual();
    if (!p) return { hay: false };
    return {
      hay: true, enJam: true, titulo: p.titulo, artista: p.artista, album: jam.sala.nombre,
      portada: urlJam(p.portada), duracion: p.duracion || 0, posicion: posicionJam(), sonando: jam.sala.sonando,
    };
  }
  const c = rep.actual;
  if (!c) return { hay: false };
  return {
    hay: true, enJam: false, titulo: c.titulo, artista: c.artista, album: c.album || "",
    portada: c.portada || null, duracion: rep.dur || c.duracion || 0,
    // Mientras carga la siguiente, en pausa y en 0 (si no, el reloj sigue contando la anterior)
    posicion: rep.cargando ? 0 : rep.pos, sonando: rep.sonando && !rep.cargando,
  };
}

let ultimoEnviado = "";
function enviar() {
  const e = ahora();
  // La posición no cuenta para decidir si cambió: el sistema la calcula solo mientras suena
  const clave = JSON.stringify({ ...e, posicion: Math.round(e.posicion / 10) });
  if (clave === ultimoEnviado) return;
  ultimoEnviado = clave;
  if (esAndroid) invoke("medios", { estado: e }).catch(() => {});
  if (web) actualizarWeb(e);
}

function actualizarWeb(e) {
  if (!e.hay) {
    web.metadata = null;
    web.playbackState = "none";
    return;
  }
  const portada = e.portada && /^https?:/.test(e.portada) ? e.portada : null;
  web.metadata = new MediaMetadata({
    title: e.titulo, artist: e.artista, album: e.enJam ? `Jam · ${e.album}` : e.album,
    artwork: portada ? [{ src: portada, sizes: "512x512" }] : [],
  });
  web.playbackState = e.sonando ? "playing" : "paused";
  try {
    if (e.duracion) web.setPositionState({ duration: e.duracion, position: Math.min(e.posicion, e.duracion), playbackRate: 1 });
  } catch {}
}

/** Un botón del reloj, la notificación o los audífonos. */
function accion(nombre, posicion) {
  if (jam.sala) {
    if (!soyAnfitrion()) {
      if (nombre === "siguiente") votar().catch(() => {});
      return; // el invitado no pausa el jam de todos
    }
    if (nombre === "play") control("play");
    else if (nombre === "pausa") control("pausa");
    else if (nombre === "siguiente") control("siguiente");
    else if (nombre === "anterior") control("anterior");
    return;
  }
  if (nombre === "play" && !rep.sonando) alternar();
  else if (nombre === "pausa" && rep.sonando) alternar();
  else if (nombre === "siguiente") siguiente();
  else if (nombre === "anterior") anterior();
  else if (nombre === "ir" && posicion != null) irA(posicion);
}

alEvento("medios", (d) => accion(d.accion, d.posicion));
if (web) {
  for (const [evento, nombre] of [["play", "play"], ["pause", "pausa"], ["nexttrack", "siguiente"], ["previoustrack", "anterior"]]) {
    try { web.setActionHandler(evento, () => accion(nombre)); } catch {}
  }
  try { web.setActionHandler("seekto", (d) => accion("ir", d.seekTime)); } catch {}
}

$effect.root(() => {
  $effect(() => {
    // Lo que importa: canción, play/pausa, duración, saltos y el estado del jam (la posición se lee sin seguirla)
    rep.actual; rep.sonando; rep.cargando; rep.dur; rep.salto;
    jam.sala?.version; jam.sala?.indice; jam.sala?.sonando;
    untrack(enviar);
  });
});
// Cada 15 s se corrige el avance por si se desfasó (y para jams, donde el reloj lo lleva el anfitrión)
setInterval(enviar, 15000);
