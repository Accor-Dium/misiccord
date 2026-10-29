<script>
  import { fade } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { abrir, aviso, descargarLink } from "../lib/estado.svelte.js";
  import { reproducir } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Tarjeta from "../componentes/Tarjeta.svelte";

  let { e } = $props();
  let q = $state(e.q ?? "");
  let tipo = $state(e.tipo ?? "todo");
  let buscando = $state(false);
  const r = $derived(e.datos);
  const esLink = $derived(/^https?:\/\//.test(q.trim()));

  async function buscar() {
    const texto = q.trim();
    if (!texto || esLink) return;
    buscando = true;
    e.q = texto;
    e.tipo = tipo;
    try {
      e.datos = await py("buscar", { q: texto, tipo });
    } catch (err) {
      aviso("No se pudo buscar. ¿Hay conexión a internet?", "error");
    } finally {
      buscando = false;
    }
  }

  function cambiarTipo(t) {
    tipo = t;
    if (q.trim()) buscar();
  }

  const tipos = [["todo", "Todo"], ["canciones", "Canciones"], ["albumes", "Álbumes"], ["artistas", "Artistas"]];
</script>

<div class="vista">
  <h1 class="titulo-vista">Buscar</h1>
  <form class="caja" onsubmit={(ev) => { ev.preventDefault(); buscar(); }}>
    <Icono nombre={esLink ? "link" : "buscar"} tam={20} />
    <input bind:value={q} placeholder="Canción, artista, álbum o link de playlist" enterkeyhint="search" />
    {#if q}<button type="button" onclick={() => { q = ""; e.datos = null; }} aria-label="Borrar"><Icono nombre="cerrar" tam={18} /></button>{/if}
  </form>

  {#if esLink}
    <div class="link" in:fade>
      <p>¿Descargar todas las canciones de este link? Funciona con playlists y álbumes de YouTube, YT Music, Spotify y SoundCloud.</p>
      <button class="pildora cian" onclick={() => descargarLink(q.trim()).then(() => (q = "")).catch(() => aviso("No pude leer ese link", "error"))}>
        <Icono nombre="descargas" tam={20} /> Descargar playlist
      </button>
    </div>
  {:else}
    <div class="chips">
      {#each tipos as [id, texto]}
        <button class="chip" class:activo={tipo === id} onclick={() => cambiarTipo(id)}>{texto}</button>
      {/each}
    </div>

    {#if buscando}
      {#each Array(6) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
    {:else if r}
      <div in:fade={{ duration: 220 }}>
        {#if r.artistas?.length}
          {#if tipo === "todo"}<div class="titulo-seccion">Artistas</div>{/if}
          <div class={tipo === "todo" ? "carrusel" : "rejilla"}>
            {#each r.artistas as a}
              <Tarjeta portada={a.miniatura} titulo={a.nombre} redonda icono="persona" ancho={tipo === "todo" ? "var(--artista)" : "100%"}
                alTocar={() => abrir("artista", { id: a.browse_id, nombre: a.nombre })} />
            {/each}
          </div>
        {/if}
        {#if r.canciones?.length}
          {#if tipo === "todo"}<div class="titulo-seccion">Canciones</div>{/if}
          {#each r.canciones as c, i}
            <FilaCancion cancion={c} alTocar={() => reproducir(r.canciones, i, `Búsqueda “${e.q}”`)} />
          {/each}
        {/if}
        {#if r.albumes?.length}
          {#if tipo === "todo"}<div class="titulo-seccion">Álbumes</div>{/if}
          <div class={tipo === "todo" ? "carrusel" : "rejilla"}>
            {#each r.albumes as a}
              <Tarjeta portada={a.miniatura} titulo={a.titulo} subtitulo={[a.tipo, a.anio].filter(Boolean).join(" · ")}
                ancho={tipo === "todo" ? "148px" : "100%"} alTocar={() => abrir("album", { id: a.browse_id })} />
            {/each}
          </div>
        {/if}
        {#if !r.canciones?.length && !r.albumes?.length && !r.artistas?.length}
          <p class="vacio">Sin resultados para “{e.q}”.</p>
        {/if}
      </div>
    {:else}
      <p class="vacio">Busca en todo YouTube Music. Toca una canción para escucharla al momento y descárgala si te gusta.</p>
    {/if}
  {/if}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
  .caja {
    position: sticky; top: calc(var(--seguro-arriba) + 6px); z-index: 5; margin-top: 16px;
    display: flex; align-items: center; gap: 10px; height: 50px; padding: 0 14px; border-radius: 14px;
    background: var(--texto); color: #04121a;
  }
  .caja input { flex: 1; min-width: 0; height: 100%; border: 0; outline: 0; background: transparent; color: #04121a; font-size: 16px; }
  .caja input::placeholder { color: #5b6b78; }
  .chips { display: flex; gap: 8px; margin: 16px calc(-1 * var(--margen)) 4px; padding: 0 var(--margen); overflow-x: auto; scrollbar-width: none; }
  .rejilla { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 14px; margin-top: 16px; }
  .link { margin-top: 20px; padding: 18px; border-radius: var(--radio); background: var(--tarjeta); }
  .link p { margin: 0 0 14px; color: var(--tenue); line-height: 1.5; }
</style>
