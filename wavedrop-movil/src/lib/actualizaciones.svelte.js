// Buscar e instalar versiones nuevas de Misiccord publicadas en GitHub Releases.
//
// - Windows: plugin oficial de Tauri (latest.json firmado): descarga, instala y reinicia la app.
// - Android: se lee la última Release de GitHub, se baja el APK y se abre el instalador del sistema
//   (Android siempre pide confirmar; el APK debe estar firmado con la misma llave que la app instalada).
import { getVersion } from "@tauri-apps/api/app";
import { invoke } from "@tauri-apps/api/core";
import { alEvento, py } from "./api.js";
import { aviso, mostrarHoja } from "./estado.svelte.js";

export const REPO = "Accor-Dium/misiccord";
const esAndroid = /Android/i.test(navigator.userAgent);

export const act = $state({
  estado: "nada", // nada | buscando | al_dia | disponible | descargando | instalando | error
  actual: "",
  version: "",
  notas: "",
  pct: 0,
  error: "",
});

let pendienteEscritorio = null; // objeto Update del plugin de Tauri
let urlApk = null;

alEvento("actualizacion", ({ pct }) => (act.pct = pct));

/** "1.2.10" > "1.2.9" */
function esMasNueva(nueva, actual) {
  const a = nueva.replace(/^v/, "").split(".").map(Number);
  const b = actual.replace(/^v/, "").split(".").map(Number);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) > (b[i] || 0);
  }
  return false;
}

async function buscarAndroid() {
  const r = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (r.status === 404) return null; // todavía no hay versiones publicadas (o el repositorio es privado)
  if (!r.ok) throw new Error(`GitHub respondió ${r.status}`);
  const rel = await r.json();
  const apk = (rel.assets || []).find((a) => a.name.toLowerCase().endsWith(".apk"));
  if (!apk || !esMasNueva(rel.tag_name, act.actual)) return null;
  urlApk = apk.browser_download_url;
  return { version: rel.tag_name.replace(/^v/, ""), notas: rel.body || "" };
}

async function buscarEscritorio() {
  const { check } = await import("@tauri-apps/plugin-updater");
  pendienteEscritorio = await check();
  return pendienteEscritorio ? { version: pendienteEscritorio.version, notas: pendienteEscritorio.body || "" } : null;
}

/** Revisa si hay versión nueva. Con avisar=true muestra la invitación a actualizar. */
export async function buscarActualizacion({ avisar = true, manual = false } = {}) {
  if (act.estado === "buscando" || act.estado === "descargando") return;
  act.actual ||= await getVersion();
  act.estado = "buscando";
  act.error = "";
  try {
    const nueva = esAndroid ? await buscarAndroid() : await buscarEscritorio();
    if (!nueva) {
      act.estado = "al_dia";
      if (manual) aviso(`Ya tienes la versión más reciente (${act.actual})`, "ok");
      return;
    }
    act.version = nueva.version;
    act.notas = nueva.notas;
    act.estado = "disponible";
    if (avisar) {
      mostrarHoja({
        titulo: `Misiccord ${nueva.version} está disponible`,
        subtitulo: `Tienes la ${act.actual}`,
        opciones: [
          { texto: "Actualizar ahora", icono: "descargas", accion: instalarActualizacion },
          { texto: "Después", icono: "cerrar", accion: () => {} },
        ],
      });
    }
  } catch (e) {
    act.estado = "error";
    act.error = e?.message || String(e);
    if (manual) aviso("No se pudo revisar si hay actualizaciones", "error");
  }
}

export async function instalarActualizacion() {
  act.estado = "descargando";
  act.pct = 0;
  try {
    if (esAndroid) {
      const { ruta } = await py("actualizacion_descargar", { url: urlApk });
      act.estado = "instalando";
      const r = await invoke("instalar_apk", { ruta });
      if (r?.falta_permiso) {
        aviso("Permite que Misiccord instale apps y vuelve a tocar “Actualizar”");
        act.estado = "disponible";
      }
      return;
    }
    let total = 0;
    let bajado = 0;
    await pendienteEscritorio.downloadAndInstall((ev) => {
      if (ev.event === "Started") total = ev.data.contentLength || 0;
      if (ev.event === "Progress") {
        bajado += ev.data.chunkLength;
        act.pct = total ? Math.round((bajado / total) * 100) : 0;
      }
      if (ev.event === "Finished") act.estado = "instalando";
    });
    const { relaunch } = await import("@tauri-apps/plugin-process");
    await relaunch();
  } catch (e) {
    act.estado = "error";
    act.error = e?.message || String(e);
    aviso("No se pudo instalar la actualización", "error");
  }
}

/** Al abrir la app: revisa en silencio como máximo cada 12 horas. */
export function revisarAlIniciar() {
  try {
    const ultima = Number(localStorage.getItem("misiccord_ultima_revision") || 0);
    if (Date.now() - ultima < 12 * 3600 * 1000) return;
    localStorage.setItem("misiccord_ultima_revision", String(Date.now()));
  } catch {}
  setTimeout(() => buscarActualizacion({ avisar: true }), 4000);
}
