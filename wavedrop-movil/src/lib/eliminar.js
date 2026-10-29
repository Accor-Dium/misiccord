// Borrar canciones descargadas: una, varias, un álbum o un artista completo.
// El archivo se borra del dispositivo y la canción desaparece de todos lados (biblioteca, playlists,
// historial, cola, jam). Siempre se pide confirmar antes.
import { py } from "./api.js";
import { aviso, mostrarHoja, ui } from "./estado.svelte.js";
import { olvidarRutas, soltarSi } from "./reproductor.svelte.js";

const plural = (n) => (n === 1 ? "1 canción" : `${n} canciones`);

/**
 * @param objetivo  { db_ids: [...] } | { album: { nombre, grupo, artista } } | { artista: "nombre" }
 * @param cuantas   cuántas canciones se van a borrar (para el texto)
 * @param titulo    qué se borra, para la hoja de confirmación ("“Canción”", "el álbum Tal"...)
 * @param seBorra   (cancion) => bool, para soltar el archivo si es lo que suena
 */
export function pedirEliminar({ objetivo, cuantas, titulo, seBorra, alTerminar }) {
  return new Promise((listo) => {
    mostrarHoja({
      titulo: `¿Eliminar ${titulo}?`,
      subtituloLargo: true,
      subtitulo: `Se borra${cuantas === 1 ? "" : "n"} ${plural(cuantas)} de este dispositivo, de tus playlists y del historial.`,
      opciones: [
        { texto: `Eliminar ${plural(cuantas)}`, icono: "basura", peligro: true, accion: async () => {
          const r = await eliminar(objetivo, seBorra);
          alTerminar?.(r);
          listo(r);
        } },
        { texto: "Cancelar", icono: "cerrar", accion: () => listo(null) },
      ],
    });
  });
}

async function eliminar(objetivo, seBorra) {
  soltarSi(seBorra);
  try {
    const r = await py("eliminar_canciones", objetivo);
    olvidarRutas(r.rutas);
    ui.version++; // las vistas abiertas se recargan
    if (r.fallidas.length) aviso(`No se pudieron borrar ${plural(r.fallidas.length)}: ${r.fallidas[0].error}`, "error");
    else aviso(`Se eliminó ${plural(r.eliminadas)}`, "ok");
    return r;
  } catch (e) {
    aviso(e.message || "No se pudo eliminar", "error");
    return null;
  }
}
