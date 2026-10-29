<script>
  import { onMount } from "svelte";
  import { fade, scale } from "svelte/transition";
  import { alEvento, py } from "../lib/api.js";
  import { abrir, aviso, mostrarHoja, ui } from "../lib/estado.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import { aBody } from "../lib/aBody.js";
  import { pedirEliminar } from "../lib/eliminar.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";
  import Tarjeta from "../componentes/Tarjeta.svelte";

  let { e } = $props();
  let pestana = $state(e.pestana ?? (e.vista === "biblioteca_albumes" ? "albumes" : "canciones"));
  $effect(() => { e.pestana = pestana; });
  let creando = $state(false);
  let nombre = $state("");
  const b = $derived(e.datos);

  // Filtro por carpeta de música ("" = todas); se recuerda al volver a esta vista
  let filtro = $state(e.filtro ?? "");
  let pedido = 0;

  async function cargar() {
    const yo = ++pedido;
    const [datos, c] = await Promise.all([py("biblioteca", { carpeta: filtro }), py("carpetas_biblioteca")]);
    if (yo !== pedido) return;
    carpetas = c;
    if (filtro && !c.carpetas.some((x) => x.ruta === filtro)) { // la carpeta filtrada se quitó
      filtro = "";
      e.filtro = "";
      return cargar();
    }
    e.datos = datos;
  }
  function filtrar(ruta) {
    if (ruta === filtro) return;
    filtro = ruta;
    e.filtro = ruta;
    salirSeleccion();
    cargar();
  }
  onMount(() => { if (!e.datos) cargar(); });
  let version = ui.version;
  $effect(() => { if (ui.version !== version) { version = ui.version; cargar(); } });

  async function crear() {
    if (!nombre.trim()) return;
    try {
      await py("crear_playlist", { nombre: nombre.trim() });
      aviso(`Playlist “${nombre.trim()}” creada`, "ok");
      nombre = "";
      creando = false;
      cargar();
    } catch {
      aviso("Ya existe una playlist con ese nombre", "error");
    }
  }

  // ---------- Carpetas de música que ya tienes ----------
  let panelCarpetas = $state(false);
  let carpetas = $state(null);      // { carpetas: [...], android }
  let explorando = $state(null);    // Android: { ruta, padre, carpetas } mientras eliges una carpeta
  let escaneando = $state(false);
  let revisadas = $state(0);

  onMount(() => {
    const quitar = [
      alEvento("escaneo", (d) => { revisadas = d.revisadas; }),
      alEvento("biblioteca", () => { escaneando = false; if (panelCarpetas) cargarCarpetas(); }),
    ];
    return () => quitar.forEach((f) => f());
  });

  async function cargarCarpetas() {
    carpetas = await py("carpetas_biblioteca");
  }
  function abrirPanel() {
    panelCarpetas = true;
    explorando = null;
    cargarCarpetas();
  }
  async function agregarCarpeta(ruta) {
    try {
      carpetas = await py("agregar_carpeta_biblioteca", { ruta });
      explorando = null;
      revisadas = 0;
      escaneando = true;
      aviso("Leyendo tu música…", "ok");
    } catch (err) {
      aviso(err.message, "error");
    }
  }
  async function elegirCarpetaMusica() {
    if (!carpetas.android) {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const ruta = await open({ directory: true, title: "¿Dónde está tu música?" });
      if (ruta) agregarCarpeta(ruta);
      return;
    }
    // Android: leer carpetas públicas pide "Acceso a todos los archivos"
    const { invoke } = await import("@tauri-apps/api/core");
    if (!(await invoke("permiso_archivos", { pedir: false }))) {
      aviso("Activa “Permitir acceso a todos los archivos” para Misiccord y regresa a la app");
      await invoke("permiso_archivos", { pedir: true });
      const alVolver = async () => {
        if (document.visibilityState !== "visible") return;
        document.removeEventListener("visibilitychange", alVolver);
        if (await invoke("permiso_archivos", { pedir: false })) irA();
        else aviso("Sin ese permiso no puedo leer tu música", "error");
      };
      document.addEventListener("visibilitychange", alVolver);
      return;
    }
    irA();
  }
  async function irA(ruta) {
    try {
      explorando = await py("subcarpetas", { ruta });
    } catch (err) {
      aviso(err.message, "error");
    }
  }
  async function quitarCarpeta(c) {
    carpetas = await py("quitar_carpeta_biblioteca", { ruta: c.ruta });
    aviso("Carpeta quitada; tus archivos siguen donde estaban", "ok");
  }
  const nombreCarpeta = (ruta) => ruta.split(/[\\/]/).filter(Boolean).pop() || ruta;

  const pestanas = [["canciones", "Canciones"], ["albumes", "Álbumes"], ["artistas", "Artistas"], ["playlists", "Playlists"]];

  // ---------- Selección múltiple para borrar ----------
  let seleccionando = $state(false);
  let elegidas = $state(new Set());
  $effect(() => { if (pestana !== "canciones") salirSeleccion(); });

  function salirSeleccion() {
    seleccionando = false;
    elegidas = new Set();
  }
  function alternarElegida(id) {
    const s = new Set(elegidas);
    s.has(id) ? s.delete(id) : s.add(id);
    elegidas = s;
  }
  const todas = $derived(b?.canciones.length > 0 && elegidas.size === b.canciones.length);
  function alternarTodas() {
    elegidas = todas ? new Set() : new Set(b.canciones.map((c) => c.db_id));
  }
  function eliminarElegidas() {
    const rutas = new Set(b.canciones.filter((c) => elegidas.has(c.db_id)).map((c) => c.ruta));
    pedirEliminar({
      objetivo: { db_ids: [...elegidas] }, cuantas: elegidas.size,
      titulo: elegidas.size === 1 ? "la canción elegida" : `${elegidas.size} canciones`,
      seBorra: (c) => rutas.has(c.ruta),
      alTerminar: (r) => r && salirSeleccion(),
    });
  }

  function opcionesArtista(a) {
    mostrarHoja({
      titulo: a.nombre, subtitulo: `${a.canciones} canciones descargadas`,
      opciones: [
        { texto: "Reproducir", icono: "play",
          accion: async () => reproducir((await py("artista_local", { nombre: a.nombre })).canciones, 0, a.nombre) },
        { texto: "Ver en YouTube Music", icono: "persona", accion: () => abrir("artista", { nombre: a.nombre }) },
        { texto: "Eliminar todas sus canciones", icono: "basura", peligro: true, accion: () => pedirEliminar({
            objetivo: { artista: a.nombre }, cuantas: a.canciones, titulo: `todo de ${a.nombre}`,
            seBorra: (c) => (c.artista || "").toLowerCase().startsWith(a.nombre.toLowerCase()) }) },
      ],
    });
  }
</script>

<div class="vista">
  <header>
    <h1 class="titulo-vista">Biblioteca</h1>
    <div class="botones">
      <button class="redondo" onclick={abrirPanel} aria-label="Carpetas de música" title="Carpetas de música"><Icono nombre="carpeta" tam={24} /></button>
      {#if pestana === "playlists"}
        <button class="redondo" onclick={() => (creando = !creando)} aria-label="Nueva playlist"><Icono nombre="agregar" tam={26} /></button>
      {/if}
    </div>
  </header>
  {#if escaneando}
    <p class="tenue leyendo">Leyendo tu música… {revisadas ? `${revisadas} canciones revisadas` : ""}</p>
  {/if}
  <div class="chips">
    {#each pestanas as [id, texto]}
      <button class="chip" class:activo={pestana === id} onclick={() => (pestana = id)}>{texto}</button>
    {/each}
  </div>
  {#if carpetas?.carpetas.length > 1}
    <div class="chips carpetas" role="group" aria-label="Filtrar por carpeta">
      <button class="chip" class:activo={!filtro} onclick={() => filtrar("")}>Todas</button>
      {#each carpetas.carpetas as c (c.ruta)}
        <button class="chip" class:activo={filtro === c.ruta} onclick={() => filtrar(c.ruta)} title={c.ruta}>
          <Icono nombre="carpeta" tam={14} /> {nombreCarpeta(c.ruta)} <small>{c.canciones}</small>
        </button>
      {/each}
    </div>
  {/if}

  {#if !b}
    {#each Array(6) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
  {:else if pestana === "canciones"}
    <div in:fade={{ duration: 220 }}>
      {#if b.canciones.length}
        {#if seleccionando}
          <div class="acciones">
            <button class="texto-boton" onclick={alternarTodas}>{todas ? "Quitar todas" : "Elegir todas"}</button>
            <button class="pildora oscura chica" onclick={salirSeleccion}>Listo</button>
          </div>
          {#each b.canciones as c (c.db_id)}
            <button class="fila-eleccion" class:elegida={elegidas.has(c.db_id)} onclick={() => alternarElegida(c.db_id)}>
              <span class="casilla">{#if elegidas.has(c.db_id)}<Icono nombre="check" tam={16} />{/if}</span>
              <Portada url={c.portada} tam="46px" radio="8px" />
              <span class="textos"><b class="cortar">{c.titulo}</b><small class="cortar">{c.artista}</small></span>
            </button>
          {/each}
        {:else}
          <div class="acciones">
            <span class="tenue">{b.canciones.length} canciones</span>
            <div class="botones">
              <button class="redondo" onclick={() => (seleccionando = true)} aria-label="Seleccionar canciones" title="Seleccionar">
                <Icono nombre="seleccionar" tam={22} />
              </button>
              <button class="pildora oscura chica" onclick={() => reproducirAleatorio(b.canciones, "Tu biblioteca")}>
                <Icono nombre="aleatorio" tam={18} /> Aleatorio
              </button>
            </div>
          </div>
          {#each b.canciones as c, i}
            <FilaCancion cancion={c} alTocar={() => reproducir(b.canciones, i, "Tu biblioteca")} />
          {/each}
        {/if}
      {:else}
        <p class="vacio">Aún no tienes canciones descargadas.</p>
      {/if}
    </div>
  {:else if pestana === "albumes"}
    <div class="rejilla" in:fade={{ duration: 220 }}>
      {#each b.albumes as a}
        <Tarjeta portada={a.portada} titulo={a.nombre} subtitulo={a.artista} ancho="100%" alTocar={() => abrir("album", { local: a })} />
      {:else}
        <p class="vacio">Sin álbumes todavía.</p>
      {/each}
    </div>
  {:else if pestana === "artistas"}
    <div in:fade={{ duration: 220 }}>
      {#each b.artistas as a}
        <div class="fila-con-menu">
          <button class="fila-artista" onclick={() => abrir("artista", { nombre: a.nombre })}>
            <span class="avatar"><Icono nombre="persona" tam={22} /></span>
            <span class="textos"><b class="cortar">{a.nombre}</b><small>{a.canciones} canciones</small></span>
          </button>
          <button class="mas" aria-label="Opciones de {a.nombre}" onclick={() => opcionesArtista(a)}><Icono nombre="mas" tam={22} /></button>
        </div>
      {:else}
        <p class="vacio">Sin artistas todavía.</p>
      {/each}
    </div>
  {:else}
    <div in:fade={{ duration: 220 }}>
      {#if creando}
        <form class="nueva" onsubmit={(ev) => { ev.preventDefault(); crear(); }}>
          <input bind:value={nombre} placeholder="Nombre de la playlist" />
          <button class="pildora cian chica">Crear</button>
        </form>
      {/if}
      {#each b.playlists as p}
        <button class="fila-artista" onclick={() => abrir("playlist", { id: p.id, nombre: p.nombre })}>
          <span class="avatar cuadro"><Icono nombre="lista" tam={22} /></span>
          <span class="textos"><b class="cortar">{p.nombre}</b><small>{p.canciones} canciones</small></span>
        </button>
      {:else}
        {#if !creando}<p class="vacio">Crea tu primera playlist con el botón <b>+</b>.</p>{/if}
      {/each}
    </div>
  {/if}
</div>

{#if panelCarpetas}
  <div class="fondo-modal" use:aBody transition:fade={{ duration: 180 }} onclick={() => (panelCarpetas = false)} role="presentation"></div>
  <div class="modal" use:aBody transition:scale={{ duration: 220, start: 0.94 }} role="dialog" aria-label="Carpetas de música">
    <button class="redondo cerrar-modal" onclick={() => (panelCarpetas = false)} aria-label="Cerrar"><Icono nombre="cerrar" tam={22} /></button>
    {#if explorando}
      <h2>Elige tu carpeta de música</h2>
      <p class="tenue ruta-actual">{explorando.ruta}</p>
      <div class="lista-carpetas">
        {#if explorando.padre}
          <button class="fila-carpeta" onclick={() => irA(explorando.padre)}><Icono nombre="atras" tam={20} /><span>Subir</span></button>
        {/if}
        {#each explorando.carpetas as c}
          <button class="fila-carpeta" onclick={() => irA(c.ruta)}><Icono nombre="carpeta" tam={20} /><span class="cortar">{c.nombre}</span></button>
        {:else}
          <p class="tenue">No hay más carpetas aquí.</p>
        {/each}
      </div>
      <button class="pildora cian ancho" onclick={() => agregarCarpeta(explorando.ruta)}>Usar esta carpeta</button>
    {:else}
      <h2>Carpetas de música</h2>
      <p class="tenue">Misiccord escucha estas carpetas, con todas sus subcarpetas, para armar tu biblioteca.</p>
      {#if escaneando}<p class="leyendo">Leyendo… {revisadas ? `${revisadas} canciones` : ""}</p>{/if}
      <div class="lista-carpetas">
        {#each carpetas?.carpetas ?? [] as c (c.ruta)}
          <div class="fila-carpeta quieta">
            <Icono nombre="carpeta" tam={20} />
            <span class="textos">
              <b class="cortar">{nombreCarpeta(c.ruta)}</b>
              <small class="cortar">{c.existe ? `${c.canciones} canciones` : "No se encuentra"}{c.descargas ? " · descargas" : ""}</small>
              <small class="cortar ruta">{c.ruta}</small>
            </span>
            {#if !c.descargas}
              <button class="redondo" onclick={() => quitarCarpeta(c)} aria-label="Quitar {nombreCarpeta(c.ruta)}"><Icono nombre="cerrar" tam={18} /></button>
            {/if}
          </div>
        {/each}
      </div>
      <button class="pildora cian ancho" disabled={!carpetas} onclick={elegirCarpetaMusica}><Icono nombre="agregar" tam={18} /> Agregar carpeta…</button>
    {/if}
  </div>
{/if}

{#if seleccionando}
  <div class="barra-seleccion" use:aBody>
    <b>{elegidas.size === 1 ? "1 elegida" : `${elegidas.size} elegidas`}</b>
    <button class="pildora rojo chica" disabled={!elegidas.size} onclick={eliminarElegidas}>
      <Icono nombre="basura" tam={18} /> Eliminar
    </button>
  </div>
{/if}

<style>
  .vista { padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
  header { display: flex; align-items: center; justify-content: space-between; }
  .chips { display: flex; gap: 8px; margin: var(--margen) calc(-1 * var(--margen)) 10px; padding: 0 var(--margen); overflow-x: auto; scrollbar-width: none; }
  /* Segunda fila de chips (carpetas): más chica para que se note que es un filtro */
  .chips.carpetas { margin-top: -2px; }
  .carpetas .chip { height: 32px; padding: 0 14px; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; background: transparent; border: 1px solid var(--borde-fuerte); }
  .carpetas .chip.activo { background: var(--cian); border-color: var(--cian); color: #04121a; }
  .carpetas .chip small { opacity: 0.65; }
  .rejilla { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 14px; margin-top: 8px; }
  .acciones { display: flex; justify-content: space-between; align-items: center; margin: 6px 0 8px; }
  .chica { height: 38px; padding: 0 16px; font-size: 14px; }
  .fila-artista { width: 100%; display: flex; align-items: center; gap: 14px; padding: 8px 0; text-align: left; }
  .avatar { width: 54px; height: 54px; border-radius: 50%; background: var(--tarjeta-2); display: grid; place-items: center; color: var(--tenue); flex-shrink: 0; }
  .avatar.cuadro { border-radius: 10px; }
  .textos { min-width: 0; display: flex; flex-direction: column; }
  .textos small { color: var(--tenue); }
  .botones { display: flex; align-items: center; gap: 6px; }
  .texto-boton { color: var(--cian); font-weight: 600; padding: 8px 0; }
  .fila-eleccion { width: 100%; display: flex; align-items: center; gap: 12px; padding: 7px 6px; border-radius: 12px; text-align: left; transition: background 0.15s; }
  .fila-eleccion.elegida { background: rgba(34, 211, 238, 0.08); }
  .casilla { width: 24px; height: 24px; border-radius: 7px; border: 2px solid var(--borde-fuerte); display: grid; place-items: center; flex-shrink: 0; color: #04121a; transition: background 0.15s, border-color 0.15s; }
  .elegida .casilla { background: var(--cian); border-color: var(--cian); }
  .fila-eleccion .textos { flex: 1; }
  .fila-con-menu { display: flex; align-items: center; }
  .fila-con-menu .fila-artista { flex: 1; min-width: 0; }
  .mas { width: 40px; height: 44px; display: grid; place-items: center; color: var(--tenue); flex-shrink: 0; }
  /* Va encima del mini reproductor mientras eliges */
  .barra-seleccion {
    position: fixed; z-index: 32; left: 10px; right: 10px; bottom: calc(var(--nav) + var(--seguro-abajo) + 6px);
    height: var(--mini); display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 12px 0 18px;
    border-radius: 18px; background: rgba(28, 42, 53, 0.98); backdrop-filter: blur(22px); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
  }
  .rojo { background: var(--rojo); color: #fff; }
  .rojo:disabled { opacity: 0.4; }
  @media (min-width: 900px) {
    .barra-seleccion { left: calc(var(--lateral) + 16px); right: 16px; bottom: 16px; }
  }
  .leyendo { margin: 6px 0 0; font-size: 13px; color: var(--cian); }
  .fondo-modal { position: fixed; inset: 0; z-index: 300; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); }
  .modal {
    position: fixed; z-index: 301; left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: min(420px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto;
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 24px; padding: 22px 20px 20px;
  }
  .modal h2 { margin: 0 36px 0 0; font-size: 21px; font-weight: 800; }
  .modal p { margin: 6px 0 12px; font-size: 14px; line-height: 1.45; }
  .cerrar-modal { position: absolute; top: 10px; right: 10px; }
  .lista-carpetas { max-height: 46vh; overflow-y: auto; margin-bottom: 14px; }
  .fila-carpeta { width: 100%; display: flex; align-items: center; gap: 12px; padding: 10px 6px; border-radius: 12px; text-align: left; color: var(--tenue); }
  button.fila-carpeta:hover, button.fila-carpeta:active { background: var(--tarjeta-2); }
  .fila-carpeta span:not(.textos) { color: var(--texto, inherit); }
  .fila-carpeta .textos { flex: 1; color: inherit; }
  .fila-carpeta .textos b { color: var(--texto, inherit); }
  .ruta, .ruta-actual { font-size: 12px; overflow-wrap: anywhere; }
  .ancho { width: 100%; justify-content: center; }
  .nueva { display: flex; gap: 10px; margin: 4px 0 12px; }
  .nueva input { flex: 1; min-width: 0; height: 44px; border-radius: 12px; border: 1px solid var(--borde-fuerte); background: var(--tarjeta); padding: 0 14px; outline: 0; }
</style>
