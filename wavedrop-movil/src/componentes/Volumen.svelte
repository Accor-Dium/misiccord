<script>
  import { alternarSilencio, ponerVolumen, rep } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";

  // Control de volumen: toca la bocina para silenciar; arrastra o usa la rueda del mouse para subir y bajar.
  let { ancho = "100%", claro = false } = $props();
  const valor = $derived(rep.silencio ? 0 : rep.volumen);
</script>

<div class="volumen" style:width={ancho} class:claro>
  <button class="bocina" onclick={alternarSilencio} aria-label={rep.silencio ? "Quitar silencio" : "Silenciar"}>
    <Icono nombre={valor === 0 ? "silencio" : "volumen"} tam={20} />
  </button>
  <input
    type="range" min="0" max="1" step="0.01" value={valor} aria-label="Volumen"
    style:--avance="{valor * 100}%"
    oninput={(e) => ponerVolumen(+e.target.value)}
    onwheel={(e) => { e.preventDefault(); ponerVolumen(rep.volumen + (e.deltaY < 0 ? 0.05 : -0.05)); }}
  />
  <span class="pct">{Math.round(valor * 100)}%</span>
</div>

<style>
  .volumen { display: flex; align-items: center; gap: 10px; color: var(--tenue); }
  .claro { color: rgba(255, 255, 255, 0.75); }
  .bocina { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 50%; flex-shrink: 0; }
  .bocina:active { background: rgba(255, 255, 255, 0.08); }
  input { flex: 1; min-width: 60px; height: 24px; -webkit-appearance: none; appearance: none; background: transparent; margin: 0; }
  input::-webkit-slider-runnable-track {
    height: 4px; border-radius: 2px;
    background: linear-gradient(to right, var(--cian) var(--avance), rgba(255, 255, 255, 0.2) var(--avance));
  }
  .claro input::-webkit-slider-runnable-track {
    background: linear-gradient(to right, #fff var(--avance), rgba(255, 255, 255, 0.25) var(--avance));
  }
  input::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #fff; margin-top: -5px; }
  .pct { width: 38px; text-align: right; font-size: 12px; font-variant-numeric: tabular-nums; }
</style>
