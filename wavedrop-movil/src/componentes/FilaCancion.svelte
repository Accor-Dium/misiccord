<script>
  import { py, tiempo } from "../lib/api.js";
  import { abrir, aviso, descargar, mostrarHoja, ui } from "../lib/estado.svelte.js";
  import { pedirEliminar } from "../lib/eliminar.js";
  import { agregarAlJam, puedoAgregar } from "../lib/jam.svelte.js";
  import { rep } from "../lib/reproductor.svelte.js";
  import BotonDescarga from "./BotonDescarga.svelte";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Una canción en una lista. Toca para reproducir; "⋯" abre más opciones.
  let { cancion, numero = null, alTocar, sinPortada = false, extras = [] } = $props();
  const sonando = $derived(rep.actual && rep.actual.titulo === cancion.titulo && rep.actual.artista === cancion.artista);

  async function aPlaylist() {
    const { playlists } = await py("biblioteca");
    mostrarHoja({
      titulo: "Agregar a playlist",
      opciones: playlists.length
        ? playlists.map((p) => ({ texto: p.nombre, icono: "lista", accion: async () => {
            await py("agregar_a_playlist", { id: p.id, db_ids: [cancion.db_id] });
            ui.version++;
            aviso(`Agregada a “${p.nombre}”`, "ok");
          } }))
        : [{ texto: "Primero crea una playlist en Biblioteca", icono: "agregar", accion: () => {} }],
    });
  }

  function opciones() {
    const ops = [];
    if (puedoAgregar()) ops.push({ texto: "Agregar al jam", icono: "jam", accion: () => agregarAlJam(cancion) });
    if (cancion.db_id) ops.push({ texto: "Agregar a playlist", icono: "lista", accion: aPlaylist });
    if (!cancion.local && !cancion.ruta) ops.push({ texto: "Descargar", icono: "descargas", accion: () => descargar([cancion]) });
    if (cancion.album_id) ops.push({ texto: "Ver álbum", icono: "disco", accion: () => abrir("album", { id: cancion.album_id }) });
    ops.push({ texto: `Buscar más de ${cancion.artista.split(",")[0]}`, icono: "persona",
               accion: () => abrir("buscar_artista", { nombre: cancion.artista.split(",")[0] }) });
    if (cancion.db_id) ops.push({ texto: "Eliminar de la biblioteca", icono: "basura", peligro: true, accion: () =>
      pedirEliminar({ objetivo: { db_ids: [cancion.db_id] }, cuantas: 1, titulo: `“${cancion.titulo}”`,
                      seBorra: (c) => c.ruta === cancion.ruta }) });
    mostrarHoja({ titulo: cancion.titulo, subtitulo: cancion.artista, portada: cancion.portada, opciones: [...extras, ...ops] });
  }
</script>

<div class="fila" class:sonando role="button" tabindex="0" onclick={alTocar} onkeydown={(e) => e.key === "Enter" && alTocar?.()}>
  {#if numero !== null}
    <span class="numero">{#if sonando}<span class="barras"><i></i><i></i><i></i></span>{:else}{numero}{/if}</span>
  {/if}
  {#if !sinPortada}
    <Portada url={cancion.portada} tam="50px" radio="8px" />
  {/if}
  <div class="textos">
    <b class="cortar">{cancion.titulo}</b>
    <small class="cortar">{cancion.artista}{#if cancion.album && sinPortada === false} · {cancion.album}{/if}</small>
  </div>
  {#if cancion.duracion}<span class="dur">{tiempo(cancion.duracion)}</span>{/if}
  {#if puedoAgregar()}
    <button class="al-jam" aria-label="Agregar al jam" title="Agregar al jam"
      onclick={(e) => { e.stopPropagation(); agregarAlJam(cancion); }}>
      <Icono nombre="jam" tam={20} />
    </button>
  {:else if !cancion.local}<BotonDescarga {cancion} />{/if}
  <button class="mas" aria-label="Más opciones" onclick={(e) => { e.stopPropagation(); opciones(); }}>
    <Icono nombre="mas" tam={22} />
  </button>
</div>

<style>
  .fila {
    display: flex; align-items: center; gap: 12px; padding: 7px 0; border-radius: 10px;
    transition: background 0.2s; cursor: pointer;
  }
  .fila:active { background: rgba(255, 255, 255, 0.05); }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .textos b { font-weight: 600; font-size: 15.5px; }
  .textos small { color: var(--tenue); font-size: 13.5px; }
  .sonando b { color: var(--cian); }
  .numero { width: 26px; text-align: center; color: var(--tenue); font-variant-numeric: tabular-nums; flex-shrink: 0; }
  .dur { color: var(--tenue); font-size: 13px; font-variant-numeric: tabular-nums; }
  .al-jam { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; color: var(--cian); background: rgba(34, 211, 238, 0.1); flex-shrink: 0; }
  .al-jam:active { transform: scale(0.9); }
  .mas { width: 36px; height: 40px; display: grid; place-items: center; color: var(--tenue); }
  .barras { display: inline-flex; gap: 2px; align-items: flex-end; height: 14px; }
  .barras i { width: 3px; background: var(--cian); border-radius: 2px; animation: eq 0.9s infinite ease-in-out; }
  .barras i:nth-child(2) { animation-delay: -0.3s; }
  .barras i:nth-child(3) { animation-delay: -0.6s; }
  @keyframes eq { 0%, 100% { height: 4px; } 50% { height: 14px; } }
</style>
