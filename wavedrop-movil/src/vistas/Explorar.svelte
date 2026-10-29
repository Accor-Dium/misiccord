<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { abrir, abrirTarjeta, atras, aviso } from "../lib/estado.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import { reproducir } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Tarjeta from "../componentes/Tarjeta.svelte";

  // "Explorar" de Inicio, con lo general de YouTube Music:
  // e.que = "lanzamientos" (álbumes nuevos) | "tendencia" (canciones) | "estados" (estados de ánimo y géneros)
  //       | "estado" (las playlists de uno: e.params).
  let { e } = $props();
  const d = $derived(e.datos);

  async function cargar() {
    try {
      e.datos = e.que === "estado" ? await py("estado_animo", { params: e.params }) : await py("explorar");
    } catch (err) {
      aviso(err.message, "error");
    }
  }
  onMount(() => { if (!e.datos) cargar(); });

  // Colores para las cajas de estados de ánimo y géneros (como etiquetas de color)
  const colores = ["#22d3ee", "#a78bfa", "#f472b6", "#34d399", "#fbbf24", "#f87171", "#60a5fa", "#fb923c"];
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
    <h1 class="titulo-vista cortar">{e.titulo}</h1>
  </header>

  {#if !d}
    <div class="rejilla">{#each Array(6) as _}<div class="cargando-bloque" style="aspect-ratio:1"></div>{/each}</div>
  {:else if e.que === "lanzamientos"}
    <div class="rejilla" in:fade={{ duration: 220 }}>
      {#each d.lanzamientos as x}
        <Tarjeta portada={x.miniatura} titulo={x.titulo} subtitulo={x.subtitulo} ancho="100%" alTocar={() => abrirTarjeta(x)} />
      {/each}
    </div>
    {#if d.videos?.length}
      <div class="titulo-seccion">{t("Videos nuevos")}</div>
      <div class="carrusel">
        {#each d.videos as x}
          <Tarjeta portada={x.miniatura} titulo={x.titulo} subtitulo={x.subtitulo} icono="video" alTocar={() => abrirTarjeta(x)} />
        {/each}
      </div>
    {/if}
  {:else if e.que === "tendencia"}
    <div in:fade={{ duration: 220 }}>
      <div class="acciones">
        <button class="pildora clara" disabled={!d.tendencia.length} onclick={() => reproducir(d.tendencia, 0, e.titulo)}>
          <Icono nombre="play" relleno tam={20} /> {t("Reproducir")}
        </button>
        {#if d.tendencia_lista}
          <button class="pildora oscura" onclick={() => abrir("album", { playlist: d.tendencia_lista, nombre: e.titulo })}>
            <Icono nombre="lista" tam={20} /> {t("Ver lista")}
          </button>
        {/if}
      </div>
      {#each d.tendencia as c, i}
        <FilaCancion cancion={c} numero={i + 1} alTocar={() => reproducir(d.tendencia, i, e.titulo)} />
      {/each}
    </div>
  {:else if e.que === "estados"}
    <div in:fade={{ duration: 220 }}>
      {#each d.estados as g}
        <div class="titulo-seccion">{g.grupo}</div>
        <div class="etiquetas">
          {#each g.opciones as x, i}
            <button class="etiqueta" style:--color={colores[i % colores.length]}
              onclick={() => abrir("explorar", { que: "estado", params: x.params, titulo: x.titulo })}>{x.titulo}</button>
          {/each}
        </div>
      {/each}
    </div>
  {:else}
    <div class="rejilla" in:fade={{ duration: 220 }}>
      {#each d.tarjetas.slice(0, 80) as x}
        <Tarjeta portada={x.miniatura} titulo={x.titulo} subtitulo={x.subtitulo} icono="lista" ancho="100%" alTocar={() => abrirTarjeta(x)} />
      {:else}
        <p class="vacio">{t("No hay playlists aquí por ahora.")}</p>
      {/each}
    </div>
  {/if}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  header { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
  header h1 { font-size: 26px; }
  .rejilla { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 14px; }
  .acciones { display: flex; gap: 12px; margin: 0 0 12px; }
  .acciones .pildora { flex: 1; max-width: 190px; }
  .etiquetas { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .etiqueta {
    height: 52px; padding: 0 14px; border-radius: 12px; text-align: left; font-weight: 700; font-size: 15px;
    background: var(--tarjeta-2); border-left: 5px solid var(--color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .etiqueta:active { transform: scale(0.97); }
  @media (min-width: 900px) {
    .etiquetas { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  }
</style>
