// Comunicación con el núcleo de Python (wavedrop.api) a través de Tauri.
import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

/** Llama a una función de wavedrop.api y devuelve su respuesta (lanza Error si Python falló). */
export async function py(funcion, datos = {}) {
  const r = JSON.parse(await invoke("py", { funcion, datos: JSON.stringify(datos) }));
  if (!r.ok) {
    const e = new Error(r.error);
    e.detalle = r.detalle;
    console.error(`[py:${funcion}]`, r.error, r.detalle);
    throw e;
  }
  return r;
}

// Avisos que manda Python cuando algo termina o avanza (descargas, recomendaciones, escaneo)
const oyentes = new Map();
listen("python", (e) => {
  const datos = JSON.parse(e.payload);
  for (const f of oyentes.get(datos.tipo) ?? []) f(datos);
});

/** Escucha un tipo de aviso de Python; devuelve la función para dejar de escuchar. */
export function alEvento(tipo, f) {
  if (!oyentes.has(tipo)) oyentes.set(tipo, new Set());
  oyentes.get(tipo).add(f);
  return () => oyentes.get(tipo).delete(f);
}

/** Convierte una ruta local o URL en algo que <img>/<audio> pueden cargar. */
export function src(ruta) {
  if (!ruta) return null;
  return /^https?:\/\//.test(ruta) ? ruta : convertFileSrc(ruta);
}

export function tiempo(segundos) {
  if (!segundos || !isFinite(segundos)) return "0:00";
  const s = Math.floor(segundos);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
