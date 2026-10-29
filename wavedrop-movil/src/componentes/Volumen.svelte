<script>
  import { t } from "../lib/idioma.svelte.js";
  import { alternarSilencio, ponerVolumen, rep, VOLUMEN_MAX } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";

  // Control de volumen: toca la bocina para silenciar; arrastra o usa la rueda del mouse para subir y bajar.
  // Va de 0 a 200 %: la marca a la mitad es 100 % (el archivo tal cual); lo de arriba se pinta de otro color.
  let { ancho = "100%", claro = false } = $props();
  const valor = $derived(rep.silencio ? 0 : rep.volumen);
</script>

<div class="volumen" style:width={ancho} class:claro>
  <button class="bocina" onclick={alternarSilencio} aria-label={rep.silencio ? t("Quitar silencio") : t("Silenciar")}>
    <Icono nombre={valor === 0 ? "silencio" : "volumen"} tam={20} />
  </button>
  <div class="barra">
    <input
      type="range" min="0" max={VOLUMEN_MAX} step="0.01" value={valor} aria-label={t("Volumen")}
      aria-valuetext="{Math.round(valor * 100)}%"
      style:--avance="{(valor / VOLUMEN_MAX) * 100}%"
      class:refuerzo={valor > 1}
      oninput={(e) => ponerVolumen(+e.target.value)}
      onwheel={(e) => { e.preventDefault(); ponerVolumen(rep.volumen + (e.deltaY < 0 ? 0.05 : -0.05)); }}
    />
    <span class="marca" aria-hidden="true"></span>
  </div>
  <span class="pct" class:alto={valor > 1}>{Math.round(valor * 100)}%</span>
</div>

<style>
  .volumen { display: flex; align-items: center; gap: 10px; color: var(--tenue); --lleno: var(--cian); --vacio: rgba(255, 255, 255, 0.2); }
  .claro { color: rgba(255, 255, 255, 0.75); --lleno: #fff; --vacio: rgba(255, 255, 255, 0.25); }
  .bocina { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 50%; flex-shrink: 0; }
  .bocina:active { background: rgba(255, 255, 255, 0.08); }
  .barra { flex: 1; min-width: 60px; position: relative; display: flex; }
  /* El input va encima de la marca: el pulgar la tapa al pasar por 100 % */
  input { position: relative; z-index: 1; flex: 1; width: 100%; height: 24px; -webkit-appearance: none; appearance: none; background: transparent; margin: 0; }
  input::-webkit-slider-runnable-track {
    height: 4px; border-radius: 2px;
    background: linear-gradient(to right, var(--lleno) var(--avance), var(--vacio) var(--avance));
  }
  /* Arriba de 100 %: hasta la mitad el color normal y de ahí al pulgar en ámbar (es refuerzo, puede saturar) */
  input.refuerzo::-webkit-slider-runnable-track {
    background: linear-gradient(to right, var(--lleno) 50%, #fbbf24 50%, #fbbf24 var(--avance), var(--vacio) var(--avance));
  }
  input::-webkit-slider-thumb {
    -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #fff; margin-top: -5px;
  }
  .marca {
    position: absolute; left: 50%; top: 50%; width: 2px; height: 10px; margin: -5px 0 0 -1px; border-radius: 1px;
    background: currentColor; opacity: 0.55; pointer-events: none;
  }
  .pct { width: 40px; text-align: right; font-size: 12px; font-variant-numeric: tabular-nums; }
  .pct.alto { color: #fbbf24; }
</style>
