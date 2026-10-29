// Idioma de la interfaz. Los textos se escriben en español en el código y se pasan por t("…");
// las traducciones viven en lib/textos/<idioma>.js con el texto en español como clave (lo que falte sale en español).
// Por defecto se usa el idioma del dispositivo; en Ajustes se puede fijar otro (localStorage "misiccord_idioma").
import { en } from "./textos/en.js";

export const IDIOMAS = [
  ["", "Automático (del dispositivo)"],
  ["es", "Español"],
  ["en", "English"],
];
const TEXTOS = { en };

function delDispositivo() {
  for (const l of navigator.languages ?? [navigator.language]) {
    const base = (l || "").slice(0, 2).toLowerCase();
    if (base === "es" || TEXTOS[base]) return base;
  }
  return "es";
}

export function idiomaElegido() {
  try { return localStorage.getItem("misiccord_idioma") || ""; } catch { return ""; }
}

export const idioma = $state({ actual: idiomaElegido() || delDispositivo() });
document.documentElement.lang = idioma.actual;

/** t("Hola {nombre}", { nombre }) → texto en el idioma actual. */
export function t(texto, datos) {
  let s = TEXTOS[idioma.actual]?.[texto] ?? texto;
  if (datos) s = s.replace(/\{(\w+)\}/g, (m, k) => (datos[k] ?? m));
  return s;
}

/** "1 canción" / "5 canciones" (y en inglés "1 song" / "5 songs"). */
export function canciones(n) {
  return n === 1 ? t("1 canción") : t("{n} canciones", { n });
}

/** Cambia el idioma. La app se recarga para que todo (también lo que ya estaba armado) salga en el nuevo. */
export function ponerIdioma(codigo) {
  try { codigo ? localStorage.setItem("misiccord_idioma", codigo) : localStorage.removeItem("misiccord_idioma"); } catch {}
  if ((codigo || delDispositivo()) !== idioma.actual) location.reload();
}

/** Para fechas y números (Intl). */
export const local = () => (idioma.actual === "en" ? "en-US" : "es-MX");
