<script>
  import { onMount } from "svelte";
  import { alEvento, py } from "../lib/api.js";
  import { alternarMeGusta, atras, descargar, ui } from "../lib/estado.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";

  // Tus Me gusta: descargadas (suenan del archivo) y vistas previas (suenan en línea y se pueden descargar).
  let { e } = $props();
  const canciones = $derived(e.datos ?? []);
  // Las que no tienes y no traen id de YouTube Music no se pueden escuchar (se muestran apagadas)
  const reproducibles = $derived(canciones.filter((c) => c.local || c.id));
  const faltan = $derived(canciones.filter((c) => !c.local && c.id));

  async function cargar() {
    e.datos = (await py("me_gusta")).canciones;
  }
  onMount(() => {
    if (!e.datos) cargar();
    return alEvento("me_gusta", cargar);
  });
  let version = ui.version;
  $effect(() => { if (ui.version !== version) { version = ui.version; cargar(); } });

  function tocar(c) {
    const i = reproducibles.indexOf(c);
    if (i >= 0) reproducir(reproducibles, i, "Me gusta");
  }
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label="Atrás"><Icono nombre="atras" tam={24} /></button>
  </header>
  <div class="cab">
    <div class="tapa"><Icono nombre="corazon" relleno tam={72} /></div>
    <h1>Me gusta</h1>
    <p class="tenue">
      {canciones.length} canciones{#if faltan.length} · {faltan.length} sin descargar{/if}
    </p>
  </div>
  <div class="acciones">
    <button class="pildora clara" disabled={!reproducibles.length} onclick={() => reproducir(reproducibles, 0, "Me gusta")}><Icono nombre="play" relleno tam={20} /> Reproducir</button>
    <button class="pildora oscura" disabled={!reproducibles.length} onclick={() => reproducirAleatorio(reproducibles, "Me gusta")}><Icono nombre="aleatorio" tam={20} /> Aleatorio</button>
  </div>
  {#if faltan.length}
    <button class="pildora cian descargar" onclick={() => descargar(faltan, "Me gusta")}>
      <Icono nombre="descargas" tam={18} /> Descargar {faltan.length === 1 ? "la que falta" : `las ${faltan.length} que faltan`}
    </button>
  {/if}
  {#each canciones as c (c.titulo + "|" + c.artista)}
    <div class:apagada={!c.local && !c.id} title={!c.local && !c.id ? "Ya no está en tu dispositivo y no se encontró en YouTube Music" : null}>
      <FilaCancion cancion={c} alTocar={() => tocar(c)}
        extras={[{ texto: "Quitar de Me gusta", icono: "corazon", accion: () => alternarMeGusta(c) }]} />
    </div>
  {:else}
    <p class="vacio">Toca el <Icono nombre="corazon" tam={16} /> en el reproductor (o “Me gusta” en el menú ⋯ de cualquier canción) y aquí aparecerá, aunque no la hayas descargado.</p>
  {/each}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  .cab { text-align: center; margin-top: 4px; }
  .tapa {
    width: 56%; max-width: 260px; aspect-ratio: 1; margin: 0 auto 18px; display: grid; place-items: center; color: #fff;
    border-radius: 12px; background: linear-gradient(135deg, #ff4d6d, #7c3aed); box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
  }
  h1 { margin: 0; font-size: 26px; font-weight: 800; }
  .cab p { margin: 6px 0 0; }
  .acciones { display: flex; gap: 12px; justify-content: center; margin: 20px 0 12px; }
  .acciones .pildora { flex: 1; max-width: 170px; }
  .descargar { display: flex; margin: 0 auto 12px; justify-content: center; gap: 8px; height: 42px; padding: 0 18px; font-size: 14.5px; }
  /* Se ve apagada y tocarla no hace nada (tocar() la ignora), pero su ⋯ sigue sirviendo para quitarla */
  .apagada { opacity: 0.4; }
  .vacio :global(svg) { vertical-align: -3px; color: #ff4d6d; }
</style>
