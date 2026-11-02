// Filtros de Biblioteca: décadas y categorías que juntan los muchos géneros de las etiquetas, sin cambiar los archivos.
// Se deducen aquí (es instantáneo y no usa internet) del género, el nombre del álbum y la carpeta. Tú mandas: puedes crear
// categorías, sumarles géneros y mover canciones o álbumes (`cfg`, de biblioteca.categorias_config); eso reemplaza a lo deducido.
import { normalizar } from "./ordenar.js";

export const CATEGORIAS = [["jazz", "Jazz"], ["pop", "Pop"], ["rock", "Rock"], ["soundtrack", "Soundtrack"], ["videojuegos", "Videojuegos"], ["anime", "Anime"]];

/** Las que trae la app con lo que le hayas cambiado, y luego las tuyas. `cfg` es biblioteca.categorias_config(). */
export function todasLasCategorias(cfg) {
  const propias = cfg?.propias ?? [];
  const base = CATEGORIAS.map(([id, nombre]) => ({ id, nombre, generos: [], oculta: false, ...propias.find((p) => p.id === id), deLaApp: true }));
  return [...base, ...propias.filter((p) => !esDecada(p.id) && !base.some((b) => b.id === p.id))];
}

export const listaCategorias = (cfg) => todasLasCategorias(cfg).filter((c) => !c.oculta);

// Las décadas son categorías como las demás (id "d1980"): salen del año, pero se pueden renombrar, llenar y vaciar
export const esDecada = (id) => /^d\d{4}$/.test(id);
const SIN_DECADA = "sin-decada"; // la sacaste de su década: sin esto el año la volvería a meter

/** Una categoría o década con lo que le hayas cambiado. */
export function datosCategoria(id, cfg) {
  if (!esDecada(id)) return todasLasCategorias(cfg).find((c) => c.id === id);
  return { id, nombre: nombreDecada(Number(id.slice(1))), generos: [], oculta: false, ...cfg?.propias?.find((p) => p.id === id), deLaApp: true };
}

/** Lo que Biblioteca enseña: décadas que tengas y categorías, cada una con cuántas canciones trae. */
export function conteoCategorias(canciones, cfg) {
  const cuantas = new Map();
  for (const c of canciones) for (const id of categoriasDe(c, cfg)) cuantas.set(id, (cuantas.get(id) ?? 0) + 1);
  const decadas = [...cuantas.keys()].filter(esDecada).sort().map((id) => datosCategoria(id, cfg)).filter((c) => !c.oculta);
  return {
    decadas: decadas.map((c) => ({ ...c, n: cuantas.get(c.id) })),
    categorias: listaCategorias(cfg).map((c) => ({ ...c, n: cuantas.get(c.id) ?? 0 })),
  };
}

export const categoriasOcultas = (cfg) => [...todasLasCategorias(cfg), ...(cfg?.propias ?? []).filter((p) => esDecada(p.id))].filter((c) => c.oculta);

/** Las categorías que le quedan a una canción después de moverla. */
export function cambiarCategorias(c, cfg, { poner, quitar }) {
  const r = new Set(categoriasDe(c, cfg));
  if (quitar) r.delete(quitar);
  if (poner) r.add(poner);
  if (quitar && esDecada(quitar) && ![...r].some(esDecada)) r.add(SIN_DECADA);
  return [...r];
}

const POR_GENERO = {
  jazz: /\bjazz|bebop|bossa|\bswing\b|big band/,
  pop: /\bpop\b|[a-z]-?pop\b/,
  rock: /\brock\b|metal|punk|grunge|alternativ/,
  soundtrack: /soundtrack|\bost\b|\bscore\b|banda sonora|\bfilm\b|\bcine\b|pelicula/,
  videojuegos: /video ?game|videojuego|game music|chiptune|\bvgm\b/,
  anime: /\banime\b/,
};
const POR_ALBUM = {
  soundtrack: /soundtrack|\bo\.?s\.?t\.?\b|banda sonora|motion picture|film score|original score/,
  videojuegos: /videojuego|video ?game|\bgame\b.*(soundtrack|\bost\b|music)|(soundtrack|\bost\b).*\bgame\b/,
  anime: /\banime\b|the animation/,
};
const POR_CARPETA = {
  soundtrack: /soundtrack|banda sonora|bandas sonoras|\bost\b/,
  videojuegos: /videojuego|video ?game|\bvgm\b|game ?(ost|soundtrack|music)/,
  anime: /\banime\b/,
};
const CARPETAS_A_REVISAR = 3; // solo las más cercanas al archivo: "C:\Users\Anime Fan\Music" no hace anime todo lo que tengas

const deducidas = new WeakMap(); // ordenar y filtrar piden esto muchas veces: las reglas se corren una sola vez por canción

function deducir(c) {
  const genero = normalizar(c.genero);
  const album = normalizar(c.album);
  const carpetas = normalizar((c.ruta ?? "").split(/[\\/]/).slice(0, -1).slice(-CARPETAS_A_REVISAR).join("/"));
  const r = new Set();
  for (const [id, regla] of Object.entries(POR_GENERO)) if (regla.test(genero)) r.add(id);
  for (const [id, regla] of Object.entries(POR_ALBUM)) if (regla.test(album)) r.add(id);
  for (const [id, regla] of Object.entries(POR_CARPETA)) if (regla.test(carpetas)) r.add(id);
  // "Soundtrack" es de películas y series: el de un juego o un anime va en lo suyo
  if (r.has("videojuegos") || r.has("anime")) r.delete("soundtrack");
  const decada = decadaDe(c);
  if (decada !== null) r.add(`d${decada}`);
  return r;
}

export const claveAlbum = (c) => `${c.album}|${c.artista_album ?? ""}`;

/** Lo que tú moviste gana: primero la canción, luego su álbum, y si no lo deducido más los géneros que le sumaste a cada categoría. */
export function categoriasDe(c, cfg = {}) {
  const corregidas = cfg.canciones?.[c.db_id] ?? cfg.albumes?.[claveAlbum(c)];
  if (corregidas) {
    const r = new Set(corregidas);
    const decada = decadaDe(c);
    if (decada !== null && !r.has(SIN_DECADA) && !corregidas.some(esDecada)) r.add(`d${decada}`);
    return r;
  }
  let r = deducidas.get(c);
  if (!r) deducidas.set(c, (r = deducir(c)));
  const genero = normalizar(c.genero);
  const sumadas = genero ? cfg.propias?.filter((p) => p.generos?.includes(genero)) : null;
  return sumadas?.length ? new Set([...r, ...sumadas.map((p) => p.id)]) : r;
}

/** 1985 → 1980; sin año que se entienda, null. */
export function decadaDe(c) {
  const anio = parseInt(c.anio, 10);
  return anio >= 1900 && anio < 2100 ? Math.floor(anio / 10) * 10 : null;
}

/** 1980 → "80s", 2010 → "2010s". */
export const nombreDecada = (d) => (d < 2000 ? `${d % 100 || "00"}s` : `${d}s`);

/** Como artista_principal de biblioteca.py: el primero de "A, B" o "A & B", que es por el que se agrupan los artistas. */
export const artistaPrincipal = (texto) => (texto ?? "").split(/,|&| x | y | and |;|\//)[0].trim();
