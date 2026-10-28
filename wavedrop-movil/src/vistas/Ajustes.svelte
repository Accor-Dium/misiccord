<script>
  import { onMount } from "svelte";
  import { py } from "../lib/api.js";
  import { atras } from "../lib/estado.svelte.js";
  import { rep } from "../lib/reproductor.svelte.js";
  import Icono from "../componentes/Icono.svelte";

  let aj = $state(null);
  let info = $state(null);

  onMount(async () => {
    aj = (await py("ajustes")).ajustes;
  });

  async function guardar(cambios) {
    aj = { ...aj, ...cambios };
    if ("fundido" in cambios) rep.fundido = cambios.fundido;
    aj = (await py("guardar_ajustes", cambios)).ajustes;
  }
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label="Atrás"><Icono nombre="atras" tam={24} /></button>
    <h1>Ajustes</h1>
  </header>

  {#if aj}
    <section>
      <h2>Reproducción</h2>
      <div class="opcion">
        <div class="texto">
          <b><Icono nombre="fundido" tam={18} /> Fundido entre canciones</b>
          <small>{aj.fundido ? `${aj.fundido} s: la siguiente entra mientras la actual se desvanece` : "Sin fundido: una canción tras otra"}</small>
        </div>
        <span class="valor">{aj.fundido} s</span>
      </div>
      <input class="deslizador" type="range" min="0" max="12" step="1" value={aj.fundido}
        style:--avance="{(aj.fundido / 12) * 100}%"
        oninput={(e) => (aj.fundido = +e.target.value)} onchange={(e) => guardar({ fundido: +e.target.value })} />
    </section>

    <section>
      <h2>Descargas</h2>
      <label class="opcion">
        <div class="texto">
          <b>Completar datos con MusicBrainz</b>
          <small>Álbum, año, número de pista y portada oficiales</small>
        </div>
        <input type="checkbox" class="interruptor" checked={aj.musicbrainz} onchange={(e) => guardar({ musicbrainz: e.target.checked })} />
      </label>
      <label class="opcion">
        <div class="texto">
          <b>Carpetas por artista</b>
          <small>Si lo apagas, cada playlist va en su propia carpeta</small>
        </div>
        <input type="checkbox" class="interruptor" checked={aj.por_artista} onchange={(e) => guardar({ por_artista: e.target.checked })} />
      </label>
      <div class="opcion">
        <div class="texto">
          <b>Descargas simultáneas</b>
          <small>Se aplica al reiniciar la app</small>
        </div>
        <div class="segmentos">
          {#each [1, 2, 3, 4] as n}
            <button class:activo={aj.descargas_simultaneas === n} onclick={() => guardar({ descargas_simultaneas: n })}>{n}</button>
          {/each}
        </div>
      </div>
    </section>

    <section>
      <h2>Acerca de</h2>
      <p class="tenue acerca">
        WaveDrop · música de YouTube Music, recomendaciones y letras de LRCLIB, datos de MusicBrainz.
        Descarga solo contenido que tengas permiso de guardar.
      </p>
    </section>
  {/if}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  header { display: flex; align-items: center; gap: 12px; }
  h1 { margin: 0; font-size: 24px; font-weight: 800; }
  section { margin-top: 26px; }
  h2 { font-size: 13px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--cian); margin: 0 0 8px; }
  .opcion { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 0; border-bottom: 1px solid var(--borde); }
  .texto { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .texto b { display: flex; align-items: center; gap: 8px; font-weight: 600; }
  .texto small { color: var(--tenue); line-height: 1.4; }
  .valor { font-weight: 800; color: var(--cian); font-variant-numeric: tabular-nums; }
  .deslizador { width: 100%; -webkit-appearance: none; appearance: none; background: transparent; height: 30px; }
  .deslizador::-webkit-slider-runnable-track { height: 5px; border-radius: 3px; background: linear-gradient(to right, var(--cian) var(--avance), var(--borde-fuerte) var(--avance)); }
  .deslizador::-webkit-slider-thumb { -webkit-appearance: none; width: 22px; height: 22px; border-radius: 50%; background: #fff; margin-top: -8.5px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4); }
  .interruptor { -webkit-appearance: none; appearance: none; width: 50px; height: 30px; border-radius: 15px; background: var(--borde-fuerte); position: relative; flex-shrink: 0; transition: background 0.25s; }
  .interruptor::after { content: ""; position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; border-radius: 50%; background: #fff; transition: transform 0.25s var(--curva); }
  .interruptor:checked { background: var(--cian); }
  .interruptor:checked::after { transform: translateX(20px); }
  .segmentos { display: flex; gap: 6px; }
  .segmentos button { width: 38px; height: 38px; border-radius: 10px; background: var(--tarjeta-2); font-weight: 700; }
  .segmentos .activo { background: var(--cian); color: #04121a; }
  .acerca { line-height: 1.5; font-size: 14px; }
</style>
