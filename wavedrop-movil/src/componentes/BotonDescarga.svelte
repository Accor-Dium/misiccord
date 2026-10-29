<script>
  import { t } from "../lib/idioma.svelte.js";
  import { descargar, estadoDescarga } from "../lib/estado.svelte.js";
  import Icono from "./Icono.svelte";

  // Botón de descarga con anillo de progreso. Si ya la tienes, muestra una palomita.
  let { cancion } = $props();
  const trabajo = $derived(estadoDescarga(cancion));
  const pct = $derived(trabajo?.pct ?? 0);
  const ocupado = $derived(trabajo && ["cola", "buscando", "descargando", "etiquetando"].includes(trabajo.estado));
</script>

<button
  class="boton"
  class:listo={trabajo?.estado === "listo" || trabajo?.estado === "existe"}
  aria-label={t("Descargar")}
  onclick={(e) => {
    e.stopPropagation();
    if (!trabajo || trabajo.estado === "error" || trabajo.estado === "cancelado") descargar([cancion]);
  }}
>
  {#if trabajo?.estado === "listo" || trabajo?.estado === "existe"}
    <Icono nombre="check" tam={20} />
  {:else if ocupado}
    <svg width="28" height="28" viewBox="0 0 36 36" class="anillo">
      <circle cx="18" cy="18" r="15" class="fondo" />
      <circle cx="18" cy="18" r="15" class="avance" stroke-dasharray="94.2" stroke-dashoffset={94.2 * (1 - pct / 100)} />
    </svg>
  {:else}
    <Icono nombre="descargas" tam={21} />
  {/if}
</button>

<style>
  .boton { width: 40px; height: 40px; display: grid; place-items: center; color: var(--tenue); border-radius: 50%; }
  .boton:active { background: rgba(255, 255, 255, 0.08); }
  .listo { color: var(--cian); }
  .anillo { transform: rotate(-90deg); }
  .anillo circle { fill: none; stroke-width: 3.5; }
  .fondo { stroke: var(--borde-fuerte); }
  .avance { stroke: var(--cian); stroke-linecap: round; transition: stroke-dashoffset 0.4s var(--curva); }
</style>
