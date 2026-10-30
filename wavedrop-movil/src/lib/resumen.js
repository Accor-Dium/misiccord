// Resumen tipo YouTube Music / Apple Music: el último día del mes, del trimestre o del año aparece un aviso que abre
// la presentación (Resumen.svelte). Una sola vez por periodo (localStorage "misiccord_resumen_visto").
import { py } from "./api.js";
import { aviso, ui } from "./estado.svelte.js";
import { local, t } from "./idioma.svelte.js";

const inicioDe = (fecha, tipo) => {
  const mes = fecha.getMonth();
  if (tipo === "anio") return new Date(fecha.getFullYear(), 0, 1);
  if (tipo === "trimestre") return new Date(fecha.getFullYear(), mes - (mes % 3), 1);
  return new Date(fecha.getFullYear(), mes, 1);
};

/** Días que van del periodo (lo que se le pide a las estadísticas). */
export function diasDelPeriodo(tipo, fecha = new Date()) {
  return Math.max(1, Math.ceil((fecha - inicioDe(fecha, tipo)) / 86400000));
}

/** "octubre de 2026", "4.º trimestre de 2026", "2026". */
export function nombrePeriodo(tipo, fecha = new Date()) {
  if (tipo === "anio") return String(fecha.getFullYear());
  if (tipo === "trimestre") return t("Trimestre {n} de {anio}", { n: Math.floor(fecha.getMonth() / 3) + 1, anio: fecha.getFullYear() });
  return fecha.toLocaleDateString(local(), { month: "long", year: "numeric" });
}

/** ¿Hoy cierra algo? Lo más grande gana: el 31 de diciembre es el resumen del año, no el del mes. */
export function periodoQueCierra(fecha = new Date()) {
  const manana = new Date(fecha);
  manana.setDate(fecha.getDate() + 1);
  if (manana.getDate() !== 1) return null;
  const mes = fecha.getMonth();
  return mes === 11 ? "anio" : (mes + 1) % 3 === 0 ? "trimestre" : "mes";
}

export function abrirResumen(tipo) {
  ui.resumen = { tipo, dias: diasDelPeriodo(tipo), nombre: nombrePeriodo(tipo) };
}

export async function revisarResumen() {
  const hoy = new Date();
  const tipo = periodoQueCierra(hoy);
  if (!tipo) return;
  const clave = `${tipo}-${hoy.getFullYear()}-${hoy.getMonth()}`;
  try {
    if (localStorage.getItem("misiccord_resumen_visto") === clave) return;
    const e = await py("estadisticas", { dias: diasDelPeriodo(tipo, hoy) });
    if (e.actual.reproducciones < 5) return; // casi no hay nada que contar
    localStorage.setItem("misiccord_resumen_visto", clave);
    const texto = tipo === "anio" ? t("Ya está tu resumen del año") : tipo === "trimestre" ? t("Ya está tu resumen del trimestre") : t("Ya está tu resumen del mes");
    aviso(texto, "ok", { duracion: 20000, accion: { texto: t("Ver"), f: () => abrirResumen(tipo) } });
  } catch {}
}
