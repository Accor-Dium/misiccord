<script>
  import { src } from "../lib/api.js";
  import Icono from "./Icono.svelte";

  // Portada con aparición suave y un icono si no hay imagen.
  let { url = null, tam = "100%", radio = "10px", redonda = false, icono = "nota", sombra = false } = $props();
  let cargada = $state(false);
  let fallo = $state(false);
  const imagen = $derived(src(url));
  $effect(() => {
    imagen;
    cargada = false;
    fallo = false;
  });
</script>

<div
  class="portada"
  class:sombra
  style:width={tam}
  style:border-radius={redonda ? "50%" : radio}
>
  {#if imagen && !fallo}
    <img src={imagen} alt="" loading="lazy" class:cargada onload={() => (cargada = true)} onerror={() => (fallo = true)} />
  {/if}
  {#if !imagen || fallo || !cargada}
    <div class="sin"><Icono nombre={icono} tam={28} /></div>
  {/if}
</div>

<style>
  .portada {
    position: relative; aspect-ratio: 1; overflow: hidden; flex-shrink: 0;
    background: var(--tarjeta-2); color: var(--tenue);
  }
  .sombra { box-shadow: 0 18px 50px rgba(0, 0, 0, 0.55); }
  img {
    position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
    opacity: 0; transition: opacity 0.35s var(--curva); z-index: 1;
  }
  img.cargada { opacity: 1; }
  .sin { position: absolute; inset: 0; display: grid; place-items: center; }
</style>
