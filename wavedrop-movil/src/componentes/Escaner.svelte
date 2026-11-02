<script>
  import { fade } from "svelte/transition";
  import { ui } from "../lib/estado.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import Icono from "./Icono.svelte";

  // Lector de QR (lib/qr.js): la cámara nativa queda detrás de la WebView transparente y aquí se tapa todo
  // menos el cuadro donde va el QR, con su título y "Cancelar". El resto de la app se oculta (html.escaneando).
  $effect(() => {
    document.documentElement.classList.toggle("escaneando", !!ui.escaner);
    return () => document.documentElement.classList.remove("escaneando");
  });

  async function cancelar() {
    const { cancel } = await import("@tauri-apps/plugin-barcode-scanner");
    cancel().catch(() => {});
  }
</script>

{#if ui.escaner}
  <div class="escaner" transition:fade={{ duration: 160 }}>
    <header>
      <b>{ui.escaner.titulo || t("Escanea el QR")}</b>
      {#if ui.escaner.texto}<small>{ui.escaner.texto}</small>{/if}
    </header>
    <div class="marco" aria-hidden="true">
      <span class="esquina a"></span><span class="esquina b"></span><span class="esquina c"></span><span class="esquina d"></span>
      <span class="linea"></span>
    </div>
    <button class="pildora oscura cancelar" onclick={cancelar}><Icono nombre="cerrar" tam={20} /> {t("Cancelar")}</button>
  </div>
{/if}

<style>
  .escaner {
    position: fixed; inset: 0; z-index: 200; display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 28px; padding: calc(env(safe-area-inset-top, 0px) + 24px) 24px calc(var(--seguro-abajo) + 24px); overflow: hidden;
  }
  header { display: flex; flex-direction: column; align-items: center; gap: 6px; text-align: center; max-width: 320px; position: relative; }
  header b { font-size: 20px; font-weight: 800; }
  header small { color: rgba(255, 255, 255, 0.72); line-height: 1.45; font-size: 14px; }
  /* Lo de afuera del cuadro se tapa con su propia sombra: solo se ve la cámara dentro */
  .marco {
    position: relative; width: min(72vw, 52vh, 300px); aspect-ratio: 1; border-radius: 26px; flex-shrink: 0;
    box-shadow: 0 0 0 200vmax rgba(4, 9, 14, 0.9);
  }
  header, .cancelar { z-index: 1; }
  .esquina { position: absolute; width: 38px; height: 38px; border: 4px solid var(--cian); }
  .a { top: -2px; left: -2px; border-right: 0; border-bottom: 0; border-top-left-radius: 28px; }
  .b { top: -2px; right: -2px; border-left: 0; border-bottom: 0; border-top-right-radius: 28px; }
  .c { bottom: -2px; left: -2px; border-right: 0; border-top: 0; border-bottom-left-radius: 28px; }
  .d { bottom: -2px; right: -2px; border-left: 0; border-top: 0; border-bottom-right-radius: 28px; }
  .linea {
    position: absolute; left: 10%; right: 10%; top: 12%; height: 2px; border-radius: 2px;
    background: var(--cian); box-shadow: 0 0 12px var(--cian); animation: barrer 2.2s ease-in-out infinite alternate;
  }
  @keyframes barrer { to { top: 88%; } }
  .cancelar { height: 48px; padding: 0 24px; display: inline-flex; align-items: center; gap: 8px; position: relative; }
</style>
