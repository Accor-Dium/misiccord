// Filtros de Biblioteca: décadas y categorías que juntan los muchos géneros de las etiquetas, sin cambiar los archivos.
// Se deducen aquí (es instantáneo y no usa internet) del género, el nombre del álbum y la carpeta. Lo que no acierte se
// corrige a mano por álbum: lo corregido (`manual`, de biblioteca.categorias_albumes) reemplaza a lo deducido.
import { normalizar } from "./ordenar.js";

export const CATEGORIAS = [["jazz", "Jazz"], ["pop", "Pop"], ["rock", "Rock"], ["soundtrack", "Soundtrack"], ["videojuegos", "Videojuegos"], ["anime", "Anime"]];

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
  return r;
}

export const claveAlbum = (c) => `${c.album}|${c.artista_album ?? ""}`;

export function categoriasDe(c, manual = {}) {
  const corregidas = manual[claveAlbum(c)];
  if (corregidas) return new Set(corregidas);
  let r = deducidas.get(c);
  if (!r) deducidas.set(c, (r = deducir(c)));
  return r;
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
