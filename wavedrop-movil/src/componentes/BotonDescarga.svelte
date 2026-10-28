<script>
  import { descargar, estadoDescarga } from "../lib/estado.svelte.js";
  import Icono from "./Icono.svelte";

  // Botón de descarga con anillo de progreso. Si ya la tienes, muestra una palomita.
  let { cancion } = $props();
  const t = $derived(estadoDescarga(cancion));
  const pct = $derived(t?.pct ?? 0);
  const ocupado = $derived(t && ["cola", "buscando", "descargando", "etiquetando"].includes(t.estado));
</script>

<button
  class="boton"
  class:listo={t?.estado === "listo" || t?.estado === "existe"}
  aria-label="Descargar"
  onclick={(e) => {
    e.stopPropagation();
    if (!t || t.estado === "error" || t.estado === "cancelado") descargar([cancion]);
  }}
>
  {#if t?.estado === "listo" || t?.estado === "existe"}
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
