// Leer un QR con la cámara (solo en el cel): lo usan Jams (unirse) y Mis dispositivos (vincular).
import { aviso, mostrarHoja, ui } from "./estado.svelte.js";
import { t } from "./idioma.svelte.js";

/** El texto del QR, o null si se canceló o falló (el error ya se avisó). */
export async function leerQR() {
  const { invoke } = await import("@tauri-apps/api/core");
  // Si la app volvió a una sesión que siguió sonando sin ella, la cámara ya no tiene su pantalla: hay que reiniciar
  const sesion = await invoke("sesion", { datos: {} }).catch(() => ({}));
  if (sesion.reanudada) {
    mostrarHoja({
      titulo: t("Hay que reiniciar Misiccord"),
      subtitulo: t("Para usar la cámara (la música se detiene)"),
      opciones: [{ texto: t("Reiniciar ahora"), icono: "actualizar", accion: () => invoke("sesion", { datos: { accion: "reiniciar" } }) }],
    });
    return null;
  }
  try {
    // Cámara a pantalla completa con el escáner nativo
    const { scan, cancel, checkPermissions, requestPermissions, Format } = await import("@tauri-apps/plugin-barcode-scanner");
    let permiso = await checkPermissions();
    if (permiso !== "granted") permiso = await requestPermissions();
    if (permiso !== "granted") {
      aviso(t("Sin permiso de cámara no puedo leer el QR"), "error");
      return null;
    }
    // "Atrás" de Android mientras la cámara está abierta: cancelar el escaneo en vez de salir de la app
    ui.alAtras = () => cancel().catch(() => {});
    history.pushState({ wavedrop: "camara" }, "");
    try {
      return (await scan({ windowed: false, formats: [Format.QRCode] }))?.content ?? null;
    } finally {
      if (ui.alAtras) {
        ui.alAtras = () => {}; // quitar la entrada del historial sin navegar
        history.back();
      }
    }
  } catch (err) {
    const texto = err?.message || String(err);
    if (!/cancel/i.test(texto)) aviso(texto, "error");
    return null;
  }
}
