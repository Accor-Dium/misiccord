<script>
  import { py } from "../lib/api.js";
  import { aviso } from "../lib/estado.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import { aplicarEcualizador, convertirBandas, frecuenciasEq, NUM_BANDAS, PRESETS_EQ, rep } from "../lib/reproductor.svelte.js";

  // Panel del ecualizador, junto a la letra y la cola del reproductor. Lo que mueves suena al instante y se guarda al soltar.
  const bandas = $derived(rep.eq.bandas);
  const frecuencias = $derived(frecuenciasEq(bandas.length));
  const presetActual = $derived(PRESETS_EQ.find(([, p]) => convertirBandas(p, bandas.length).every((v, i) => v === bandas[i]))?.[0]);
  const etiqueta = (f) => (f >= 1000 ? `${Math.round(f / 100) / 10}k` : String(Math.round(f)));

  function guardar() {
    const { activo, bandas: b, mono } = rep.eq;
    py("guardar_ajustes", { eq_activo: activo, eq_bandas: b, eq_mono: mono }).catch((e) => aviso(e.message, "error"));
  }
  function aplicar(cambios) {
    const { activo, bandas: b, mono } = { ...rep.eq, ...cambios };
    aplicarEcualizador(activo, b, mono);
    guardar();
  }
  function moverBanda(i, valor) {
    const b = [...rep.eq.bandas];
    b[i] = valor;
    aplicarEcualizador(rep.eq.activo, b, rep.eq.mono);
  }
</script>

<div class="eq">
  <label class="fila">
    <b>{t("Ecualizador")}</b>
    <input type="checkbox" class="interruptor" checked={rep.eq.activo} onchange={(e) => aplicar({ activo: e.target.checked })} aria-label={t("Ecualizador")} />
  </label>

  <div class="fila">
    <span>{t("Sonido")}</span>
    <div class="segmentos" role="group" aria-label={t("Sonido")}>
      <button class:activo={!rep.eq.mono} onclick={() => aplicar({ mono: false })}>{t("Estéreo")}</button>
      <button class:activo={rep.eq.mono} onclick={() => aplicar({ mono: true })}>{t("Mono")}</button>
    </div>
  </div>

  <div class="fila">
    <span>{t("Bandas")}</span>
    <div class="segmentos" role="group" aria-label={t("Bandas")}>
      {#each NUM_BANDAS as n}
        <button class:activo={bandas.length === n} onclick={() => aplicar({ bandas: convertirBandas(bandas, n) })}>{n}</button>
      {/each}
    </div>
  </div>

  <div class="ajustable" class:apagado={!rep.eq.activo}>
    <div class="presets">
      {#each PRESETS_EQ as [nombre, curva]}
        <button class:activo={presetActual === nombre} onclick={() => aplicar({ bandas: convertirBandas(curva, bandas.length) })}>{t(nombre)}</button>
      {/each}
    </div>
    <div class="bandas" class:muchas={bandas.length > 10}>
      {#each frecuencias as f, i}
        <label class="banda">
          <span class="db">{bandas[i] > 0 ? "+" : ""}{bandas[i]}</span>
          <input type="range" min="-12" max="12" step="1" value={bandas[i]} aria-label="{etiqueta(f)} Hz" disabled={!rep.eq.activo}
            oninput={(e) => moverBanda(i, +e.target.value)} onchange={guardar} />
          <small>{etiqueta(f)}</small>
        </label>
      {/each}
    </div>
  </div>
</div>

<style>
  .eq { height: 100%; overflow-y: auto; scrollbar-width: none; display: flex; flex-direction: column; gap: 12px; touch-action: pan-y; }
  .eq::-webkit-scrollbar { display: none; }
  .fila { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 15px; }
  .fila span { color: rgba(255, 255, 255, 0.7); }
  .interruptor { -webkit-appearance: none; appearance: none; width: 46px; height: 28px; border-radius: 14px; background: rgba(255, 255, 255, 0.2); position: relative; flex-shrink: 0; transition: background 0.25s; }
  .interruptor::after { content: ""; position: absolute; top: 3px; left: 3px; width: 22px; height: 22px; border-radius: 50%; background: #fff; transition: transform 0.25s var(--curva); }
  .interruptor:checked { background: var(--cian); }
  .interruptor:checked::after { transform: translateX(18px); }
  .segmentos { display: flex; padding: 3px; border-radius: 999px; background: rgba(255, 255, 255, 0.12); }
  .segmentos button { min-width: 42px; height: 30px; padding: 0 12px; border-radius: 999px; font-size: 13.5px; font-weight: 700; color: rgba(255, 255, 255, 0.72); }
  .segmentos .activo { background: #fff; color: #04121a; }
  .ajustable { transition: opacity 0.2s; }
  .ajustable.apagado { opacity: 0.4; }
  .presets { display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; padding-bottom: 6px; touch-action: pan-x pan-y; }
  .presets::-webkit-scrollbar { display: none; }
  .presets button { height: 32px; padding: 0 13px; border-radius: 999px; font-size: 13px; font-weight: 600; background: rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.78); flex-shrink: 0; }
  .presets .activo { background: var(--cian); color: #04121a; }
  /* Con 15 o 31 bandas no caben: se recorren de lado */
  .bandas { display: flex; justify-content: space-between; gap: 4px; padding-top: 10px; overflow-x: auto; scrollbar-width: none; touch-action: pan-x; }
  .bandas::-webkit-scrollbar { display: none; }
  .banda { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1 0 34px; min-width: 34px; }
  .muchas .banda { flex: 0 0 38px; }
  .db { font-size: 11.5px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--cian); min-height: 1em; }
  .banda small { color: rgba(255, 255, 255, 0.6); font-size: 11px; white-space: nowrap; }
  /* Deslizadores verticales (Chromium 124+, como WebView2 y el WebView de Android actuales) */
  .banda input { writing-mode: vertical-lr; direction: rtl; height: 150px; width: 28px; accent-color: var(--cian); touch-action: none; }
</style>
