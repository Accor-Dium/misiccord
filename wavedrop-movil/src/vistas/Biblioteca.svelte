<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { abrir, aviso, ui } from "../lib/estado.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
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
        <div class="acciones">
          <span class="tenue">{b.canciones.length} canciones</span>
          <button class="pildora oscura chica" onclick={() => reproducirAleatorio(b.canciones, "Tu biblioteca")}>
            <Icono nombre="aleatorio" tam={18} /> Aleatorio
          </button>
        </div>
        {#each b.canciones as c, i}
          <FilaCancion cancion={c} alTocar={() => reproducir(b.canciones, i, "Tu biblioteca")} />
        {/each}
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
        <button class="fila-artista" onclick={() => abrir("artista", { nombre: a.nombre })}>
          <span class="avatar"><Icono nombre="persona" tam={22} /></span>
          <span class="textos"><b class="cortar">{a.nombre}</b><small>{a.canciones} canciones</small></span>
        </button>
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

<style>
  .vista { padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
  header { display: flex; align-items: center; justify-content: space-between; }
  .chips { display: flex; gap: 8px; margin: var(--margen) calc(-1 * var(--margen)) 10px; padding: 0 var(--margen); overflow-x: auto; scrollbar-width: none; }
  .rejilla { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 14px; margin-top: 8px; }
  .acciones { display: flex; justify-content: space-between; align-items: center; margin: 6px 0 8px; }
  .chica { height: 38px; padding: 0 16px; font-size: 14px; }
  .fila-artista { width: 100%; display: flex; align-items: center; gap: 14px; padding: 8px 0; text-align: left; }
  .avatar { width: 54px; height: 54px; border-radius: 50%; background: var(--tarjeta-2); display: grid; place-items: center; color: var(--tenue); flex-shrink: 0; }
  .avatar.cuadro { border-radius: 10px; }
  .textos { min-width: 0; display: flex; flex-direction: column; }
  .textos small { color: var(--tenue); }
  .nueva { display: flex; gap: 10px; margin: 4px 0 12px; }
  .nueva input { flex: 1; min-width: 0; height: 44px; border-radius: 12px; border: 1px solid var(--borde-fuerte); background: var(--tarjeta); padding: 0 14px; outline: 0; }
</style>
