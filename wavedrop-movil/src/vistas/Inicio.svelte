<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { alEvento, py } from "../lib/api.js";
  import { abrir, ui } from "../lib/estado.svelte.js";
  import { reproducir } from "../lib/reproductor.svelte.js";
  import Buscador from "../componentes/Buscador.svelte";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Tarjeta from "../componentes/Tarjeta.svelte";

  let { e } = $props(); // entrada de la pila: guarda los datos para volver al instante

  let pestana = $state(e.pestana ?? "para_ti");
  $effect(() => { e.pestana = pestana; });

  async function cargar() {
    const r = await py("inicio");
    e.datos = { ...r, secciones: r.secciones ?? e.datos?.secciones ?? null };
  }

  onMount(() => {
    if (!e.datos) cargar();
    const quitar = alEvento("recomendaciones", ({ secciones }) => {
      e.datos = { ...(e.datos ?? {}), secciones };
    });
    return quitar;
  });

  // Recargar lo local cuando cambia la biblioteca (descargas nuevas, escaneo)
  let version = ui.version;
  $effect(() => {
    if (ui.version !== version) {
      version = ui.version;
      cargar();
    }
  });

  function actualizar() {
    e.datos = { ...(e.datos ?? {}), secciones: null };
    py("recomendaciones");
  }

  const d = $derived(e.datos);
  let buscandoAlgo = $state(false);

  // Las primeras recomendaciones se dejan listas para que suenen en cuanto las toques
  $effect(() => {
    const ids = (d?.secciones?.[0]?.canciones ?? []).filter((c) => !c.ruta).slice(0, 4).map((c) => c.id);
    if (ids.length) py("precargar", { ids }).catch(() => {});
  });
</script>

<div class="vista">
  <header>
    <h1 class="titulo-vista">Inicio</h1>
    <button class="redondo" onclick={() => abrir("ajustes")} aria-label="Ajustes"><Icono nombre="ajustes" tam={24} /></button>
  </header>

  <Buscador {e} bind:activo={buscandoAlgo} />

  {#if !buscandoAlgo}
  <div class="chips">
    <button class="chip" class:activo={pestana === "para_ti"} onclick={() => (pestana = "para_ti")}>Para ti</button>
    <button class="chip" class:activo={pestana === "tu_musica"} onclick={() => (pestana = "tu_musica")}>Tu música</button>
  </div>

  {#if pestana === "para_ti"}
    <div in:fade={{ duration: 220 }}>
      {#if !d || d.secciones === null}
        <div class="titulo-seccion">Buscando recomendaciones…</div>
        <div class="rejilla">
          {#each Array(4) as _}<div class="cargando-bloque" style="aspect-ratio:1"></div>{/each}
        </div>
      {:else if !d.secciones.length}
        <p class="vacio">Descarga o escucha algunas canciones y aquí aparecerán recomendaciones para ti.</p>
      {:else}
        {#each d.secciones as s, k}
          <div class="titulo-seccion">
            <span>{s.titulo}</span>
            {#if k === 0}<button onclick={actualizar}><small>Actualizar</small></button>{/if}
          </div>
          {#if s.artistas?.length}
            <div class="carrusel">
              {#each s.artistas as a}
                <Tarjeta portada={a.miniatura} titulo={a.nombre} redonda icono="persona" ancho="var(--artista)"
                  alTocar={() => abrir("artista", { id: a.browse_id, nombre: a.nombre })} />
              {/each}
            </div>
          {:else if k === 0}
            <!-- La primera sección en rejilla grande, como portada de la app -->
            <div class="rejilla">
              {#each s.canciones.slice(0, 4) as c, i}
                <Tarjeta portada={c.portada} titulo={c.titulo} subtitulo={c.artista} ancho="100%" icono="nota"
                  alTocar={() => reproducir(s.canciones, i, s.titulo)} />
              {/each}
            </div>
            {#if s.canciones.length > 4}
              <div class="carrusel" style="margin-top:18px">
                {#each s.canciones.slice(4) as c, i}
                  <Tarjeta portada={c.portada} titulo={c.titulo} subtitulo={c.artista} icono="nota"
                    alTocar={() => reproducir(s.canciones, i + 4, s.titulo)} />
                {/each}
              </div>
            {/if}
          {:else}
            <div class="carrusel">
              {#each s.canciones as c, i}
                <Tarjeta portada={c.portada} titulo={c.titulo} subtitulo={c.artista} icono="nota"
                  alTocar={() => reproducir(s.canciones, i, s.titulo)} />
              {/each}
            </div>
          {/if}
        {/each}
      {/if}
    </div>
  {:else}
    <div in:fade={{ duration: 220 }}>
      {#if d && !d.total}
        <p class="vacio">Todavía no tienes canciones. Búscalas arriba y descárgalas.</p>
      {/if}
      {#if d?.recientes?.length}
        <div class="titulo-seccion">Escuchado recientemente</div>
        <div class="carrusel">
          {#each d.recientes as c, i}
            <Tarjeta portada={c.portada} titulo={c.titulo} subtitulo={c.artista} icono="nota"
              alTocar={() => reproducir(d.recientes, i, "Escuchado recientemente")} />
          {/each}
        </div>
      {/if}
      {#if d?.mas_escuchadas?.length}
        <div class="titulo-seccion">Lo que más escuchas</div>
        {#each d.mas_escuchadas.slice(0, 6) as c, i}
          <FilaCancion cancion={c} alTocar={() => reproducir(d.mas_escuchadas, i, "Lo que más escuchas")} />
        {/each}
      {/if}
      {#if d?.albumes?.length}
        <div class="titulo-seccion">Tus álbumes <button onclick={() => abrir("biblioteca_albumes")}><small>Ver todos</small></button></div>
        <div class="carrusel">
          {#each d.albumes as a}
            <Tarjeta portada={a.portada} titulo={a.nombre} subtitulo={a.artista}
              alTocar={() => abrir("album", { local: a })} />
          {/each}
        </div>
      {/if}
    </div>
  {/if}
  {/if}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
  header { display: flex; align-items: center; justify-content: space-between; }
  .chips { display: flex; gap: 10px; margin: var(--margen) 0 4px; }
  .rejilla { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 14px; }
</style>
