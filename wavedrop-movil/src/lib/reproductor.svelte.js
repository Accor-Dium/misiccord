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
  eq: { activo: false, bandas: [0, 0, 0, 0, 0] }, // ecualizador (se carga de los ajustes)
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
// Web Audio: los dos <audio> pasan por un pre-amplificador, 5 filtros, el refuerzo de volumen y un limitador. El grafo se
// arma solo la primera vez que se prende el ecualizador o se sube de 100 %: si no, el audio sale directo como siempre
// (no se arriesga la música en segundo plano).
// Necesita CORS en lo que suena: el protocolo asset de Tauri y el flujo local (flujo.py) lo mandan.
export const BANDAS_EQ = [60, 230, 910, 3600, 14000];
let eq = null; // { ctx, filtros, previo, refuerzo, limitador, suave }

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
  const filtros = BANDAS_EQ.map((frecuencia, i) => {
    const f = ctx.createBiquadFilter();
    f.type = i === 0 ? "lowshelf" : i === BANDAS_EQ.length - 1 ? "highshelf" : "peaking";
    f.frequency.value = frecuencia;
    f.Q.value = 1;
    return f;
  });
  [previo, ...filtros, refuerzo, limitador, suave].reduce((a, b) => (a.connect(b), b)).connect(ctx.destination);
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
  eq = { ctx, filtros, previo, refuerzo, limitador, suave };
  aplicarRefuerzo();
  return eq;
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

/** Ajustes del ecualizador: prendido/apagado y los dB de cada banda (−12 a +12). */
export function aplicarEcualizador(activo, bandas) {
  rep.eq = { activo: !!activo, bandas: [...(bandas ?? [])] };
  if (!activo && !eq) return;
  const { ctx, filtros, previo } = armarEq();
  filtros.forEach((f, i) => f.gain.setTargetAtTime(activo ? Number(bandas[i]) || 0 : 0, ctx.currentTime, 0.05));
  // Si subes bandas, se baja un poco todo para que no sature
  const maximo = activo ? Math.max(0, ...bandas.map(Number)) : 0;
  previo.gain.setTargetAtTime(Math.pow(10, -maximo / 2 / 20), ctx.currentTime, 0.05);
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

function indiceSiguiente() {
  const n = rep.cola.length;
  if (!n) return -1;
  if (rep.aleatorio && n > 1) {
    let j;
    do j = Math.floor(Math.random() * n);
    while (j === rep.indice);
    return j;
  }
  if (rep.indice + 1 < n) return rep.indice + 1;
  return rep.repetir === 1 ? 0 : -1;
}

/** Deja lista la vista previa de la siguiente canción para que el fundido no tenga que esperar. */
let siguientePrecargado = -1;
function precargarSiguiente() {
  const j = rep.aleatorio ? -1 : indiceSiguiente();
  siguientePrecargado = j;
  if (j >= 0 && !rep.cola[j].ruta && !rep.cola[j].fuente_previa) fuenteDe(rep.cola[j]).catch(() => {});
}

function revisarFin(a) {
  if (avanceProgramado || rep.fundido <= 0 || rep.repetir === 2 || !a.duration || !isFinite(a.duration)) return;
  if (a.duration - a.currentTime <= rep.fundido && indiceSiguiente() >= 0) {
    avanceProgramado = true;
    const j = rep.aleatorio ? indiceSiguiente() : siguientePrecargado >= 0 ? siguientePrecargado : indiceSiguiente();
    cargar(j, false);
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
  cargar(i, true);
}

/** Agrega a la cola: al final, o justo después de la que suena. Si no suena nada, empieza a sonar. */
export function agregarACola(c, aContinuacion = false) {
  if (!rep.actual) return reproducir([c], 0, t("Tu cola"));
  const copia = { ...c };
  if (aContinuacion) rep.cola.splice(rep.indice + 1, 0, copia);
  else rep.cola.push(copia);
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
