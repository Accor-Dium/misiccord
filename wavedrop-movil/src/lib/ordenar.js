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
];

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
