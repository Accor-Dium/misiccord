<script>
  import { tiempo } from "../lib/api.js";
  import { t } from "../lib/idioma.svelte.js";
  import { agregarAlJam, puedoAgregar } from "../lib/jam.svelte.js";
  import { mantener } from "../lib/mantener.js";
  import { menuCancion } from "../lib/menuCancion.js";
  import { rep } from "../lib/reproductor.svelte.js";
  import BotonDescarga from "./BotonDescarga.svelte";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Una canción en una lista. Toca para reproducir; "⋯" o dejarla presionada abre el menú (lib/menuCancion.js).
  let { cancion, numero = null, alTocar, sinPortada = false, extras = [] } = $props();
  const sonando = $derived(rep.actual && rep.actual.titulo === cancion.titulo && rep.actual.artista === cancion.artista);
  const opciones = () => menuCancion(cancion, extras);
</script>

<div class="fila" class:sonando role="button" tabindex="0" onclick={alTocar} onkeydown={(e) => e.key === "Enter" && alTocar?.()}
  use:mantener={opciones}>
  {#if numero !== null}
    <span class="numero">{#if sonando}<span class="barras"><i></i><i></i><i></i></span>{:else}{numero}{/if}</span>
  {/if}
  {#if !sinPortada}
    <Portada url={cancion.portada} tam="50px" radio="8px" />
  {/if}
  <div class="textos">
    <b class="cortar">{cancion.titulo}</b>
    <small class="cortar">{cancion.artista}{#if cancion.album && sinPortada === false} · {cancion.album}{/if}</small>
  </div>
  {#if cancion.duracion}<span class="dur">{tiempo(cancion.duracion)}</span>{/if}
  {#if puedoAgregar()}
    <button class="al-jam" aria-label={t("Agregar al jam")} title={t("Agregar al jam")}
      onclick={(e) => { e.stopPropagation(); agregarAlJam(cancion); }}>
      <Icono nombre="jam" tam={20} />
    </button>
  {:else if !cancion.local}<BotonDescarga {cancion} />{/if}
  <button class="mas" aria-label={t("Más opciones")} onclick={(e) => { e.stopPropagation(); opciones(); }}>
    <Icono nombre="mas" tam={22} />
  </button>
</div>

<style>
  .fila {
    display: flex; align-items: center; gap: 12px; padding: 7px 0; border-radius: 10px;
    transition: background 0.2s; cursor: pointer;
  }
  .fila:active { background: rgba(255, 255, 255, 0.05); }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .textos b { font-weight: 600; font-size: 15.5px; }
  .textos small { color: var(--tenue); font-size: 13.5px; }
  .sonando b { color: var(--cian); }
  .numero { width: 26px; text-align: center; color: var(--tenue); font-variant-numeric: tabular-nums; flex-shrink: 0; }
  .dur { color: var(--tenue); font-size: 13px; font-variant-numeric: tabular-nums; }
  .al-jam { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; color: var(--cian); background: rgba(34, 211, 238, 0.1); flex-shrink: 0; }
  .al-jam:active { transform: scale(0.9); }
  .mas { width: 36px; height: 40px; display: grid; place-items: center; color: var(--tenue); }
  .barras { display: inline-flex; gap: 2px; align-items: flex-end; height: 14px; }
  .barras i { width: 3px; background: var(--cian); border-radius: 2px; animation: eq 0.9s infinite ease-in-out; }
  .barras i:nth-child(2) { animation-delay: -0.3s; }
  .barras i:nth-child(3) { animation-delay: -0.6s; }
  @keyframes eq { 0%, 100% { height: 4px; } 50% { height: 14px; } }
</style>
