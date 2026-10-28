<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py, src } from "../lib/api.js";
  import { abrir, atras, aviso, descargar, descargarLink, ui } from "../lib/estado.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";

  // Álbum de YouTube Music (e.id) o de tu biblioteca (e.local).
  let { e } = $props();
  const a = $derived(e.datos);

  async function cargar() {
    try {
      if (e.local) {
        const r = await py("album_local", { nombre: e.local.nombre, artista: e.local.artista, grupo: e.local.grupo });
        e.datos = { titulo: e.local.nombre, artista: e.local.artista, anio: e.local.anio, tipo: "Álbum",
                    portada: e.local.portada, canciones: r.canciones, local: true };
      } else {
        e.datos = (await py("album", { browse_id: e.id })).album;
      }
    } catch (err) {
      aviso("No se pudo abrir el álbum", "error");
    }
  }
  onMount(() => { if (!e.datos) cargar(); });

  let version = ui.version;
  $effect(() => { if (ui.version !== version) { version = ui.version; cargar(); } });

  const faltan = $derived(a?.canciones?.filter((c) => !c.local && !c.ruta) ?? []);
  const duracion = $derived(Math.round((a?.canciones ?? []).reduce((s, c) => s + (c.duracion || 0), 0) / 60));

  function descargarTodo() {
    if (a.lista) descargarLink(a.lista).catch(() => descargar(faltan, a.titulo));
    else descargar(faltan, a.titulo);
  }
</script>

<div class="vista">
  <button class="redondo relleno volver" onclick={atras} aria-label="Atrás"><Icono nombre="atras" tam={24} /></button>
  {#if a}
    <div class="hero" in:fade={{ duration: 300 }}>
      <div class="ambiente" style:background-image={a.portada ? `url("${src(a.portada)}")` : "none"}></div>
      <div class="tapa"><Portada url={a.portada} radio="12px" sombra /></div>
      <h1>{a.titulo}</h1>
      {#if a.artista_id}
        <button class="artista" onclick={() => abrir("artista", { id: a.artista_id, nombre: a.artista })}>{a.artista}</button>
      {:else}
        <p class="artista">{a.artista}</p>
      {/if}
      <p class="meta">{[a.tipo, a.anio, `${a.canciones.length} canciones`, duracion ? `${duracion} min` : ""].filter(Boolean).join(" · ")}</p>
    </div>
    <div class="acciones">
      <button class="pildora clara" onclick={() => reproducir(a.canciones, 0, a.titulo)}><Icono nombre="play" relleno tam={20} /> Reproducir</button>
      <button class="pildora oscura" onclick={() => reproducirAleatorio(a.canciones, a.titulo)}><Icono nombre="aleatorio" tam={20} /> Aleatorio</button>
      {#if faltan.length}
        <button class="redondo relleno" onclick={descargarTodo} aria-label="Descargar álbum"><Icono nombre="descargas" tam={22} /></button>
      {/if}
    </div>
    <div class="canciones">
      {#each a.canciones as c, i}
        <FilaCancion cancion={c} numero={c.pista || i + 1} sinPortada alTocar={() => reproducir(a.canciones, i, a.titulo)} />
      {/each}
    </div>
  {:else}
    <div class="hero"><div class="cargando-bloque" style="width:62%;aspect-ratio:1;margin:0 auto"></div></div>
  {/if}
</div>

<style>
  .vista { position: relative; padding: 0 var(--margen); }
  .volver { position: absolute; top: calc(var(--seguro-arriba) + 10px); left: 12px; z-index: 3; background: rgba(0, 0, 0, 0.35); backdrop-filter: blur(10px); }
  .hero { position: relative; text-align: center; padding: calc(var(--seguro-arriba) + 62px) 0 4px; }
  .ambiente {
    position: absolute; inset: 0 calc(-1 * var(--margen)) -40px; z-index: -1; background-size: cover; background-position: center;
    filter: blur(60px) saturate(1.4) brightness(0.55); opacity: 0.9;
    mask-image: linear-gradient(#000 40%, transparent);
  }
  .tapa { width: 62%; max-width: 300px; margin: 0 auto 22px; }
  h1 { margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.4px; }
  .artista { display: block; margin: 8px auto 0; font-size: 17px; font-weight: 600; color: var(--cian); }
  .meta { margin: 6px 0 0; color: var(--tenue); font-size: 14px; }
  .acciones { display: flex; gap: 10px; justify-content: center; align-items: center; margin: 20px 0 14px; }
  .acciones .pildora { flex: 1; max-width: 170px; }
</style>
