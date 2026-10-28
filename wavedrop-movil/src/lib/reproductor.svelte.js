// Motor de reproducción con fundido entre canciones (crossfade).
//
// Usa dos <audio>: al cambiar de canción, el nuevo sube de volumen mientras el viejo baja,
// con curva de potencia constante (seno/coseno) para que no haya "hueco" a mitad del fundido.
// Las canciones de YouTube Music que no tienes se escuchan como vista previa (se bajan a caché).
import { py, src } from "./api.js";
import { aviso } from "./estado.svelte.js";

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
  volumen: 1,
  fundido: 6, // segundos; se carga de los ajustes
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
  });
  a.addEventListener("ended", () => {
    if (i === actual && !avanceProgramado) siguienteAutomatico();
  });
  a.addEventListener("play", () => i === actual && (rep.sonando = true));
  a.addEventListener("pause", () => i === actual && (rep.sonando = false));
  a.addEventListener("error", () => {
    if (i === actual && a.src) aviso("No se pudo reproducir esta canción", "error");
  });
});

/** Ruta reproducible: la canción descargada o, si es de YouTube Music, su vista previa en caché. */
async function rutaDe(c) {
  if (c.ruta) return c.ruta;
  if (c.ruta_previa) return c.ruta_previa;
  c.ruta_previa = (await py("previa", { id: c.id })).ruta;
  return c.ruta_previa;
}

function cancelarFundido() {
  if (fundido) {
    clearInterval(fundido.intervalo);
    for (const a of audios) if (a !== el()) a.pause();
    el().volume = rep.volumen;
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
    nuevo.volume = rep.volumen;
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
      nuevo.volume = rep.volumen * Math.sin((x * Math.PI) / 2);
      viejo.volume = v0 * Math.cos((x * Math.PI) / 2);
      if (x >= 1) {
        clearInterval(fundido.intervalo);
        viejo.pause();
        viejo.volume = rep.volumen;
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
  let ruta;
  try {
    ruta = await rutaDe(c);
  } catch (e) {
    rep.cargando = false;
    aviso(`No se pudo cargar “${c.titulo}”`, "error");
    return;
  }
  if (rep.indice !== i) return; // mientras cargaba se eligió otra
  rep.cargando = false;
  // Fundido completo cuando termina sola; uno cortito si la cambias tú
  cruzarA(src(ruta), manual ? Math.min(0.6, rep.fundido) : rep.fundido);
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
  if (j >= 0 && !rep.cola[j].ruta && !rep.cola[j].ruta_previa) rutaDe(rep.cola[j]).catch(() => {});
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
  if (contada || !rep.actual?.ruta || !a.duration) return;
  if (a.currentTime >= Math.min(30, a.duration / 2)) {
    contada = true;
    py("reproduccion", { ruta: rep.actual.ruta }).catch(() => {});
  }
}

// ---------- Controles ----------

export function reproducir(lista, i = 0, origen = "") {
  rep.cola = lista.map((c) => ({ ...c }));
  rep.origen = origen;
  cargar(i, true);
}

export function reproducirAleatorio(lista, origen = "") {
  rep.aleatorio = true;
  reproducir(lista, Math.floor(Math.random() * lista.length), origen);
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
  rep.volumen = v;
  if (!fundido) el().volume = v;
}

export function alternarAleatorio() {
  rep.aleatorio = !rep.aleatorio;
}

export function ciclarRepetir() {
  rep.repetir = (rep.repetir + 1) % 3;
}

export function reproducirDeCola(i) {
  cargar(i, true);
}

/** Cuando una vista previa se descarga, la canción pasa a ser local (sin cortar lo que suena). */
export function marcarDescargada(titulo, artista, ruta) {
  for (const c of rep.cola) if (c.titulo === titulo && c.artista === artista) c.ruta = ruta;
}
