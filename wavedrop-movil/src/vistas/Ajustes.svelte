<script>
  import { onMount } from "svelte";
  import { py } from "../lib/api.js";
  import { atras, aviso } from "../lib/estado.svelte.js";
  import { act, buscarActualizacion, instalarActualizacion, REPO } from "../lib/actualizaciones.svelte.js";
  import { getVersion } from "@tauri-apps/api/app";
  import { aplicarAjustesVideo, rep } from "../lib/reproductor.svelte.js";
  import Icono from "../componentes/Icono.svelte";

  let aj = $state(null);
  let info = $state(null); // carpeta actual, carpetas sugeridas y si es Android

  onMount(async () => {
    act.actual ||= await getVersion();
    info = await py("ajustes");
    aj = info.ajustes;
  });

  async function guardar(cambios) {
    aj = { ...aj, ...cambios };
    if ("fundido" in cambios) rep.fundido = cambios.fundido;
    if ("video_ver" in cambios || "video_descargar" in cambios) aplicarAjustesVideo(aj);
    try {
      info = await py("guardar_ajustes", cambios);
      aj = info.ajustes;
      if ("carpeta" in cambios) aviso("Las descargas nuevas se guardarán ahí", "ok");
    } catch (e) {
      aviso(e.message, "error");
      info = await py("ajustes");
      aj = info.ajustes;
    }
  }

  /** Android: las carpetas públicas (Música) piden "Acceso a todos los archivos" antes de poder escribir. */
  async function elegirCarpetaAndroid(c) {
    const publica = c.ruta.startsWith("/storage/emulated/0/") && !c.ruta.includes("/Android/data/");
    if (!publica) return guardar({ carpeta: c.ruta });
    const { invoke } = await import("@tauri-apps/api/core");
    if (await invoke("permiso_archivos", { pedir: false })) return guardar({ carpeta: c.ruta });
    aviso("Activa “Permitir acceso a todos los archivos” para Misiccord y regresa a la app");
    await invoke("permiso_archivos", { pedir: true });
    // Al volver de Ajustes de Android se revisa otra vez y, si ya hay permiso, se aplica la carpeta
    const alVolver = async () => {
      if (document.visibilityState !== "visible") return;
      document.removeEventListener("visibilitychange", alVolver);
      if (await invoke("permiso_archivos", { pedir: false })) guardar({ carpeta: c.ruta });
      else aviso("Sin ese permiso las canciones se quedan en la carpeta de la app", "error");
    };
    document.addEventListener("visibilitychange", alVolver);
  }

  async function elegirCarpeta() {
    // Escritorio: el selector de carpetas del sistema
    const { open } = await import("@tauri-apps/plugin-dialog");
    const ruta = await open({ directory: true, title: "¿Dónde guardar las canciones?", defaultPath: info.carpeta_actual });
    if (ruta) guardar({ carpeta: ruta });
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
      <h2>Video</h2>
      <label class="opcion">
        <div class="texto">
          <b>Ver el video con la canción</b>
          <small>Pone un interruptor sobre la carátula del reproductor. El video va mudo y sigue al audio; si no lo tienes descargado se transmite de YouTube y gasta datos</small>
        </div>
        <input type="checkbox" class="interruptor" checked={aj.video_ver} onchange={(e) => guardar({ video_ver: e.target.checked })} />
      </label>
      <label class="opcion">
        <div class="texto">
          <b>Descargar también el video</b>
          <small>Al descargar una canción se guarda su videoclip (mp4, hasta 720p) en la misma carpeta. Ocupa bastante más espacio</small>
        </div>
        <input type="checkbox" class="interruptor" checked={aj.video_descargar} onchange={(e) => guardar({ video_descargar: e.target.checked })} />
      </label>
    </section>

    <section>
      <h2>Descargas</h2>
      <div class="opcion">
        <div class="texto">
          <b><Icono nombre="descargas" tam={18} /> Carpeta de descargas</b>
          <small class="ruta">{info.carpeta_actual}</small>
        </div>
        {#if !info.android}
          <button class="pildora oscura chica" onclick={elegirCarpeta}>Cambiar…</button>
        {/if}
      </div>
      {#if info.android}
        {#each info.carpetas as c}
          <button class="eleccion" class:activa={info.carpeta_actual === c.ruta} onclick={() => elegirCarpetaAndroid(c)}>
            <span class="radio"></span>
            <span class="texto"><b>{c.nombre}</b><small>{c.detalle}</small></span>
          </button>
        {/each}
      {:else if info.carpeta_actual !== info.carpetas[0]?.ruta}
        <button class="restaurar" onclick={() => guardar({ carpeta: info.carpetas[0].ruta })}>Volver a la carpeta por defecto</button>
      {/if}
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
      <div class="opcion">
        <div class="texto">
          <b>Misiccord {act.actual || ""}</b>
          <small>
            {#if act.estado === "buscando"}Buscando versiones nuevas…
            {:else if act.estado === "al_dia"}Tienes la versión más reciente
            {:else if act.estado === "disponible"}Hay una versión nueva: {act.version}
            {:else if act.estado === "descargando"}Descargando la actualización… {act.pct}%
            {:else if act.estado === "instalando"}Instalando…
            {:else if act.estado === "error"}No se pudo revisar: {act.error}
            {:else}Las versiones nuevas se publican en github.com/{REPO}{/if}
          </small>
        </div>
        {#if act.estado === "disponible"}
          <button class="pildora cian chica" onclick={instalarActualizacion}>Actualizar</button>
        {:else}
          <button class="pildora oscura chica" disabled={act.estado === "buscando" || act.estado === "descargando"}
            onclick={() => buscarActualizacion({ avisar: false, manual: true })}>Buscar</button>
        {/if}
      </div>
      {#if act.estado === "descargando"}
        <div class="progreso"><div style:width="{act.pct}%"></div></div>
      {/if}
      <p class="tenue acerca">
        Misiccord · música de YouTube Music, recomendaciones y letras de LRCLIB, datos de MusicBrainz.
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
  .ruta { font-family: ui-monospace, monospace; font-size: 12.5px; word-break: break-all; }
  .chica { height: 40px; padding: 0 16px; font-size: 14px; flex-shrink: 0; }
  .eleccion { width: 100%; display: flex; align-items: center; gap: 14px; padding: 12px 4px; text-align: left; border-bottom: 1px solid var(--borde); }
  .radio { width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--borde-fuerte); flex-shrink: 0; transition: border 0.2s; }
  .eleccion.activa .radio { border: 7px solid var(--cian); }
  .restaurar { color: var(--cian); font-weight: 600; padding: 10px 0; }
  .progreso { height: 4px; border-radius: 2px; background: var(--borde-fuerte); overflow: hidden; margin: 4px 0 10px; }
  .progreso div { height: 100%; background: var(--cian); transition: width 0.4s var(--curva); }
</style>
