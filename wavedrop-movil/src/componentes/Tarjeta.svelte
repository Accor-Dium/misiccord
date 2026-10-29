<script>
  import { mantener } from "../lib/mantener.js";
  import Portada from "./Portada.svelte";

  // Tarjeta de álbum, canción o artista (redonda) para carruseles y rejillas.
  // alMantener: dejarla presionada (en canciones: agregar a la cola).
  let { portada, titulo, subtitulo = "", ancho = "148px", redonda = false, icono = "disco", alTocar, alMantener = null } = $props();
</script>

<button class="tarjeta" style:width={ancho} onclick={alTocar} class:redonda use:mantener={alMantener}>
  <Portada url={portada} {redonda} {icono} radio="12px" />
  <b class="cortar">{titulo}</b>
  {#if subtitulo}<small class="cortar">{subtitulo}</small>{/if}
</button>

<style>
  .tarjeta {
    display: flex; flex-direction: column; gap: 4px; text-align: left; min-width: 0;
    transition: transform 0.18s var(--curva);
  }
  .tarjeta:active { transform: scale(0.96); }
  .redonda { text-align: center; align-items: center; }
  .redonda b { font-size: 13.5px; font-weight: 600; }
  b { margin-top: 8px; font-size: 15px; font-weight: 700; width: 100%; }
  small { color: var(--tenue); font-size: 13.5px; width: 100%; }
</style>
