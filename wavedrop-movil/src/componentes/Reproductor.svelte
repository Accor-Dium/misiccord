<script>
  import { onMount } from "svelte";
  import { fade, fly } from "svelte/transition";
  import { alEvento, py, src, tiempo } from "../lib/api.js";
  import { abrir, abrirAlbumDe, alternarMeGusta, aviso, cerrarReproductor, descargar, irPestana, mostrarHoja, ui, verInfo } from "../lib/estado.svelte.js";
  import {
    alternar, alternarAleatorio, alternarVideo, anterior, ciclarRepetir, irA, montarVideo, rep, siguiente,
  } from "../lib/reproductor.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import { menuCancion } from "../lib/menuCancion.js";
  import BotonDescarga from "./BotonDescarga.svelte";
  import Cola from "./Cola.svelte";
  import Ecualizador from "./Ecualizador.svelte";
  import Icono from "./Icono.svelte";
  import Letra from "./Letra.svelte";
  import Marquesina from "./Marquesina.svelte";
  import Visualizador from "./Visualizador.svelte";
  import Portada from "./Portada.svelte";
  import Volumen from "./Volumen.svelte";

  // Reproductor a pantalla completa. Fondo: la portada difuminada. Desliza hacia abajo para cerrarlo.
  let panel = $state("portada"); // "portada" | "letra" | "cola"
  let arrastre = $state(0);
  let inicioY = $state(null);
  let buscando = $state(null); // segundos mientras arrastras la barra

  let lado = $state("letra"); // panel derecho en pantalla ancha
  const vista = $derived(ui.amplio ? lado : panel);

  function alternarPanel(cual) {
    if (ui.amplio) lado = cual;
    else panel = panel === cual ? "portada" : cual;
  }

  // ---------- Me gusta ----------
  let gusta = $state(false);
  $effect(() => {
    const actual = c;
    if (!actual) return;
    py("me_gusta_es", { titulo: actual.titulo, artista: actual.artista })
      .then((r) => { if (c === actual) gusta = r.gusta; })
      .catch(() => {});
  });
  // Si lo cambias desde otro lado (el ⋯ de una lista) mientras suena, el corazón se entera
  onMount(() => alEvento("me_gusta", (d) => {
    if (c && d.titulo === c.titulo && d.artista === c.artista) gusta = d.gusta;
  }));
  async function tocarMeGusta() {
    gusta = !gusta; // al instante; si falla se regresa
    const r = await alternarMeGusta(c);
    if (r === null) gusta = !gusta;
  }

  // Tocar el artista o el álbum lleva a su vista (se cierra el reproductor primero, como en "Ir a…")
  function verArtista(nombre) {
    cerrarReproductor();
    setTimeout(() => abrir("artista", { nombre }), 250);
  }
  function verAlbum() {
    const actual = c;
    cerrarReproductor();
    setTimeout(() => abrirAlbumDe(actual), 250);
  }

  function irAJams() {
    cerrarReproductor();
    setTimeout(() => irPestana("jams"), 250);
  }

  const c = $derived(rep.actual);
  const avance = $derived(rep.dur ? ((buscando ?? rep.pos) / rep.dur) * 100 : 0);

  function tocarInicio(e) {
    if (panel !== "portada") return;
    // Arrastrar la barra de avance o el volumen no cierra el reproductor
    if (e.target.closest?.(".barra, .vol, input[type=range]")) return;
    inicioY = e.touches[0].clientY;
  }
  function tocarMover(e) {
    if (inicioY === null) return;
    arrastre = Math.max(0, e.touches[0].clientY - inicioY);
  }
  function tocarFin() {
    if (inicioY === null) return;
    inicioY = null;
    if (arrastre > 140) cerrarReproductor();
    arrastre = 0;
  }

  // Qué se ve sobre el título: la carátula, un visualizador o el video
  let verVisual = $state(leerVisual());
  function leerVisual() {
    try { return localStorage.getItem("misiccord_ver_visual") === "1"; } catch { return false; }
  }
  const vistaCentro = $derived(verVisual ? "visual" : rep.videoDisponible && rep.verVideo ? "video" : "cancion");
  function elegirVista(v) {
    if ((v === "video") !== rep.verVideo) alternarVideo();
    verVisual = v === "visual";
    try { localStorage.setItem("misiccord_ver_visual", verVisual ? "1" : "0"); } catch {}
  }

  // El video reemplaza a la carátula mientras carga o suena; si no hay video para esta canción se queda la carátula
  const enVideo = $derived(rep.videoDisponible && rep.verVideo && rep.videoEstado !== "error");

  async function bajarVideo() {
    try {
      const r = await py("descargar_video", { ruta: c.ruta, titulo: c.titulo, artista: c.artista, duracion: c.duracion });
      if (r.estado === "existe") aviso(t("Ya tienes el video de esta canción"));
      else aviso(t("Descargando el video…"), "ok");
    } catch (e) {
      aviso(e.message, "error");
    }
  }

  // El mismo menú que al dejar presionada una canción, más bajar el video si aplica
  function mas() {
    const extras = c.ruta && rep.videoDescargar ? [{ texto: t("Descargar video"), icono: "video", accion: bajarVideo }] : [];
    menuCancion(c, extras);
  }
</script>

{#if ui.reproductorAbierto && c}
  <div
    class="reproductor"
    role="dialog"
    aria-label={t("Reproductor")}
    style:transform="translateY({arrastre}px)"
    style:transition={inicioY === null ? "transform 0.35s var(--curva)" : "none"}
    transition:fly={{ y: 900, duration: 420, opacity: 1 }}
    ontouchstart={tocarInicio}
    ontouchmove={tocarMover}
    ontouchend={tocarFin}
  >
    <!-- Fondo ambiental con la portada difuminada -->
    {#key c.portada}
      <div class="ambiente" transition:fade={{ duration: 600 }} style:background-image={c.portada ? `url("${src(c.portada)}")` : "none"}></div>
    {/key}
    <div class="velo"></div>

    <header>
      <button class="redondo" onclick={cerrarReproductor} aria-label={t("Cerrar")}><Icono nombre="abajo" tam={28} /></button>
      <div class="origen">
        <small>{t("REPRODUCIENDO DESDE")}</small>
        <b class="cortar">{rep.origen || t("tu música")}</b>
      </div>
      <button class="redondo" onclick={mas} aria-label={t("Más opciones")}><Icono nombre="mas" tam={26} /></button>
    </header>

    <section class="centro">
      {#if panel === "portada" || ui.amplio}
        <div class="pila" in:fade={{ duration: 250 }}>
          <div class="selector" role="tablist" aria-label={t("Qué ver")}>
            <button role="tab" aria-selected={vistaCentro === "cancion"} class:activo={vistaCentro === "cancion"} onclick={() => elegirVista("cancion")}>{t("Canción")}</button>
            <button role="tab" aria-selected={vistaCentro === "visual"} class:activo={vistaCentro === "visual"} onclick={() => elegirVista("visual")}>{t("Visual")}</button>
            {#if rep.videoDisponible}
              <button role="tab" aria-selected={vistaCentro === "video"} class:activo={vistaCentro === "video"} onclick={() => elegirVista("video")}>{t("Video")}</button>
            {/if}
          </div>
          {#if vistaCentro === "video" && rep.videoEstado === "error"}<small class="sin-video">{t("Esta canción no tiene video")}</small>{/if}
          <div class="portada">
            {#if vistaCentro === "visual"}
              <Visualizador />
            {:else if !enVideo}
              {#key c.portada}
                <div class="tapa" in:fade={{ duration: 350 }}>
                  <Portada url={c.portada} radio="14px" sombra />
                </div>
              {/key}
            {/if}
            <div class="caja-video" class:visible={enVideo} use:montarVideo>
              {#if rep.videoEstado === "cargando"}<span class="girando claro"></span>{/if}
            </div>
          </div>
        </div>
      {:else if panel === "letra"}
        <div class="lado" in:fade={{ duration: 250 }}><Letra /></div>
      {:else if panel === "eq"}
        <div class="lado" in:fade={{ duration: 250 }}><Ecualizador /></div>
      {:else}
        <div class="lado" in:fade={{ duration: 250 }}><Cola /></div>
      {/if}
    </section>

    <section class="datos">
      <div class="titulos">
        {#key c}
          <h2><Marquesina>{c.titulo}</Marquesina></h2>
          <p>
            <Marquesina>
              {#each c.artista.split(", ").filter(Boolean) as nombre, i}{#if i}{", "}{/if}<button class="enlace" onclick={() => verArtista(nombre)}>{nombre}</button>{/each}
              {#if c.album}{" · "}<button class="enlace" onclick={verAlbum}>{c.album}</button>{/if}
            </Marquesina>
          </p>
        {/key}
      </div>
      <button class="redondo corazon" class:gusta onclick={tocarMeGusta} aria-pressed={gusta}
        aria-label={gusta ? t("Quitar de Me gusta") : t("Me gusta")} title={gusta ? t("Quitar de Me gusta") : t("Me gusta")}>
        <Icono nombre="corazon" relleno={gusta} tam={26} />
      </button>
      {#if !c.local}<BotonDescarga cancion={c} />{/if}
    </section>

    <section class="barra">
      <input
        type="range" min="0" max={rep.dur || 1} step="0.1" value={buscando ?? rep.pos}
        style:--avance="{avance}%"
        oninput={(e) => (buscando = +e.target.value)}
        onchange={(e) => { irA(+e.target.value); buscando = null; }}
      />
      <div class="tiempos">
        <span>{tiempo(buscando ?? rep.pos)}</span>
        {#if !c.ruta}<span class="etiqueta">{t("VISTA PREVIA")}</span>{/if}
        <span>{tiempo(rep.dur || c.duracion)}</span>
      </div>
    </section>

    <section class="controles">
      <button class="redondo" class:encendido={rep.aleatorio} onclick={alternarAleatorio} aria-label={t("Aleatorio")}>
        <Icono nombre="aleatorio" tam={24} />
      </button>
      <button class="redondo grande" onclick={anterior} aria-label={t("Anterior")}><Icono nombre="anterior" relleno tam={34} /></button>
      <button class="play" onclick={alternar} aria-label={rep.sonando ? t("Pausar") : t("Reproducir")}>
        {#if rep.cargando}<span class="girando"></span>
        {:else}<Icono nombre={rep.sonando ? "pausa" : "play"} relleno tam={36} />{/if}
      </button>
      <button class="redondo grande" onclick={siguiente} aria-label={t("Siguiente")}><Icono nombre="siguiente" relleno tam={34} /></button>
      <button class="redondo" class:encendido={rep.repetir > 0} onclick={ciclarRepetir} aria-label={t("Repetir")}>
        <Icono nombre="repetir" tam={24} />
        {#if rep.repetir === 2}<span class="uno">1</span>{/if}
      </button>
    </section>

    <div class="vol"><Volumen claro /></div>

    <footer>
      <button class="redondo relleno" class:encendido={vista === "cola"} onclick={() => alternarPanel("cola")} aria-label={t("Cola")}>
        <Icono nombre="cola" tam={22} />
      </button>
      <button class="redondo relleno" class:encendido={vista === "letra"} onclick={() => alternarPanel("letra")} aria-label={t("Letra")}>
        <Icono nombre="comillas" tam={22} />
      </button>
      <button class="redondo relleno" class:encendido={vista === "eq" || rep.eq.activo} onclick={() => alternarPanel("eq")} aria-label={t("Ecualizador")} title={t("Ecualizador")}>
        <Icono nombre="ecualizador" tam={22} />
      </button>
      <button class="redondo relleno" onclick={irAJams} aria-label={t("Jams")} title={t("Escuchar en grupo")}>
        <Icono nombre="jam" tam={22} />
      </button>
    </footer>

    {#if ui.amplio}
      <!-- En pantalla ancha la letra o la cola siempre están a la derecha -->
      <aside class="derecha">
        <div class="pestanas">
          <button class:activa={lado === "letra"} onclick={() => (lado = "letra")}>{t("Letra")}</button>
          <button class:activa={lado === "cola"} onclick={() => (lado = "cola")}>{t("A continuación")}</button>
          <button class:activa={lado === "eq"} onclick={() => (lado = "eq")}>{t("Ecualizador")}</button>
        </div>
        {#if lado === "letra"}
          <div class="lado" in:fade={{ duration: 250 }}><Letra /></div>
        {:else if lado === "eq"}
          <div class="lado" in:fade={{ duration: 250 }}><Ecualizador /></div>
        {:else}
          <div class="lado" in:fade={{ duration: 250 }}><Cola /></div>
        {/if}
      </aside>
    {/if}
  </div>
{/if}

<style>
  .reproductor {
    position: fixed; inset: 0; z-index: 50; display: flex; flex-direction: column;
    padding: calc(var(--seguro-arriba) + 10px) 22px calc(var(--seguro-abajo) + 18px);
    background: #0b1117; overflow: hidden; touch-action: pan-x;
  }
  .ambiente {
    position: absolute; inset: -15%; background-size: cover; background-position: center;
    filter: blur(70px) saturate(1.5) brightness(0.6); transform: scale(1.2); z-index: -2;
  }
  .velo {
    position: absolute; inset: 0; z-index: -1;
    background: linear-gradient(to bottom, rgba(10, 15, 20, 0.15), rgba(10, 15, 20, 0.35) 45%, rgba(10, 15, 20, 0.85));
  }
  header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .origen { min-width: 0; text-align: center; display: flex; flex-direction: column; }
  .origen small { font-size: 11px; letter-spacing: 1.5px; color: rgba(255, 255, 255, 0.65); }
  .origen b { font-size: 14px; }
  .centro { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; margin: 18px 0; }
  .pila { width: min(100%, 50vh); display: flex; flex-direction: column; gap: 12px; }
  .portada { width: 100%; display: grid; }
  .portada > * { grid-area: 1 / 1; }
  /* Selector "Canción | Video" como el de YouTube Music: la opción activa va en blanco */
  .selector { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; align-self: center; width: min(100%, 300px); padding: 4px; border-radius: 999px; background: rgba(255, 255, 255, 0.14); backdrop-filter: blur(10px); }
  .selector button { height: 34px; border-radius: 999px; font-size: 14px; font-weight: 600; color: rgba(255, 255, 255, 0.75); transition: background 0.25s, color 0.25s; }
  .selector button.activo { background: #fff; color: #04121a; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3); }
  .sin-video { align-self: center; color: rgba(255, 255, 255, 0.6); }
  /* El <video> lo pone reproductor.svelte.js (use:montarVideo); el sonido sigue siendo el del audio */
  .caja-video { display: none; align-self: center; aspect-ratio: 16 / 9; position: relative; background: #000; border-radius: 14px; overflow: hidden; place-items: center; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); }
  .caja-video.visible { display: grid; }
  .caja-video :global(video) { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }
  .caja-video .girando { border-color: rgba(255, 255, 255, 0.25); border-top-color: #fff; position: relative; }
  .lado { width: 100%; height: 100%; }
  .datos { display: flex; align-items: center; gap: 12px; }
  .titulos { flex: 1; min-width: 0; }
  h2 { margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.3px; }
  .titulos p { margin: 4px 0 0; font-size: 17px; color: rgba(255, 255, 255, 0.7); }
  .corazon { color: rgba(255, 255, 255, 0.75); flex-shrink: 0; transition: transform 0.2s var(--curva), color 0.2s; }
  .corazon.gusta { color: #ff4d6d; }
  .corazon:active { transform: scale(0.85); }
  .enlace { display: inline; padding: 0; font: inherit; color: inherit; }
  .enlace:hover { color: #fff; text-decoration: underline; }
  .barra { margin-top: 18px; }
  input[type="range"] {
    width: 100%; height: 22px; background: transparent; -webkit-appearance: none; appearance: none; margin: 0;
  }
  input[type="range"]::-webkit-slider-runnable-track {
    height: 4px; border-radius: 2px;
    background: linear-gradient(to right, #fff var(--avance), rgba(255, 255, 255, 0.25) var(--avance));
  }
  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #fff; margin-top: -5px;
  }
  .tiempos { display: flex; justify-content: space-between; font-size: 13px; color: rgba(255, 255, 255, 0.7); font-variant-numeric: tabular-nums; }
  .etiqueta { letter-spacing: 1.5px; color: var(--cian); font-weight: 700; font-size: 12px; }
  .controles { display: flex; align-items: center; justify-content: space-between; margin: 16px 0 22px; }
  .grande { width: 56px; height: 56px; }
  .play {
    width: 76px; height: 76px; border-radius: 50%; background: #fff; color: #04121a; display: grid; place-items: center;
    transition: transform 0.15s var(--curva);
  }
  .play:active { transform: scale(0.92); }
  .encendido { color: var(--cian); }
  .redondo { position: relative; }
  .uno { position: absolute; top: 7px; right: 6px; font-size: 10px; font-weight: 800; color: var(--cian); }
  footer { display: flex; justify-content: space-between; }
  .vol { margin: -6px 0 14px; }
  .apagado { opacity: 0.4; }
  .girando {
    width: 30px; height: 30px; border-radius: 50%; border: 3px solid rgba(4, 18, 26, 0.2);
    border-top-color: #04121a; animation: giro 0.8s linear infinite;
  }
  @keyframes giro { to { transform: rotate(360deg); } }

  .derecha { display: none; }
  @media (min-width: 900px) {
    /* Dos columnas: portada y controles a la izquierda; letra o cola a la derecha */
    .reproductor {
      display: grid; grid-template-columns: minmax(360px, 440px) 1fr; column-gap: 64px;
      grid-template-rows: auto 1fr auto auto auto auto; padding: 26px 56px 30px;
    }
    header { grid-column: 1 / -1; }
    .centro, .datos, .barra, .controles, .vol, footer { grid-column: 1; }
    .reproductor { grid-template-rows: auto 1fr auto auto auto auto auto; }
    .derecha { grid-row: 2 / span 6; }
    .centro { margin: 24px 0; }
    /* La carátula cabe en lo que queda de alto (título, barra y controles van abajo): en ventanas bajitas se achica */
    .pila { width: min(100%, max(180px, calc(100vh - 470px))); }
    footer { justify-content: center; gap: 28px; }
    .derecha {
      display: flex; flex-direction: column; grid-column: 2; grid-row: 2 / span 5; min-height: 0;
      background: rgba(10, 15, 20, 0.35); border-radius: 20px; padding: 18px 26px; backdrop-filter: blur(10px);
    }
    .pestanas { display: flex; gap: 8px; margin-bottom: 8px; }
    .pestanas button { padding: 8px 16px; border-radius: 999px; font-weight: 700; color: rgba(255, 255, 255, 0.6); }
    .pestanas .activa { background: rgba(255, 255, 255, 0.12); color: #fff; }
    .derecha .lado { flex: 1; min-height: 0; }
  }
</style>
