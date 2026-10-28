<script>
  import { fly } from "svelte/transition";
  import { abrirReproductor } from "../lib/estado.svelte.js";
  import { alternar, rep, siguiente } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Reproductor flotante sobre la barra de navegación; tócalo para verlo en grande.
  const avance = $derived(rep.dur ? (rep.pos / rep.dur) * 100 : 0);
</script>

{#if rep.actual}
  <div class="mini" transition:fly={{ y: 90, duration: 350 }}>
    <button class="info" onclick={abrirReproductor}>
      <Portada url={rep.actual.portada} tam="46px" radio="8px" />
      <div class="textos">
        <b class="cortar">{rep.actual.titulo}</b>
        <small class="cortar">{rep.actual.artista}{#if !rep.actual.ruta} · vista previa{/if}</small>
      </div>
    </button>
    <button class="redondo play" onclick={alternar} aria-label={rep.sonando ? "Pausar" : "Reproducir"}>
      {#if rep.cargando}<span class="girando"></span>
      {:else}<Icono nombre={rep.sonando ? "pausa" : "play"} relleno tam={22} />{/if}
    </button>
    <button class="redondo" onclick={siguiente} aria-label="Siguiente"><Icono nombre="siguiente" relleno tam={22} /></button>
    <div class="avance" style:width="{avance}%"></div>
  </div>
{/if}

<style>
  .mini {
    position: fixed; z-index: 31; left: 10px; right: 10px;
    bottom: calc(var(--nav) + var(--seguro-abajo) + 6px); height: var(--mini);
    display: flex; align-items: center; gap: 6px; padding: 0 8px 0 10px; border-radius: 18px;
    background: rgba(28, 42, 53, 0.92); backdrop-filter: blur(22px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45); overflow: hidden;
  }
  .info { flex: 1; min-width: 0; display: flex; align-items: center; gap: 12px; text-align: left; height: 100%; }
  .textos { min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .textos b { font-size: 15px; font-weight: 700; }
  .textos small { color: var(--tenue); font-size: 13px; }
  .play { background: var(--texto); color: #04121a; width: 46px; height: 46px; }
  .avance { position: absolute; left: 0; bottom: 0; height: 2px; background: var(--cian); transition: width 0.3s linear; }
  @media (min-width: 900px) {
    .mini { left: calc(var(--lateral) + 16px); right: 16px; bottom: 16px; padding: 0 16px; gap: 12px; }
    .info { gap: 16px; }
    .textos b { font-size: 16px; }
  }
  .girando {
    width: 20px; height: 20px; border-radius: 50%; border: 2.5px solid rgba(4, 18, 26, 0.25);
    border-top-color: #04121a; animation: giro 0.8s linear infinite;
  }
  @keyframes giro { to { transform: rotate(360deg); } }
</style>
