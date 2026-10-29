// Links para unirse a un jam: al abrir uno (desde WhatsApp, el navegador o la cámara) se abre Misiccord
// y entra al jam.
//
// Formatos que se entienden:
//   https://accor-dium.github.io/misiccord/jam/#ip=…&puerto=…&codigo=…&nombre=…[&url=https://…]   (el que se comparte)
//   misiccord://jam?ip=…&puerto=…&codigo=…                                                         (el que abre la app)
// Los datos van después de "#": el navegador no se los manda a GitHub, se quedan en el teléfono.
import { irPestana } from "./estado.svelte.js";
import { jam } from "./jam.svelte.js";

export const PAGINA_JAM = "https://accor-dium.github.io/misiccord/jam/";

/** Lee cualquiera de los formatos; null si no es un link de jam. */
export function leerInvitacion(texto) {
  const t = (texto || "").trim();
  let parametros = null;
  const propio = /^(?:misiccord|wavedrop):\/\/jam\/?\?(.+)$/i.exec(t);
  if (propio) parametros = propio[1];
  else if (t.toLowerCase().startsWith(PAGINA_JAM.toLowerCase())) {
    const resto = t.slice(PAGINA_JAM.length);
    parametros = resto.replace(/^[#?]/, "");
  }
  if (!parametros) return null;
  const p = new URLSearchParams(parametros);
  const codigo = p.get("codigo");
  if (!codigo || (!p.get("ip") && !p.get("url"))) return null;
  return { ip: p.get("ip"), puerto: p.get("puerto") || "47480", codigo, nombre: p.get("nombre") || "", url: p.get("url") || null };
}

/** El link para compartir (abre la app sola; si no la tienes, ofrece descargarla). */
export function linkParaCompartir({ ip, puerto, codigo, nombre, url }) {
  const p = new URLSearchParams({ ip: ip || "", puerto: String(puerto || ""), codigo, nombre: nombre || "" });
  if (url) p.set("url", url);
  return `${PAGINA_JAM}#${p}`;
}

function recibir(urls) {
  for (const u of urls || []) {
    const datos = leerInvitacion(u);
    if (!datos) continue;
    if (jam.sala) return; // ya estás en un jam: no se cambia solo
    jam.invitacion = datos;
    irPestana("jams");
    return;
  }
}

/** Escucha los links con los que se abre la app (al arrancar y mientras ya está abierta). */
export async function escucharEnlaces() {
  try {
    const { getCurrent, onOpenUrl } = await import("@tauri-apps/plugin-deep-link");
    recibir(await getCurrent());
    await onOpenUrl(recibir);
  } catch (e) {
    console.warn("[enlaces]", e);
  }
}

/** Copia texto al portapapeles (con respaldo para WebViews sin permiso de portapapeles). */
export async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = texto;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  }
}
