<script>
  import { fade, fly } from "svelte/transition";
  import { cerrarHoja, ui } from "../lib/estado.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Hoja de opciones que sube desde abajo (como el menú "⋯" de una canción).
</script>

{#if ui.hoja}
  <div class="velo" transition:fade={{ duration: 200 }} onclick={cerrarHoja} role="presentation"></div>
  <div class="hoja" transition:fly={{ y: 400, duration: 320, opacity: 1 }}>
    <div class="asa"></div>
    {#if ui.hoja.titulo}
      <div class="cab">
        {#if ui.hoja.portada !== undefined}<Portada url={ui.hoja.portada} tam="52px" radio="8px" />{/if}
        <div class="textos">
          <b class="cortar">{ui.hoja.titulo}</b>
          {#if ui.hoja.subtitulo}<small class:cortar={!ui.hoja.subtituloLargo}>{ui.hoja.subtitulo}</small>{/if}
        </div>
      </div>
    {/if}
    {#each ui.hoja.opciones as op}
      <button
        class="opcion"
        class:peligro={op.peligro}
        onclick={() => {
          cerrarHoja();
          setTimeout(op.accion, 120);
        }}
      >
        <Icono nombre={op.icono} tam={22} />
        <span>{op.texto}</span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .velo { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.55); z-index: 60; }
  .hoja {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 61; background: var(--tarjeta);
    border-radius: 22px 22px 0 0; padding: 8px 12px calc(16px + var(--seguro-abajo));
    max-height: 80vh; overflow-y: auto;
  }
  .asa { width: 40px; height: 4px; border-radius: 2px; background: var(--borde-fuerte); margin: 4px auto 12px; }
  .cab { display: flex; gap: 12px; align-items: center; padding: 4px 8px 14px; border-bottom: 1px solid var(--borde); margin-bottom: 6px; }
  .textos { min-width: 0; display: flex; flex-direction: column; }
  .textos small { color: var(--tenue); }
  .opcion {
    width: 100%; display: flex; align-items: center; gap: 16px; padding: 14px 10px; border-radius: 12px;
    font-size: 16px; text-align: left;
  }
  .opcion:active, .opcion:hover { background: var(--tarjeta-2); }
  .peligro { color: var(--rojo); font-weight: 700; }
  .textos small:not(.cortar) { line-height: 1.4; margin-top: 2px; }
  @media (min-width: 900px) {
    /* En escritorio, ventana centrada en vez de hoja que sube */
    .hoja { left: calc(50% - 220px); right: auto; width: 440px; bottom: auto; top: 16vh; border-radius: 20px; padding-bottom: 12px; }
    .asa { display: none; }
  }
</style>
