<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py } from "./lib/api.js";
  import { revisarAlIniciar } from "./lib/actualizaciones.svelte.js";
  import { revisarResumen } from "./lib/resumen.js";
  import { escucharEnlaces } from "./lib/enlaces.svelte.js";
  import { aplicarAjustesLetra, aplicarCaratulas, nav } from "./lib/estado.svelte.js";
  import { idioma, t } from "./lib/idioma.svelte.js";
  import { jam } from "./lib/jam.svelte.js";
  import "./lib/medios.svelte.js"; // notificación, pantalla bloqueada, relojes y teclas multimedia
  import "./lib/carrusel.js"; // carruseles con mouse: arrastrar y flechas
  import { aplicarAjustesVideo, aplicarEcualizador, rep } from "./lib/reproductor.svelte.js";
  import { aplicarAjusteBurbuja } from "./lib/escritorio.svelte.js";
  import Avisos from "./componentes/Avisos.svelte";
  import Hoja from "./componentes/Hoja.svelte";
  import CompletarDatos from "./componentes/CompletarDatos.svelte";
  import Resumen from "./componentes/Resumen.svelte";
  import InfoCancion from "./componentes/InfoCancion.svelte";
  import MiniReproductor from "./componentes/MiniReproductor.svelte";
  import Navegacion from "./componentes/Navegacion.svelte";
  import Reproductor from "./componentes/Reproductor.svelte";
  import Album from "./vistas/Album.svelte";
  import Ajustes from "./vistas/Ajustes.svelte";
  import Artista from "./vistas/Artista.svelte";
  import Biblioteca from "./vistas/Biblioteca.svelte";
  import Descargas from "./vistas/Descargas.svelte";
  import Estadisticas from "./vistas/Estadisticas.svelte";
  import Genero from "./vistas/Genero.svelte";
  import Explorar from "./vistas/Explorar.svelte";
  import MeGusta from "./vistas/MeGusta.svelte";
  import Inicio from "./vistas/Inicio.svelte";
  import Jams from "./vistas/Jams.svelte";
  import Playlist from "./vistas/Playlist.svelte";

  const vistas = {
    inicio: Inicio, biblioteca: Biblioteca, descargas: Descargas, jams: Jams,
    album: Album, artista: Artista, buscar_artista: Artista, playlist: Playlist, ajustes: Ajustes,
    biblioteca_albumes: Biblioteca, estadisticas: Estadisticas, me_gusta: MeGusta, genero: Genero, explorar: Explorar,
  };

  let listo = $state(false);
  let error = $state("");
  let principal = $state();
  const entrada = $derived(nav.pila.at(-1));

  onMount(async () => {
    try {
      const r = await py("iniciar", { idioma: idioma.actual });
      rep.fundido = r.ajustes.fundido;
      aplicarAjustesVideo(r.ajustes);
      aplicarAjustesLetra(r.ajustes);
      aplicarCaratulas(r.ajustes.caratulas);
      aplicarEcualizador(r.ajustes.eq_activo, r.ajustes.eq_bandas, r.ajustes.eq_mono);
      aplicarAjusteBurbuja(r.ajustes.burbuja);
      listo = true;
      revisarAlIniciar();
      revisarResumen();
      setInterval(revisarResumen, 3600000); // por si la app se queda abierta y cambia el día
      escucharEnlaces(); // links de jam con los que se abre la app
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
    <b>Misiccord</b>
    {#if error}<p class="error">{t("No se pudo iniciar: {error}", { error })}</p>{/if}
  </div>
{:else}
  <main bind:this={principal} class:con-mini={rep.actual || jam.sala}>
    {#key entrada}
      {@const Vista = vistas[entrada.vista]}
      <Vista e={entrada} />
    {/key}
  </main>
  <MiniReproductor />
  <Navegacion />
  <Reproductor />
  <Hoja />
  <InfoCancion />
  <CompletarDatos />
  <Resumen />
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
  /* Cel acostado: a la derecha del riel de pestañas y lejos de la muesca del otro lado */
  @media (orientation: landscape) and (max-height: 560px) {
    main { left: var(--riel); padding-right: env(safe-area-inset-right, 0px); }
  }
  @media (min-width: 900px) and (min-height: 561px) {
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
