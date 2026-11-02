// Mis dispositivos: el cel y la PC vinculados que se sincronizan solos en la misma red (python/wavedrop/sincronizar.py).
import { alEvento, py } from "./api.js";
import { mostrarHoja } from "./estado.svelte.js";
import { t } from "./idioma.svelte.js";

export const sinc = $state({
  estado: null, // lo de sincronizar.resumen(): este dispositivo, los vinculados, los cercanos y el avance
  vinculo: null, // un QR o link de vinculación leído: { ip, ips, puerto, codigo, h, nombre }
});

alEvento("sincronizacion", ({ tipo, ...r }) => (sinc.estado = r));

export async function cargarSinc() {
  sinc.estado = await py("sinc_estado");
}

/** misiccord://vincular?ip=…&ips=…&puerto=…&codigo=…&h=…&nombre=… (lo que lleva el QR). null si no es eso. */
export function leerVinculo(texto) {
  const m = /^misiccord:\/\/vincular\/?\?(.+)$/i.exec((texto || "").trim());
  if (!m) return null;
  const p = new URLSearchParams(m[1]);
  if (!p.get("ip") || !p.get("puerto") || !p.get("codigo")) return null;
  return { ip: p.get("ip"), ips: p.get("ips") || "", puerto: p.get("puerto"), codigo: p.get("codigo"), h: p.get("h") || "",
           nombre: p.get("nombre") || "" };
}

/**
 * Android 17+: sin el permiso de red local ("Dispositivos cercanos") nada de la Wi-Fi responde. Lo pide si falta;
 * si ya se negó, ofrece abrir los ajustes de la app. true si se puede seguir.
 */
export async function permisoRed() {
  const { invoke } = await import("@tauri-apps/api/core");
  const r = await invoke("red_local", { datos: { pedir: "permiso" } }).catch(() => ({ concedido: true }));
  if (r.concedido) return true;
  mostrarHoja({
    titulo: t("Falta un permiso"),
    subtitulo: t("Para encontrar tus otros dispositivos en la Wi-Fi, Misiccord necesita el permiso Dispositivos cercanos."),
    opciones: [{ texto: t("Abrir ajustes de la app"), icono: "ajustes",
                 accion: () => invoke("red_local", { datos: { pedir: "ajustes" } }).catch(() => {}) }],
  });
  return false;
}

// Al volver a la app (en el cel, Android pausa todo en segundo plano) se pone al día si hace rato que no
document.addEventListener("visibilitychange", () => {
  if (document.hidden) return;
  const viejos = (sinc.estado?.dispositivos ?? []).filter((d) => d.en_linea && !d.sincronizando && Date.now() / 1000 - (d.ultima ?? 0) > 60);
  for (const d of viejos) py("sinc_ahora", { id: d.id }).catch(() => {});
});
