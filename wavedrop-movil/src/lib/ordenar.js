import { t } from "./idioma.svelte.js";
// Buscar, ordenar y agrupar la biblioteca en la interfaz (es instantáneo: no hace falta preguntarle a Python).

/** Minúsculas y sin acentos: "Corazón" y "corazon" son lo mismo al buscar y al ordenar. */
export const normalizar = (t) => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

/** ¿Están todas las palabras de la búsqueda en alguno de los textos? (en cualquier orden) */
export function coincide(consulta, ...textos) {
  const donde = normalizar(textos.join(" "));
  return normalizar(consulta).split(/\s+/).filter(Boolean).every((p) => donde.includes(p));
}

// "The Beatles" se ordena en la B, como en las demás apps de música.
// Ordenar compara miles de veces: cada texto se normaliza una sola vez y hay un solo Collator
// (localeCompare con opciones es mucho más lento).
const sinArticulos = new Map();
function sinArticulo(texto) {
  let r = sinArticulos.get(texto);
  if (r === undefined) sinArticulos.set(texto, (r = normalizar(texto).replace(/^the\s+/, "")));
  return r;
}
const comparar = new Intl.Collator("es", { sensitivity: "base", numeric: true }).compare;

/** Letra del índice: A–Z, o "#" para números y otros alfabetos. */
export function letraDe(texto) {
  const c = sinArticulo(texto)[0] || "";
  return /[a-z]/.test(c) ? c.toUpperCase() : "#";
}

/** Cualquier lista (artistas, playlists) en grupos por letra inicial, "#" al final: [{ titulo, items }]. */
export function agruparPorLetra(items, nombreDe) {
  const lista = [...items].sort((a, b) => comparar(sinArticulo(nombreDe(a)), sinArticulo(nombreDe(b))));
  const ordenada = [...lista.filter((x) => letraDe(nombreDe(x)) !== "#"), ...lista.filter((x) => letraDe(nombreDe(x)) === "#")];
  const grupos = [];
  for (const x of ordenada) {
    const g = letraDe(nombreDe(x));
    if (grupos.at(-1)?.titulo !== g) grupos.push({ titulo: g, items: [] });
    grupos.at(-1).items.push(x);
  }
  return grupos;
}

export const ORDENES = [
  ["titulo", t("Título (A–Z)")],
  ["artista", t("Artista (A–Z)")],
  ["album", t("Álbum")],
  ["recientes", t("Agregadas recientemente")],
  ["reproducidas", t("Más reproducidas")],
];

// Las demás pestañas: todas se pueden ordenar y agrupar por nombre
export const ORDENES_LISTA = {
  albumes: [["nombre", t("Nombre (A–Z)")], ["artista", t("Artista (A–Z)")], ["anio", t("Año")], ["canciones", t("Más canciones")]],
  artistas: [["nombre", t("Nombre (A–Z)")], ["canciones", t("Más canciones")]],
  playlists: [["nombre", t("Nombre (A–Z)")], ["canciones", t("Más canciones")]],
  generos: [["nombre", t("Nombre (A–Z)")], ["canciones", t("Más canciones")]],
};

/** Álbumes, artistas, playlists o géneros ordenados y en grupos con encabezado: [{ titulo, items }]. */
export function agruparLista(items, orden) {
  if (orden === "artista") return agruparPorLetra(items, (x) => x.artista);
  if (orden === "canciones") {
    const lista = [...items].sort((a, b) => b.canciones - a.canciones || comparar(a.nombre, b.nombre));
    return lista.length ? [{ titulo: t("Más canciones"), items: lista }] : [];
  }
  if (orden === "anio") {
    const lista = [...items].sort((a, b) => comparar(String(b.anio || ""), String(a.anio || "")) || comparar(a.nombre, b.nombre));
    const grupos = [];
    for (const x of lista) {
      const g = x.anio ? String(x.anio).slice(0, 4) : t("Sin año");
      if (grupos.at(-1)?.titulo !== g) grupos.push({ titulo: g, items: [] });
      grupos.at(-1).items.push(x);
    }
    return grupos;
  }
  return agruparPorLetra(items, (x) => x.nombre);
}

function puesto(i, c) {
  if (!c.veces) return t("Sin reproducir");
  if (i < 10) return t("Top 10");
  if (i < 50) return t("Top 50");
  return t("Las demás");
}

function periodo(segundos) {
  const dias = (Date.now() / 1000 - (segundos || 0)) / 86400;
  if (dias < 7) return t("Esta semana");
  if (dias < 31) return t("Este mes");
  if (dias < 92) return t("Últimos 3 meses");
  return t("Antes");
}

/**
 * Canciones ordenadas y en grupos con encabezado: [{ titulo, canciones }].
 * Por título o artista se agrupa por letra (y "#" va al final); por álbum, por álbum; por recientes, por periodo.
 */
export function agrupar(canciones, orden) {
  let lista = [...canciones];
  let grupoDe;
  if (orden === "artista") {
    lista.sort((a, b) => comparar(sinArticulo(a.artista), sinArticulo(b.artista)) || comparar(a.album || "", b.album || "")
      || (a.pista ?? 0) - (b.pista ?? 0) || comparar(a.titulo, b.titulo));
    grupoDe = (c) => letraDe(c.artista);
  } else if (orden === "album") {
    lista.sort((a, b) => comparar(a.album || "~", b.album || "~") || (a.pista ?? 0) - (b.pista ?? 0) || comparar(a.titulo, b.titulo));
    grupoDe = (c) => c.album || t("Sin álbum");
  } else if (orden === "recientes") {
    lista.sort((a, b) => (b.agregada || 0) - (a.agregada || 0));
    grupoDe = (c) => periodo(c.agregada);
  } else if (orden === "reproducidas") {
    lista.sort((a, b) => (b.veces || 0) - (a.veces || 0) || comparar(sinArticulo(a.titulo), sinArticulo(b.titulo)));
    const puestos = new Map(lista.map((c, i) => [c, puesto(i, c)]));
    grupoDe = (c) => puestos.get(c);
  } else {
    lista.sort((a, b) => comparar(sinArticulo(a.titulo), sinArticulo(b.titulo)));
    grupoDe = (c) => letraDe(c.titulo);
  }
  if (orden === "titulo" || orden === "artista") {
    // Lo que no empieza con letra va al final, como en el índice
    lista = [...lista.filter((c) => grupoDe(c) !== "#"), ...lista.filter((c) => grupoDe(c) === "#")];
  }
  const grupos = [];
  for (const c of lista) {
    const g = grupoDe(c);
    // Con `comparar`, como al ordenar: "Días de Fuego" y "Días de fuego" se intercalan y serían grupos repetidos
    if (!grupos.length || comparar(grupos.at(-1).titulo, g)) grupos.push({ titulo: g, canciones: [] });
    grupos.at(-1).canciones.push(c);
  }
  return grupos;
}
