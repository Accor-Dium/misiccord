// Menú de una canción: el mismo al dejarla presionada y al tocar "⋯" (filas, tarjetas, reproductor).
// Arriba: Me gusta y tres acciones grandes (Reproducir después, Playlist, Compartir); abajo, todo lo demás.
import { py } from "./api.js";
import { compartir } from "./compartir.js";
import { pedirEliminar } from "./eliminar.js";
import { abrir, abrirAlbumDe, alternarMeGusta, aviso, cerrarReproductor, descargar, mostrarHoja, ui, verInfo } from "./estado.svelte.js";
import { t } from "./idioma.svelte.js";
import { agregarAlJam, puedoAgregar } from "./jam.svelte.js";
import { agregarACola, reproducir, rep } from "./reproductor.svelte.js";

async function aPlaylist(c) {
  const { playlists } = await py("biblioteca");
  mostrarHoja({
    titulo: t("Agregar a playlist"),
    opciones: playlists.length
      ? playlists.map((p) => ({ texto: p.nombre, icono: "lista", accion: async () => {
          await py("agregar_a_playlist", { id: p.id, db_ids: [c.db_id] });
          ui.version++;
          aviso(t("Agregada a “{nombre}”", { nombre: p.nombre }), "ok");
        } }))
      : [{ texto: t("Primero crea una playlist en Biblioteca"), icono: "agregar", accion: () => {} }],
  });
}

async function radio(c) {
  aviso(t("Armando la radio de “{titulo}”…", { titulo: c.titulo }));
  try {
    const r = await py("radio", { id: c.id, titulo: c.titulo, artista: c.artista });
    reproducir([c, ...r.canciones], 0, t("Radio de {titulo}", { titulo: c.titulo }));
  } catch (e) {
    aviso(e.message, "error");
  }
}

const primerArtista = (c) => (c.artista || "").split(",")[0].trim();

/** Ir a otra vista desde el menú: con el reproductor grande abierto, primero se cierra (si no, queda encima). */
function irA(f) {
  if (!ui.reproductorAbierto) return f();
  cerrarReproductor();
  setTimeout(f, 250);
}

/** extras: opciones propias de la vista (p. ej. "Quitar de esta playlist"), van primero en la lista. */
export async function menuCancion(c, extras = []) {
  const { gusta } = await py("me_gusta_es", { titulo: c.titulo, artista: c.artista }).catch(() => ({ gusta: false }));
  const enJam = puedoAgregar();

  const botones = [
    rep.actual
      ? { texto: t("Reproducir después"), icono: "siguiente", accion: () => {
          agregarACola(c, true);
          aviso(t("“{titulo}” suena después de esta", { titulo: c.titulo }), "ok");
        } }
      : { texto: t("Reproducir"), icono: "play", accion: () => reproducir([c], 0) },
    c.db_id
      ? { texto: t("A playlist"), icono: "lista", accion: () => aPlaylist(c) }
      : !c.ruta
        ? { texto: t("Descargar"), icono: "descargas", accion: () => descargar([c]) }
        : { texto: t("A la cola"), icono: "cola", accion: () => {
            agregarACola(c);
            aviso(t("“{titulo}” se agregó a la cola", { titulo: c.titulo }), "ok");
          } },
    { texto: t("Compartir"), icono: "compartir", accion: () => compartir([c], { titulo: c.titulo }) },
  ];

  const ops = [...extras];
  if (enJam) ops.push({ texto: t("Agregar al jam"), icono: "jam", accion: () => agregarAlJam(c) });
  ops.push({ texto: t("Iniciar radio"), icono: "radio", accion: () => radio(c) });
  ops.push({ texto: t("Agregar a la cola"), icono: "cola", accion: () => {
    agregarACola(c);
    aviso(t("“{titulo}” se agregó a la cola", { titulo: c.titulo }), "ok");
  } });
  if (c.album) ops.push({ texto: t("Ver álbum"), icono: "disco", accion: () => irA(() => abrirAlbumDe(c)) });
  if (c.artista) ops.push({ texto: t("Ver artista"), icono: "persona", accion: () => irA(() => abrir("buscar_artista", { nombre: primerArtista(c) })) });
  ops.push({ texto: c.ruta ? t("Información y etiquetas") : t("Información"), icono: "info", accion: () => verInfo(c) });
  if (c.db_id) ops.push({ texto: t("Eliminar de la biblioteca"), icono: "basura", peligro: true, accion: () =>
    pedirEliminar({ objetivo: { db_ids: [c.db_id] }, cuantas: 1, titulo: `“${c.titulo}”`, seBorra: (x) => x.ruta === c.ruta }) });

  navigator.vibrate?.(10);
  mostrarHoja({
    titulo: c.titulo, subtitulo: c.artista, portada: c.portada,
    cabAccion: { icono: "corazon", activo: gusta, texto: t("Me gusta"), accion: () => alternarMeGusta(c) },
    botones, opciones: ops,
  });
}
