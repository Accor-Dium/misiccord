<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py } from "../lib/api.js";
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

  async function cargar() {
    e.datos = await py("biblioteca");
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
    {#if pestana === "playlists"}
      <button class="redondo" onclick={() => (creando = !creando)} aria-label="Nueva playlist"><Icono nombre="agregar" tam={26} /></button>
    {/if}
  </header>
  <div class="chips">
    {#each pestanas as [id, texto]}
      <button class="chip" class:activo={pestana === id} onclick={() => (pestana = id)}>{texto}</button>
    {/each}
  </div>

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
  .nueva { display: flex; gap: 10px; margin: 4px 0 12px; }
  .nueva input { flex: 1; min-width: 0; height: 44px; border-radius: 12px; border: 1px solid var(--borde-fuerte); background: var(--tarjeta); padding: 0 14px; outline: 0; }
</style>
