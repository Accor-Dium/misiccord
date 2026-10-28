<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py } from "./lib/api.js";
  import { nav } from "./lib/estado.svelte.js";
  import { rep } from "./lib/reproductor.svelte.js";
  import Avisos from "./componentes/Avisos.svelte";
  import Hoja from "./componentes/Hoja.svelte";
  import MiniReproductor from "./componentes/MiniReproductor.svelte";
  import Navegacion from "./componentes/Navegacion.svelte";
  import Reproductor from "./componentes/Reproductor.svelte";
  import Album from "./vistas/Album.svelte";
  import Ajustes from "./vistas/Ajustes.svelte";
  import Artista from "./vistas/Artista.svelte";
  import Biblioteca from "./vistas/Biblioteca.svelte";
  import Buscar from "./vistas/Buscar.svelte";
  import Descargas from "./vistas/Descargas.svelte";
  import Inicio from "./vistas/Inicio.svelte";
  import Jams from "./vistas/Jams.svelte";
  import Playlist from "./vistas/Playlist.svelte";

  const vistas = {
    inicio: Inicio, buscar: Buscar, biblioteca: Biblioteca, descargas: Descargas, jams: Jams,
    album: Album, artista: Artista, buscar_artista: Artista, playlist: Playlist, ajustes: Ajustes,
    biblioteca_albumes: Biblioteca,
  };

  let listo = $state(false);
  let error = $state("");
  let principal = $state();
  const entrada = $derived(nav.pila.at(-1));

  onMount(async () => {
    try {
      const r = await py("iniciar");
      rep.fundido = r.ajustes.fundido;
      listo = true;
    } catch (e) {
      error = e.message;
    }
  });

  // Al cambiar de vista: volver a donde estabas (si regresas) o al principio (si entras)
  let anterior = null;
  $effect(() => {
    const e = entrada;
    if (!principal) return;
    if (anterior && anterior !== e) anterior.scroll = principal.scrollTop;
    anterior = e;
    requestAnimationFrame(() => (principal.scrollTop = e.scroll ?? 0));
  });
</script>

{#if !listo}
  <div class="arranque" out:fade={{ duration: 300 }}>
    <div class="logo">
      <span></span><span></span><span></span><span></span><span></span>
    </div>
    <b>WaveDrop</b>
    {#if error}<p class="error">No se pudo iniciar: {error}</p>{/if}
  </div>
{:else}
  <main bind:this={principal} class:con-mini={rep.actual}>
    {#key entrada}
      {@const Vista = vistas[entrada.vista]}
      <Vista e={entrada} />
    {/key}
  </main>
  <MiniReproductor />
  <Navegacion />
  <Reproductor />
  <Hoja />
{/if}
<Avisos />

<style>
  main {
    position: fixed; inset: 0; overflow-y: auto; overflow-x: hidden;
    padding-bottom: calc(var(--nav) + var(--seguro-abajo) + 28px);
    view-transition-name: contenido; scrollbar-width: none;
  }
  main::-webkit-scrollbar { display: none; }
  main.con-mini { padding-bottom: calc(var(--nav) + var(--mini) + var(--seguro-abajo) + 34px); }
  @media (min-width: 900px) {
    main { left: var(--lateral); }
  }
  .arranque { position: fixed; inset: 0; display: grid; place-content: center; justify-items: center; gap: 18px; }
  .arranque b { font-size: 28px; font-weight: 900; letter-spacing: -0.5px; }
  .logo { display: flex; gap: 5px; align-items: center; height: 46px; }
  .logo span { width: 7px; border-radius: 4px; background: var(--cian); animation: ola 1.1s infinite ease-in-out; }
  .logo span:nth-child(2) { animation-delay: -0.9s; }
  .logo span:nth-child(3) { animation-delay: -0.7s; }
  .logo span:nth-child(4) { animation-delay: -0.5s; }
  .logo span:nth-child(5) { animation-delay: -0.3s; }
  @keyframes ola { 0%, 100% { height: 10px; opacity: 0.6; } 50% { height: 46px; opacity: 1; } }
  .error { color: var(--rojo); max-width: 80vw; text-align: center; }
</style>
