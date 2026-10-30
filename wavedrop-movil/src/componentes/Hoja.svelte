<script>
  import { fade, fly } from "svelte/transition";
  import { cerrarHoja, ui } from "../lib/estado.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Hoja de opciones que sube desde abajo (como el menú "⋯" de una canción).
  // hoja.botones: acciones grandes arriba (Reproducir después, Playlist, Compartir).
  // hoja.cabAccion: botón junto al título que no cierra la hoja (Me gusta): { icono, activo, accion }.
  function elegir(op) {
    cerrarHoja();
    setTimeout(op.accion, 120);
  }

  async function tocarCab() {
    const a = ui.hoja.cabAccion;
    const r = await a.accion();
    if (typeof r === "boolean" && ui.hoja?.cabAccion === a) a.activo = r;
  }
</script>

{#if ui.hoja}
  <div class="velo" transition:fade={{ duration: 200 }} onclick={cerrarHoja} role="presentation"></div>
  <div class="hoja" transition:fly={{ y: 400, duration: 320, opacity: 1 }} role="dialog" aria-label={ui.hoja.titulo}>
    <div class="asa"></div>
    {#if ui.hoja.titulo}
      <div class="cab">
        {#if ui.hoja.portada !== undefined}<Portada url={ui.hoja.portada} tam="52px" radio="8px" />{/if}
        <div class="textos">
          <b class="cortar">{ui.hoja.titulo}</b>
          {#if ui.hoja.subtitulo}<small class:cortar={!ui.hoja.subtituloLargo}>{ui.hoja.subtitulo}</small>{/if}
        </div>
        {#if ui.hoja.cabAccion}
          <button class="cab-boton" class:activo={ui.hoja.cabAccion.activo} onclick={tocarCab}
            aria-label={ui.hoja.cabAccion.texto} aria-pressed={ui.hoja.cabAccion.activo}>
            <Icono nombre={ui.hoja.cabAccion.icono} relleno={ui.hoja.cabAccion.activo} tam={24} />
          </button>
        {/if}
        <button class="cab-boton" onclick={cerrarHoja} aria-label={t("Cerrar")}><Icono nombre="cerrar" tam={22} /></button>
      </div>
    {/if}
    {#if ui.hoja.botones?.length}
      <div class="botones" style:grid-template-columns="repeat({ui.hoja.botones.length}, minmax(0, 1fr))">
        {#each ui.hoja.botones as op}
          <button class="grande" onclick={() => elegir(op)}>
            <span class="caja"><Icono nombre={op.icono} tam={24} /></span>
            <span class="cortar">{op.texto}</span>
          </button>
        {/each}
      </div>
    {/if}
    {#each ui.hoja.opciones as op}
      <button class="opcion" class:peligro={op.peligro} onclick={() => elegir(op)}>
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
    max-height: 85vh; overflow-y: auto;
  }
  .asa { width: 40px; height: 4px; border-radius: 2px; background: var(--borde-fuerte); margin: 4px auto 12px; }
  .cab { display: flex; gap: 12px; align-items: center; padding: 4px 4px 14px 8px; border-bottom: 1px solid var(--borde); margin-bottom: 6px; }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .textos small { color: var(--tenue); }
  .cab-boton { width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center; flex-shrink: 0; color: var(--texto); }
  .cab-boton:active { background: var(--tarjeta-2); }
  .cab-boton.activo { color: #ff4d6d; }
  .botones { display: grid; gap: 10px; padding: 8px 4px 10px; }
  .grande { display: flex; flex-direction: column; align-items: center; gap: 8px; font-size: 13.5px; font-weight: 600; min-width: 0; }
  .grande .caja {
    width: 100%; height: 64px; border-radius: 14px; display: grid; place-items: center;
    background: var(--tarjeta-2); transition: background 0.15s, transform 0.15s var(--curva);
  }
  .grande:active .caja, .grande:hover .caja { background: var(--borde-fuerte); }
  .grande:active .caja { transform: scale(0.95); }
  .grande span.cortar { max-width: 100%; }
  .opcion {
    width: 100%; display: flex; align-items: center; gap: 16px; padding: 13px 10px; border-radius: 12px;
    font-size: 16px; text-align: left;
  }
  .opcion:active, .opcion:hover { background: var(--tarjeta-2); }
  .peligro { color: var(--rojo); font-weight: 700; }
  .textos small:not(.cortar) { line-height: 1.4; margin-top: 2px; }
  @media (min-width: 900px) and (min-height: 561px) {
    /* En escritorio, ventana centrada en vez de hoja que sube */
    .hoja { left: calc(50% - 230px); right: auto; width: 460px; bottom: auto; top: 10vh; max-height: 80vh; border-radius: 20px; padding-bottom: 12px; }
    .asa { display: none; }
  }
  /* Cel acostado: centrada y no más ancha de lo cómodo (a todo lo ancho los renglones quedaban larguísimos) */
  @media (orientation: landscape) and (max-height: 560px) {
    .hoja { left: calc(50% - min(240px, 45vw)); right: auto; width: min(480px, 90vw); max-height: 92vh; }
  }
</style>
