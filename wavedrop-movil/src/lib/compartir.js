// Compartir o exportar canciones descargadas (sueltas, álbumes o playlists).
// Android: el menú "Compartir" del sistema (WhatsApp, Telegram, Bluetooth, Drive, guardar en una USB…).
// PC: copiar los archivos al portapapeles (se pegan en WhatsApp/Telegram de escritorio), a una USB conectada
// o a cualquier carpeta. Lo que no está descargado se comparte como link de YouTube Music.
import { alEvento, py } from "./api.js";
import { copiar } from "./enlaces.svelte.js";
import { aviso, mostrarHoja } from "./estado.svelte.js";
import { canciones as nCanciones, t } from "./idioma.svelte.js";

const esAndroid = /Android/i.test(navigator.userAgent);
export const linkDe = (c) => `https://music.youtube.com/watch?v=${c.id}`;

/**
 * @param lista   canciones a compartir
 * @param titulo  qué se comparte (para el menú)
 * @param grupos  opcional: [{ carpeta, rutas, lista }] para exportar álbumes/playlists en su propia carpeta
 */
export async function compartir(lista, { titulo = "", grupos = null } = {}) {
  const rutas = [...new Set(lista.filter((c) => c.ruta).map((c) => c.ruta))];
  const enLinea = lista.filter((c) => !c.ruta && c.id);
  if (!rutas.length && !enLinea.length) return aviso(t("No hay nada que compartir"), "error");
  const texto = enLinea.length ? enLinea.map((c) => `${c.titulo} – ${c.artista}\n${linkDe(c)}`).join("\n\n") : null;

  if (esAndroid) {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("compartir", { datos: { rutas, texto: rutas.length ? null : texto, titulo: titulo || t("Compartir") } });
    } catch (e) {
      aviso(e?.message || String(e), "error");
    }
    return;
  }

  if (!rutas.length) {
    await copiar(texto);
    return aviso(enLinea.length === 1 ? t("Link copiado: pégalo donde quieras") : t("Links copiados: pégalos donde quieras"), "ok");
  }

  const grupo = grupos ?? [{ carpeta: "", rutas, lista: false }];
  const opciones = [
    { texto: t("Copiar archivos (pégalos en WhatsApp o Telegram)"), icono: "copiar", accion: async () => {
      try {
        await py("copiar_archivos", { rutas });
        aviso(rutas.length === 1 ? t("Archivo copiado: pégalo con Ctrl+V") : t("{n} archivos copiados: pégalos con Ctrl+V", { n: rutas.length }), "ok");
      } catch (e) {
        aviso(e.message, "error");
      }
    } },
  ];
  try {
    for (const d of (await py("destinos_exportar")).destinos) {
      opciones.push({ texto: t("Copiar a {nombre} ({letra}:)", { nombre: d.nombre, letra: d.letra }), icono: "usb",
                      accion: () => exportarA(grupo, d.ruta, `${d.nombre} (${d.letra}:)`) });
    }
  } catch {}
  opciones.push({ texto: t("Copiar a una carpeta…"), icono: "carpeta", accion: async () => {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const destino = await open({ directory: true, title: t("¿A dónde las copio?") });
    if (destino) exportarA(grupo, destino, destino);
  } });
  if (rutas.length === 1) {
    opciones.push({ texto: t("Mostrar en el explorador"), icono: "abrir", accion: () => py("mostrar_archivo", { ruta: rutas[0] }) });
  }
  if (enLinea.length) {
    opciones.push({ texto: t("Copiar links de las que no tienes"), icono: "link", accion: async () => {
      await copiar(texto);
      aviso(t("Links copiados"), "ok");
    } });
  }
  mostrarHoja({ titulo: titulo || t("Compartir"), subtitulo: nCanciones(rutas.length), opciones });
}

async function exportarA(grupos, destino, nombre) {
  try {
    const { total } = await py("exportar_canciones", { grupos, destino, nombre });
    aviso(t("Copiando {n} a {destino}…", { n: nCanciones(total), destino: nombre }), "info", { id: "exportar", duracion: 0 });
  } catch (e) {
    aviso(e.message, "error");
  }
}

alEvento("exportar", (d) => {
  if (d.estado === "copiando") {
    aviso(t("Copiando a {destino}: {hechas} de {total}", d), "info", { id: "exportar", duracion: 0, avance: d.hechas / d.total });
  } else if (d.estado === "listo") {
    const malas = d.fallidas?.length ?? 0;
    aviso(malas ? t("Se copiaron {n}; {m} fallaron", { n: d.copiadas, m: malas }) : t("Listo: {n} en {destino}", { n: nCanciones(d.copiadas), destino: d.destino }),
          malas ? "error" : "ok", { id: "exportar", accion: { texto: t("Abrir"), f: () => py("mostrar_archivo", { ruta: d.carpeta }) } });
  } else {
    aviso(t("No se pudo copiar: {error}", d), "error", { id: "exportar" });
  }
});
