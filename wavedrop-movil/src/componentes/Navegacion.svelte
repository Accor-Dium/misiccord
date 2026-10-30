<script>
  import { t } from "../lib/idioma.svelte.js";
  import { activas, irPestana, nav } from "../lib/estado.svelte.js";
  import { jam } from "../lib/jam.svelte.js";
  import Icono from "./Icono.svelte";

  // Abajo en el cel; riel a la izquierda (solo íconos) con el cel acostado; barra lateral con nombres en pantalla ancha.
  const pestanas = [
    { id: "inicio", icono: "inicio", texto: t("Inicio") },
    { id: "biblioteca", icono: "biblioteca", texto: t("Biblioteca") },
    { id: "jams", icono: "jam", texto: t("Jams") },
    { id: "descargas", icono: "descargas", texto: t("Descargas") },
  ];
  const pendientes = $derived(activas());
</script>

<nav class="barra">
  <div class="marca">
    <span class="ondas"><i></i><i></i><i></i><i></i></span>
    <b>Misiccord</b>
  </div>
  {#each pestanas as p}
    <button class="boton" class:activo={nav.pestana === p.id} onclick={() => irPestana(p.id)} aria-label={p.texto}>
      <span class="pastilla"><Icono nombre={p.icono} tam={23} /></span>
      <span class="texto">{p.texto}</span>
      {#if p.id === "descargas" && pendientes}<span class="globo">{pendientes}</span>{/if}
      {#if p.id === "jams" && jam.sala}<span class="globo vivo">●</span>{/if}
    </button>
  {/each}
</nav>

<style>
  .barra {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 30;
    height: calc(64px + var(--seguro-abajo)); padding: 0 8px var(--seguro-abajo);
    display: flex; justify-content: space-around; align-items: center;
    background: linear-gradient(to top, rgba(10, 15, 20, 1) 55%, rgba(10, 15, 20, 0.85));
    backdrop-filter: blur(18px);
  }
  .marca, .texto { display: none; }
  .boton { position: relative; flex: 1; height: 100%; display: grid; place-items: center; color: var(--tenue); }
  .pastilla {
    width: 58px; height: 38px; border-radius: 999px; display: grid; place-items: center;
    transition: background 0.3s var(--curva), color 0.3s;
  }
  .activo { color: var(--texto); }
  .activo .pastilla { background: rgba(34, 211, 238, 0.14); color: var(--cian); }
  .globo {
    position: absolute; top: 9px; left: calc(50% + 8px); min-width: 18px; height: 18px; padding: 0 5px;
    border-radius: 9px; background: var(--cian); color: #04121a; font-size: 11px; font-weight: 800;
    display: grid; place-items: center;
  }
  .globo.vivo { background: transparent; color: var(--verde); font-size: 14px; }

  @media (orientation: landscape) and (max-height: 560px) {
    .barra {
      top: 0; right: auto; width: var(--riel); height: auto;
      padding: var(--seguro-arriba) 0 var(--seguro-abajo) env(safe-area-inset-left, 0px);
      flex-direction: column; justify-content: center; gap: 4px;
      background: var(--panel); border-right: 1px solid var(--borde); backdrop-filter: none;
    }
    .boton { flex: none; width: 100%; height: 64px; }
    .pastilla { width: 52px; height: 36px; }
    .globo { top: 4px; left: calc(50% + 6px); }
  }

  @media (min-width: 900px) and (min-height: 561px) {
    .barra {
      top: 0; right: auto; width: var(--lateral); height: auto; padding: 22px 14px;
      flex-direction: column; justify-content: flex-start; align-items: stretch; gap: 4px;
      background: var(--panel); border-right: 1px solid var(--borde);
    }
    .marca { display: flex; align-items: center; gap: 12px; padding: 4px 12px 24px; }
    .marca b { font-size: 22px; font-weight: 900; letter-spacing: -0.5px; }
    .ondas { display: flex; gap: 3px; align-items: center; height: 26px; }
    .ondas i { width: 4px; border-radius: 2px; background: var(--cian); }
    .ondas i:nth-child(1) { height: 10px; } .ondas i:nth-child(2) { height: 24px; }
    .ondas i:nth-child(3) { height: 16px; } .ondas i:nth-child(4) { height: 8px; }
    .boton { flex: none; height: 48px; display: flex; align-items: center; gap: 6px; padding: 0 6px; border-radius: 12px; }
    .boton:hover { background: var(--tarjeta); color: var(--texto); }
    .activo { background: var(--tarjeta-2); }
    .activo .pastilla { background: none; }
    .pastilla { width: 40px; height: 40px; }
    .texto { display: inline; font-weight: 600; font-size: 15px; }
    .globo { position: static; margin-left: auto; }
  }
</style>
