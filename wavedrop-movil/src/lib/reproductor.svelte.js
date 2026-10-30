// Motor de reproducción con fundido entre canciones (crossfade).
//
// Usa dos <audio>: al cambiar de canción, el nuevo sube de volumen mientras el viejo baja,
// con curva de potencia constante (seno/coseno) para que no haya "hueco" a mitad del fundido.
// Las canciones de YouTube Music que no tienes suenan mientras llegan (flujo del servidor local de Python);
// si se escuchan completas se quedan en la caché de previas.
import { py, src } from "./api.js";
import { aviso } from "./estado.svelte.js";
import { t } from "./idioma.svelte.js";

// ---------- Curva de volumen ----------
// El oído escucha en decibeles, no en amplitud: con la barra lineal de antes casi todo el cambio estaba en el
// primer 20 %. Aquí la barra es "qué tan fuerte se oye": cada +10 dB se percibe como el doble de fuerte
// (ley de Stevens / sonios), así que 50 % = −10 dB (la mitad de fuerte), 100 % = el archivo tal cual
// y 200 % = +10 dB (el doble de fuerte). Abajo de 2 % la curva baja en línea recta a 0 para que sí llegue a silencio.
export const VOLUMEN_MAX = 2;
const VOLUMEN_PISO = 0.02; // −56 dB

/** Amplitud (1 = original) que corresponde a una posición de la barra (0–2). */
export function gananciaDe(p) {
  if (p <= 0) return 0;
  const db = (x) => 10 ** ((10 * Math.log2(x)) / 20);
  return p < VOLUMEN_PISO ? db(VOLUMEN_PISO) * (p / VOLUMEN_PISO) : db(p);
}

function volumenGuardado() {
  let v = Number(localStorage.getItem("wavedrop_volumen") ?? 1);
  if (!isFinite(v)) v = 1;
  // Antes se guardaba la amplitud (barra lineal 0–1): se pasa una vez a la escala nueva para que suene igual
  if (localStorage.getItem("misiccord_volumen_escala") !== "2") {
    v = v > 0 ? Math.max(VOLUMEN_PISO, 2 ** ((20 * Math.log10(v)) / 10)) : 0;
    localStorage.setItem("misiccord_volumen_escala", "2");
    localStorage.setItem("wavedrop_volumen", String(v));
  }
  return Math.max(0, Math.min(VOLUMEN_MAX, v));
}

export const rep = $state({
  cola: [],
  indice: -1,
  actual: null,
  origen: "",
  sonando: false,
  cargando: false,
  pos: 0,
  dur: 0,
  aleatorio: false,
  repetir: 0, // 0 no, 1 toda la lista, 2 una canción
  volumen: volumenGuardado(), // posición de la barra: 0 a 2 (200 %); ver gananciaDe()
  silencio: false,
  fundido: 6, // segundos; se carga de los ajustes
  videoDisponible: false, // ajuste "ver video": si está apagado no hay interruptor ni se baja nada
  verVideo: localStorage.getItem("misiccord_ver_video") === "1", // el interruptor sobre la carátula
  videoDescargar: false, // ajuste "descargar también el video"
  eq: { activo: false, bandas: [0, 0, 0, 0, 0], mono: false }, // ecualizador (se carga de los ajustes)
  videoEstado: "", // "" | "cargando" | "listo" | "error"
  salto: 0, // sube cada vez que se adelanta o regresa (para avisar al reloj y a la notificación)
});

const audios = [new Audio(), new Audio()];
let actual = 0;
let fundido = null; // { intervalo }
let avanceProgramado = false;
let contada = false;

const el = () => audios[actual];

audios.forEach((a, i) => {
  a.preload = "auto";
  a.addEventListener("timeupdate", () => {
    if (i !== actual) return;
    rep.pos = a.currentTime;
    if (a.duration && isFinite(a.duration)) rep.dur = a.duration;
    revisarFin(a);
    contarReproduccion(a);
    sincronizarVideo(a);
  });
  a.addEventListener("ended", () => {
    if (i === actual && !avanceProgramado) siguienteAutomatico();
  });
  a.addEventListener("play", () => { if (i === actual) { rep.sonando = true; sincronizarVideo(a); } });
  a.addEventListener("pause", () => { if (i === actual) { rep.sonando = false; sincronizarVideo(a); } });
  a.addEventListener("seeked", () => { if (i === actual) { rep.salto++; sincronizarVideo(a); } });
  a.addEventListener("error", () => {
    if (i !== actual || !a.src) return;
    const c = rep.actual;
    // Si falló el flujo, respaldo: bajarla completa (como antes) y seguir donde iba
    if (c && !c.ruta && c.id && !c.respaldo) {
      c.respaldo = true;
      const donde = a.currentTime;
      rep.cargando = true;
      py("previa", { id: c.id, completa: true })
        .then(({ ruta }) => {
          if (rep.actual !== c) return;
          c.fuente_previa = src(ruta);
          a.src = c.fuente_previa;
          a.currentTime = donde;
          a.play().catch(() => {});
        })
        .catch(() => aviso(t("No se pudo reproducir esta canción"), "error"))
        .finally(() => (rep.cargando = false));
      return;
    }
    aviso(t("No se pudo reproducir esta canción"), "error");
  });
});

// ---------- Ecualizador ----------
// Web Audio: los dos <audio> pasan por un pre-amplificador, los filtros, el refuerzo de volumen y un limitador. El grafo se
// arma solo la primera vez que se prende el ecualizador, el mono, un visualizador o se sube de 100 %: si no, el audio sale
// directo como siempre (no se arriesga la música en segundo plano).
// Necesita CORS en lo que suena: el protocolo asset de Tauri y el flujo local (flujo.py) lo mandan.
export const NUM_BANDAS = [3, 5, 10, 15, 31];
const FRECUENCIAS = {
  3: [100, 1000, 10000],
  5: [60, 230, 910, 3600, 14000],
  10: [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000], // por octava
  15: [25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000, 16000], // 2/3 de octava
  31: [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150,
       4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000], // 1/3 de octava, como un ecualizador gráfico de estudio
};
// Entre más bandas, más angosta cada una (Q de 1, 2/3 y 1/3 de octava)
const Q_EQ = { 3: 0.5, 5: 1, 10: 1.41, 15: 2.15, 31: 4.32 };
export const frecuenciasEq = (n) => FRECUENCIAS[n] ?? FRECUENCIAS[5];

// Definidos en 5 bandas; convertirBandas los pasa a las que tengas
export const PRESETS_EQ = [
  ["Plano", [0, 0, 0, 0, 0]], ["Graves", [6, 3, 0, 0, 0]], ["Voces", [-2, 0, 3, 3, 1]], ["Agudos", [0, 0, 0, 3, 6]],
  ["Rock", [4, 2, -1, 2, 4]], ["Pop", [-1, 2, 4, 2, -1]], ["Electrónica", [5, 2, 0, 1, 4]],
];

/** La misma curva con otro número de bandas (interpolando en octavas, como las oye el oído). */
export function convertirBandas(bandas, n) {
  const de = frecuenciasEq(bandas.length);
  return frecuenciasEq(n).map((f) => {
    if (f <= de[0]) return bandas[0];
    if (f >= de.at(-1)) return bandas.at(-1);
    const k = de.findIndex((x) => x >= f);
    const x = Math.log2(f / de[k - 1]) / Math.log2(de[k] / de[k - 1]);
    return Math.round(bandas[k - 1] + (bandas[k] - bandas[k - 1]) * x);
  });
}

let eq = null; // { ctx, filtros, previo, refuerzo, limitador, suave, analizador }

function crearFiltros(ctx, n) {
  const frecuencias = frecuenciasEq(n);
  return frecuencias.map((frecuencia, i) => {
    const f = ctx.createBiquadFilter();
    f.type = i === 0 ? "lowshelf" : i === frecuencias.length - 1 ? "highshelf" : "peaking";
    f.frequency.value = frecuencia;
    f.Q.value = Q_EQ[n] ?? 1;
    return f;
  });
}

/** Cambia cuántas bandas hay sin cortar lo que suena: solo se reconecta el tramo de los filtros. */
function cambiarFiltros(n) {
  const { ctx, previo, refuerzo } = eq;
  previo.disconnect();
  eq.filtros.forEach((f) => f.disconnect());
  eq.filtros = crearFiltros(ctx, n);
  [previo, ...eq.filtros].reduce((a, b) => (a.connect(b), b)).connect(refuerzo);
}

function armarEq() {
  if (eq) return eq;
  const ctx = new AudioContext();
  const previo = ctx.createGain();
  // Arriba de 100 % el <audio> ya no puede subir (su volume llega a 1): el resto lo pone "refuerzo".
  // Para que el refuerzo no recorte (la distorsión dura de pasar de 0 dBFS) hay dos etapas, solo activas con refuerzo:
  // un limitador que aprieta lo que pase de −1.5 dB (con ratio 1 no toca nada) y, como se le escapan los golpes rápidos
  // (~+1.4 dB en pruebas), un recorte suave al final: lineal hasta 0.8 y de ahí una curva tanh que nunca pasa de −0.4 dB.
  // Sin sobremuestreo a propósito: el filtro del "2x"/"4x" rebota y vuelve a pasar de 0 dB.
  const refuerzo = ctx.createGain();
  const limitador = ctx.createDynamicsCompressor();
  limitador.threshold.value = -1.5;
  limitador.knee.value = 0;
  limitador.ratio.value = 1;
  limitador.attack.value = 0.001;
  limitador.release.value = 0.2;
  const suave = ctx.createWaveShaper();
  const filtros = crearFiltros(ctx, rep.eq.bandas.length || 5);
  [previo, ...filtros, refuerzo, limitador, suave].reduce((a, b) => (a.connect(b), b)).connect(ctx.destination);
  // Para los visualizadores: solo escucha, no cambia lo que suena
  const analizador = ctx.createAnalyser();
  analizador.fftSize = 2048;
  analizador.smoothingTimeConstant = 0.78;
  suave.connect(analizador);
  for (const a of audios) {
    // Sin crossOrigin el audio queda "ajeno" y Web Audio lo deja en silencio: lo que ya sonaba se recarga
    const sonaba = !a.paused;
    const donde = a.currentTime;
    const fuente = a.getAttribute("src");
    a.crossOrigin = "anonymous";
    if (fuente) {
      a.src = fuente;
      a.currentTime = donde;
      if (sonaba) a.play().catch(() => {});
    }
    ctx.createMediaElementSource(a).connect(previo);
  }
  eq = { ctx, filtros, previo, refuerzo, limitador, suave, analizador };
  aplicarRefuerzo();
  return eq;
}

/** El analizador del sonido para dibujar visualizadores (arma el grafo si hacía falta). */
export function analizadorDeAudio() {
  const { ctx, analizador } = armarEq();
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return analizador;
}

/** Lo que el <audio> no alcanza (volumen > 100 %) va en el nodo de refuerzo; el grafo se arma solo si hace falta. */
function aplicarRefuerzo() {
  const g = gananciaDe(rep.volumen);
  if (g <= 1 && !eq) return;
  const { ctx, refuerzo, limitador, suave } = armarEq();
  // setTargetAtTime: el cambio se suaviza en ~30 ms y no se oyen chasquidos al arrastrar la barra
  refuerzo.gain.setTargetAtTime(Math.max(1, g), ctx.currentTime, 0.03);
  limitador.ratio.setTargetAtTime(g > 1 ? 20 : 1, ctx.currentTime, 0.03);
  suave.curve = g > 1 ? (curvaSuave ??= hacerCurvaSuave()) : null; // null = pasa tal cual
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
}

let curvaSuave = null;
function hacerCurvaSuave() {
  const n = 2049, c = new Float32Array(n), k = 0.8;
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * 2 - 1, a = Math.abs(x);
    c[i] = Math.sign(x) * (a <= k ? a : k + (1 - k) * Math.tanh((a - k) / (1 - k)));
  }
  return c;
}

/** Volumen del <audio> (0–1): la parte de la ganancia que el elemento sí puede dar. */
const base = () => Math.min(1, gananciaDe(rep.volumen));

/** Ajustes del ecualizador: prendido/apagado, los dB de cada banda (−12 a +12) y mono. */
export function aplicarEcualizador(activo, bandas, mono = rep.eq.mono) {
  const lista = (bandas?.length ? bandas : [0, 0, 0, 0, 0]).map((x) => Number(x) || 0);
  rep.eq = { activo: !!activo, bandas: lista, mono: !!mono };
  if (!activo && !mono && !eq) return;
  const { ctx, previo } = armarEq();
  if (eq.filtros.length !== lista.length) cambiarFiltros(lista.length);
  eq.filtros.forEach((f, i) => f.gain.setTargetAtTime(activo ? lista[i] : 0, ctx.currentTime, 0.05));
  // Si subes bandas, se baja un poco todo para que no sature
  const maximo = activo ? Math.max(0, ...lista) : 0;
  previo.gain.setTargetAtTime(Math.pow(10, -maximo / 2 / 20), ctx.currentTime, 0.05);
  // Mono: desde aquí todo va en un canal (izquierda + derecha) y al final sale igual por los dos lados
  previo.channelCount = mono ? 1 : 2;
  previo.channelCountMode = mono ? "explicit" : "max";
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
}

// ---------- Video ----------
// El sonido siempre es el de los <audio>; el video va mudo y sigue al audio (su posición y si está en pausa).
// Si la canción tiene su video descargado se usa ese archivo; si no, se transmite el clip de YouTube.
const video = document.createElement("video");
video.muted = true;
video.playsInline = true;
video.preload = "auto";
video.disablePictureInPicture = true;
let pedidoVideo = 0;

/** Pone el <video> dentro de un contenedor del reproductor grande (use:montarVideo). */
export function montarVideo(nodo) {
  nodo.prepend(video);
  return { destroy: () => video.remove() };
}

function sincronizarVideo(a) {
  if (!video.getAttribute("src") || rep.videoEstado === "error") return;
  if (a.paused) {
    if (!video.paused) video.pause();
  } else if (video.paused && video.readyState >= 2) {
    video.play().catch(() => {});
  }
  if (video.readyState >= 1 && Math.abs(video.currentTime - a.currentTime) > 0.5) video.currentTime = a.currentTime;
}

video.addEventListener("loadedmetadata", () => { video.currentTime = el().currentTime; });
video.addEventListener("canplay", () => {
  if (!video.getAttribute("src")) return;
  rep.videoEstado = "listo";
  sincronizarVideo(el());
});
video.addEventListener("error", () => {
  if (video.getAttribute("src")) rep.videoEstado = "error";
});

/** Carga (o suelta) el video de la canción según el ajuste y el interruptor. */
async function prepararVideo(c) {
  const yo = ++pedidoVideo;
  video.pause();
  video.removeAttribute("src");
  video.load();
  rep.videoEstado = "";
  if (!c || !rep.videoDisponible || !rep.verVideo) return;
  rep.videoEstado = "cargando";
  try {
    const r = await py("video", { ruta: c.ruta, id: c.id, titulo: c.titulo, artista: c.artista, duracion: c.duracion });
    if (yo !== pedidoVideo) return;
    video.src = r.ruta ? src(r.ruta) : r.url;
  } catch {
    if (yo === pedidoVideo) rep.videoEstado = "error";
  }
}

export function alternarVideo() {
  rep.verVideo = !rep.verVideo;
  localStorage.setItem("misiccord_ver_video", rep.verVideo ? "1" : "0");
  prepararVideo(rep.actual);
}

/** Los ajustes de video cambiaron: aparece o desaparece el interruptor y se suelta lo que estaba cargado. */
export function aplicarAjustesVideo(aj) {
  rep.videoDescargar = !!aj.video_descargar;
  if (rep.videoDisponible === !!aj.video_ver) return;
  rep.videoDisponible = !!aj.video_ver;
  prepararVideo(rep.actual);
}

/** Dirección reproducible: el archivo descargado o, si es de YouTube Music, la caché o el flujo en vivo. */
async function fuenteDe(c) {
  if (c.ruta) return src(c.ruta);
  if (c.fuente_previa) return c.fuente_previa;
  const r = await py("previa", { id: c.id });
  c.fuente_previa = r.ruta ? src(r.ruta) : r.url;
  return c.fuente_previa;
}

function cancelarFundido() {
  if (fundido) {
    clearInterval(fundido.intervalo);
    for (const a of audios) if (a !== el()) a.pause();
    el().volume = base();
    fundido = null;
  }
}

/** Cambia al audio nuevo; si el viejo está sonando, los cruza durante `segundos`. */
function cruzarA(url, segundos) {
  cancelarFundido();
  const viejo = el();
  const nuevo = audios[1 - actual];
  nuevo.src = url;
  nuevo.currentTime = 0;
  actual = 1 - actual;
  rep.pos = 0;
  rep.dur = 0;
  if (viejo.paused || segundos <= 0) {
    viejo.pause();
    nuevo.volume = base();
    nuevo.play().catch(() => {});
    return;
  }
  nuevo.volume = 0;
  nuevo.play().catch(() => {});
  const inicio = performance.now();
  const total = segundos * 1000;
  const v0 = viejo.volume;
  // setInterval y no requestAnimationFrame: sigue funcionando con la pantalla apagada
  fundido = {
    intervalo: setInterval(() => {
      const x = Math.min(1, (performance.now() - inicio) / total);
      nuevo.volume = base() * Math.sin((x * Math.PI) / 2);
      viejo.volume = v0 * Math.cos((x * Math.PI) / 2);
      if (x >= 1) {
        clearInterval(fundido.intervalo);
        viejo.pause();
        viejo.volume = base();
        fundido = null;
      }
    }, 40),
  };
}

async function cargar(i, manual) {
  if (i < 0 || i >= rep.cola.length) return;
  const c = rep.cola[i];
  rep.indice = i;
  rep.actual = c;
  rep.cargando = true;
  avanceProgramado = false;
  contada = false;
  let fuente;
  try {
    fuente = await fuenteDe(c);
  } catch (e) {
    rep.cargando = false;
    aviso(t("No se pudo cargar “{titulo}”", { titulo: c.titulo }), "error");
    return;
  }
  if (rep.indice !== i) return; // mientras cargaba se eligió otra
  rep.cargando = false;
  // El navegador deja arrancar Web Audio solo después de que tocas algo: aquí ya hubo un toque
  if (eq?.ctx.state === "suspended") eq.ctx.resume().catch(() => {});
  // Fundido completo cuando termina sola; uno cortito si la cambias tú
  cruzarA(fuente, manual ? Math.min(0.6, rep.fundido) : rep.fundido);
  prepararVideo(c);
  precargarSiguiente();
}

// La cola siempre es el orden real en que van a sonar: con aleatorio se baraja de verdad (así "A continuación" dice
// cuál sigue) y al apagarlo regresa al orden de antes. Prenderlo otra vez baraja distinto.
let original = null; // la cola tal como estaba antes de barajar

function barajar(lista) {
  const r = [...lista];
  for (let i = r.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [r[i], r[j]] = [r[j], r[i]];
  }
  return r;
}

/** La que suena se queda primero y todas las demás se barajan después de ella. */
function mezclar() {
  const c = rep.cola[rep.indice];
  original = [...rep.cola];
  rep.cola = c ? [c, ...barajar(rep.cola.filter((_, i) => i !== rep.indice))] : barajar(rep.cola);
  if (c) rep.indice = 0;
}

function desmezclar() {
  const c = rep.cola[rep.indice];
  const hay = new Set(rep.cola);
  const base = (original ?? []).filter((x) => hay.has(x));
  const enBase = new Set(base);
  const nuevas = rep.cola.filter((x) => !enBase.has(x) && x !== c); // las que entraron mientras estaba mezclada
  let i = base.indexOf(c);
  if (i < 0 && c) {
    base.unshift(c);
    i = 0;
  }
  base.splice(i + 1, 0, ...nuevas);
  rep.cola = base;
  rep.indice = i;
  original = null;
}

function indiceSiguiente() {
  const n = rep.cola.length;
  if (!n) return -1;
  if (rep.indice + 1 < n) return rep.indice + 1;
  return rep.repetir === 1 ? 0 : -1;
}

/** Deja lista la vista previa de la siguiente canción para que el fundido no tenga que esperar. */
function precargarSiguiente() {
  const j = indiceSiguiente();
  if (j >= 0 && !rep.cola[j].ruta && !rep.cola[j].fuente_previa) fuenteDe(rep.cola[j]).catch(() => {});
}

function revisarFin(a) {
  if (avanceProgramado || rep.fundido <= 0 || rep.repetir === 2 || !a.duration || !isFinite(a.duration)) return;
  if (a.duration - a.currentTime <= rep.fundido && indiceSiguiente() >= 0) {
    avanceProgramado = true;
    cargar(indiceSiguiente(), false);
  }
}

function siguienteAutomatico() {
  if (rep.repetir === 2) {
    el().currentTime = 0;
    el().play();
    return;
  }
  const j = indiceSiguiente();
  if (j >= 0) cargar(j, false);
}

function contarReproduccion(a) {
  // Cuenta para el historial (y las recomendaciones) a los 30 s o a la mitad si es corta
  // Las vistas previas también cuentan (para las estadísticas); se mandan con su id de YouTube Music
  const c = rep.actual;
  if (contada || !(c?.ruta || c?.id) || !a.duration || !isFinite(a.duration)) return;
  if (a.currentTime >= Math.min(30, a.duration / 2)) {
    contada = true;
    const datos = c.ruta
      ? { ruta: c.ruta, duracion: a.duration }
      : { id: c.id, titulo: c.titulo, artista: c.artista, duracion: a.duration, portada: c.portada };
    py("reproduccion", datos).catch(() => {});
  }
}

// ---------- Controles ----------

// Si estás en un jam, tocar una canción no debe sonar encima del jam: jam.svelte.js registra aquí quién pregunta
// "¿la mandas al jam o sales y la escuchas aquí?" (así este módulo no importa al del jam, que ya importa a este).
let alTocarEnJam = null; // (cancion, reproducirAqui) => true si se encargó él

export function preguntarAlReproducirEnJam(f) {
  alTocarEnJam = f;
}

export function reproducir(lista, i = 0, origen = "", { aunEnJam = false } = {}) {
  if (!aunEnJam && lista[i] && alTocarEnJam?.(lista[i], () => reproducir(lista, i, origen, { aunEnJam: true }))) return;
  rep.cola = lista.map((c) => ({ ...c }));
  rep.origen = origen;
  rep.indice = i;
  original = null;
  if (rep.aleatorio) {
    mezclar();
    i = 0;
  }
  cargar(i, true);
}

/** Agrega a la cola: al final, o justo después de la que suena. Si no suena nada, empieza a sonar. */
export function agregarACola(c, aContinuacion = false) {
  if (!rep.actual) return reproducir([c], 0, t("Tu cola"));
  const copia = { ...c };
  if (aContinuacion) rep.cola.splice(rep.indice + 1, 0, copia);
  else rep.cola.push(copia);
  original?.push(rep.cola[aContinuacion ? rep.indice + 1 : rep.cola.length - 1]);
  precargarSiguiente();
}

/** Cambiar el orden de lo que falta por sonar (arrastrando en "A continuación"). */
export function moverEnCola(de, a) {
  rep.cola.splice(a, 0, rep.cola.splice(de, 1)[0]);
  precargarSiguiente();
}

/** Quitar una canción de la cola (no la que suena). */
export function quitarDeCola(i) {
  if (i === rep.indice) return;
  const [c] = rep.cola.splice(i, 1);
  if (i < rep.indice) rep.indice--;
  if (original) original = original.filter((x) => x !== c);
  precargarSiguiente();
}

export function reproducirAleatorio(lista, origen = "") {
  const i = Math.floor(Math.random() * lista.length);
  if (lista[i] && alTocarEnJam?.(lista[i], () => { rep.aleatorio = true; reproducir(lista, i, origen, { aunEnJam: true }); })) return;
  rep.aleatorio = true;
  reproducir(lista, i, origen, { aunEnJam: true });
}

export function alternar() {
  if (!rep.actual) return;
  if (el().paused) el().play().catch(() => {});
  else el().pause();
}

export function siguiente() {
  const j = indiceSiguiente();
  if (j >= 0) cargar(j, true);
}

export function anterior() {
  if (rep.pos > 3 || rep.indice <= 0) el().currentTime = 0;
  else cargar(rep.indice - 1, true);
}

export function irA(segundos) {
  el().currentTime = Math.max(0, Math.min(segundos, rep.dur || segundos));
  // Al instante: si se espera al siguiente timeupdate la barra regresa un momento a donde iba y "parpadea"
  rep.pos = el().currentTime;
  avanceProgramado = false;
}

export function ponerVolumen(v) {
  v = Math.max(0, Math.min(VOLUMEN_MAX, v));
  if (Math.abs(v - 1) < 0.03) v = 1; // se "pega" en 100 % (el archivo tal cual) para que sea fácil regresar
  rep.volumen = v;
  rep.silencio = false;
  localStorage.setItem("wavedrop_volumen", String(rep.volumen));
  for (const a of audios) a.muted = false;
  if (!fundido) el().volume = base();
  aplicarRefuerzo();
}

export function alternarSilencio() {
  rep.silencio = !rep.silencio;
  for (const a of audios) a.muted = rep.silencio;
}

// El volumen guardado se aplica desde el arranque (arriba de 100 % el refuerzo se arma al primer play:
// el navegador no deja empezar un AudioContext sin que el usuario toque algo)
for (const a of audios) a.volume = base();
audios.forEach((a) => a.addEventListener("play", () => gananciaDe(rep.volumen) > 1 && aplicarRefuerzo()));

export function alternarAleatorio() {
  rep.aleatorio = !rep.aleatorio;
  if (!rep.cola.length) return;
  if (rep.aleatorio) mezclar();
  else desmezclar();
  precargarSiguiente();
}

export function ciclarRepetir() {
  rep.repetir = (rep.repetir + 1) % 3;
}

export function reproducirDeCola(i) {
  cargar(i, true);
}

/** Antes de borrar: suelta el archivo si es lo que suena (Windows no deja borrar un archivo abierto). */
export function soltarSi(seBorra) {
  if (!rep.actual?.ruta || !seBorra(rep.actual)) return;
  cancelarFundido();
  for (const a of audios) { a.pause(); a.removeAttribute("src"); a.load(); }
  prepararVideo(null); // el video descargado también está abierto y se borra con la canción
}

/** Canciones borradas del dispositivo: salen de la cola (las de YouTube Music vuelven a ser vista previa). */
export function olvidarRutas(rutas) {
  const borradas = new Set(rutas);
  if (!rep.cola.some((c) => borradas.has(c.ruta))) return;
  const antes = rep.indice;
  const sonabaBorrada = borradas.has(rep.cola[antes]?.ruta);
  let quitadasAntes = 0;
  let seFueLaActual = false;
  const quedan = [];
  rep.cola.forEach((c, k) => {
    if (!borradas.has(c.ruta)) return quedan.push(c);
    if (c.id) return quedan.push({ ...c, ruta: null, local: false }); // se puede seguir oyendo en línea
    if (k < antes) quitadasAntes++;
    if (k === antes) seFueLaActual = true;
  });
  rep.cola = quedan;
  if (original) original = original.filter((c) => quedan.includes(c));
  const j = antes - quitadasAntes;
  if (!seFueLaActual) {
    rep.indice = j;
    rep.actual = quedan[j] ?? null;
    if (rep.actual && sonabaBorrada) cargar(j, true); // la descargada se borró: sigue en línea
  } else if (j < quedan.length) {
    cargar(j, true); // la que sonaba ya no existe: entra la que seguía
  } else {
    rep.actual = null;
    rep.indice = -1;
    rep.sonando = false;
    rep.pos = rep.dur = 0;
    prepararVideo(null);
  }
}

/** Se editaron las etiquetas o la carátula de una canción: lo que está en la cola se ve con los datos nuevos. */
export function actualizarCancion(nueva) {
  for (const c of rep.cola) {
    if (c.ruta !== nueva.ruta) continue;
    Object.assign(c, { titulo: nueva.titulo, artista: nueva.artista, album: nueva.album,
                       artista_album: nueva.artista_album, anio: nueva.anio, portada: nueva.portada });
  }
}

/** Cuando una vista previa se descarga, la canción pasa a ser local (sin cortar lo que suena). */
export function marcarDescargada(titulo, artista, ruta) {
  for (const c of rep.cola) if (c.titulo === titulo && c.artista === artista) c.ruta = ruta;
}
