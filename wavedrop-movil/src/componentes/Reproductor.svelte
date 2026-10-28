<script>
  import { fade, fly } from "svelte/transition";
  import { src, tiempo } from "../lib/api.js";
  import { abrir, cerrarReproductor, descargar, irPestana, mostrarHoja, ui } from "../lib/estado.svelte.js";
  import {
    alternar, alternarAleatorio, anterior, ciclarRepetir, irA, rep, reproducirDeCola, siguiente,
  } from "../lib/reproductor.svelte.js";
  import BotonDescarga from "./BotonDescarga.svelte";
  import Icono from "./Icono.svelte";
  import Letra from "./Letra.svelte";
  import Portada from "./Portada.svelte";

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

  function irAJams() {
    cerrarReproductor();
    setTimeout(() => irPestana("jams"), 250);
  }

  const c = $derived(rep.actual);
  const avance = $derived(rep.dur ? ((buscando ?? rep.pos) / rep.dur) * 100 : 0);

  function tocarInicio(e) {
    if (panel !== "portada") return;
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

  function mas() {
    const ops = [];
    if (!c.ruta) ops.push({ texto: "Descargar", icono: "descargas", accion: () => descargar([c]) });
    ops.push({ texto: `Ir a ${c.artista.split(",")[0]}`, icono: "persona", accion: () => {
      cerrarReproductor();
      setTimeout(() => abrir("buscar_artista", { nombre: c.artista.split(",")[0] }), 250);
    } });
    mostrarHoja({ titulo: c.titulo, subtitulo: c.artista, portada: c.portada, opciones: ops });
  }
</script>

{#if ui.reproductorAbierto && c}
  <div
    class="reproductor"
    role="dialog"
    aria-label="Reproductor"
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
      <button class="redondo" onclick={cerrarReproductor} aria-label="Cerrar"><Icono nombre="abajo" tam={28} /></button>
      <div class="origen">
        <small>REPRODUCIENDO DESDE</small>
        <b class="cortar">{rep.origen || "tu música"}</b>
      </div>
      <button class="redondo" onclick={mas} aria-label="Más opciones"><Icono nombre="mas" tam={26} /></button>
    </header>

    <section class="centro">
      {#if panel === "portada" || ui.amplio}
        <div class="portada" in:fade={{ duration: 250 }}>
          {#key c.portada}
            <div class="tapa" in:fade={{ duration: 350 }}>
              <Portada url={c.portada} radio="14px" sombra />
            </div>
          {/key}
        </div>
      {:else if panel === "letra"}
        <div class="lado" in:fade={{ duration: 250 }}><Letra /></div>
      {:else}
        <div class="lado cola" in:fade={{ duration: 250 }}>
          <h3>A continuación</h3>
          {#each rep.cola as item, i}
            <button class="item" class:actual={i === rep.indice} onclick={() => reproducirDeCola(i)}>
              <Portada url={item.portada} tam="42px" radio="6px" />
              <span class="textos"><b class="cortar">{item.titulo}</b><small class="cortar">{item.artista}</small></span>
            </button>
          {/each}
        </div>
      {/if}
    </section>

    <section class="datos">
      <div class="titulos">
        <h2 class="cortar">{c.titulo}</h2>
        <p class="cortar">{c.artista}</p>
      </div>
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
        {#if !c.ruta}<span class="etiqueta">VISTA PREVIA</span>{/if}
        <span>{tiempo(rep.dur || c.duracion)}</span>
      </div>
    </section>

    <section class="controles">
      <button class="redondo" class:encendido={rep.aleatorio} onclick={alternarAleatorio} aria-label="Aleatorio">
        <Icono nombre="aleatorio" tam={24} />
      </button>
      <button class="redondo grande" onclick={anterior} aria-label="Anterior"><Icono nombre="anterior" relleno tam={34} /></button>
      <button class="play" onclick={alternar} aria-label={rep.sonando ? "Pausar" : "Reproducir"}>
        {#if rep.cargando}<span class="girando"></span>
        {:else}<Icono nombre={rep.sonando ? "pausa" : "play"} relleno tam={36} />{/if}
      </button>
      <button class="redondo grande" onclick={siguiente} aria-label="Siguiente"><Icono nombre="siguiente" relleno tam={34} /></button>
      <button class="redondo" class:encendido={rep.repetir > 0} onclick={ciclarRepetir} aria-label="Repetir">
        <Icono nombre="repetir" tam={24} />
        {#if rep.repetir === 2}<span class="uno">1</span>{/if}
      </button>
    </section>

    <footer>
      <button class="redondo relleno" class:encendido={vista === "cola"} onclick={() => alternarPanel("cola")} aria-label="Cola">
        <Icono nombre="cola" tam={22} />
      </button>
      <button class="redondo relleno" class:encendido={vista === "letra"} onclick={() => alternarPanel("letra")} aria-label="Letra">
        <Icono nombre="letra" tam={22} />
      </button>
      <button class="redondo relleno" onclick={irAJams} aria-label="Jams" title="Escuchar en grupo">
        <Icono nombre="jam" tam={22} />
      </button>
    </footer>

    {#if ui.amplio}
      <!-- En pantalla ancha la letra o la cola siempre están a la derecha -->
      <aside class="derecha">
        <div class="pestanas">
          <button class:activa={lado === "letra"} onclick={() => (lado = "letra")}>Letra</button>
          <button class:activa={lado === "cola"} onclick={() => (lado = "cola")}>A continuación</button>
        </div>
        {#if lado === "letra"}
          <div class="lado" in:fade={{ duration: 250 }}><Letra /></div>
        {:else}
          <div class="lado cola" in:fade={{ duration: 250 }}>
            {#each rep.cola as item, i}
              <button class="item" class:actual={i === rep.indice} onclick={() => reproducirDeCola(i)}>
                <Portada url={item.portada} tam="48px" radio="6px" />
                <span class="textos"><b class="cortar">{item.titulo}</b><small class="cortar">{item.artista}</small></span>
              </button>
            {/each}
          </div>
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
  .portada { width: min(100%, 52vh); display: grid; }
  .portada > * { grid-area: 1 / 1; }
  .lado { width: 100%; height: 100%; }
  .cola { overflow-y: auto; }
  .cola h3 { margin: 0 0 10px; font-size: 18px; }
  .item { width: 100%; display: flex; align-items: center; gap: 12px; padding: 6px 4px; text-align: left; border-radius: 8px; }
  .item.actual b { color: var(--cian); }
  .item .textos { min-width: 0; display: flex; flex-direction: column; }
  .item small { color: rgba(255, 255, 255, 0.6); }
  .datos { display: flex; align-items: center; gap: 12px; }
  .titulos { flex: 1; min-width: 0; }
  h2 { margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.3px; }
  .titulos p { margin: 4px 0 0; font-size: 17px; color: rgba(255, 255, 255, 0.7); }
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
    .centro, .datos, .barra, .controles, footer { grid-column: 1; }
    .centro { margin: 24px 0; }
    .portada { width: 100%; }
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
