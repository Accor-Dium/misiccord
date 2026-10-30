<script>
  import { fade, scale } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { aBody } from "../lib/aBody.js";
  import { aviso, ui } from "../lib/estado.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import { actualizarCancion } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Completar los datos de una o varias canciones, como Picard: para cada una se buscan en MusicBrainz todas las ediciones
  // en las que sale (Billie Jean → Thriller, Thriller 25, HIStory…) y tú eliges cuál es. Se abre con completarDatos([...]).
  const lista = $derived(ui.completar ?? []);
  let k = $state(0);
  let opciones = $state(null); // null = buscando
  let error = $state("");
  let aplicando = $state(false);
  let conPortada = $state(true);
  let hechas = 0;
  const c = $derived(lista[k]);

  let pedido = 0;
  async function buscar() {
    const yo = ++pedido;
    opciones = null;
    error = "";
    try {
      const r = await py("metadata_opciones", { titulo: c.titulo, artista: c.artista, album: c.album, duracion: c.duracion });
      if (yo === pedido) opciones = r.opciones;
    } catch (e) {
      if (yo === pedido) {
        error = e.message;
        opciones = [];
      }
    }
  }
  $effect(() => {
    if (ui.completar) {
      k = 0;
      hechas = 0;
    }
  });
  $effect(() => {
    if (c) buscar();
  });

  function cerrar() {
    ui.completar = null;
    if (hechas) {
      ui.version++;
      aviso(hechas === 1 ? t("Datos completados") : t("Datos completados en {n} canciones", { n: hechas }), "ok");
    }
  }
  function siguiente() {
    if (k + 1 < lista.length) k++;
    else cerrar();
  }
  async function elegir(o) {
    aplicando = true;
    try {
      const r = await py("metadata_aplicar", { ruta: c.ruta, opcion: o, portada: conPortada });
      if (r.cancion) actualizarCancion(r.cancion);
      hechas++;
      siguiente();
    } catch (e) {
      aviso(e.message, "error");
    } finally {
      aplicando = false;
    }
  }
  const TIPOS = { Album: t("Álbum"), Single: t("Sencillo"), Compilation: t("Recopilatorio"), Live: t("En vivo"), Soundtrack: t("Banda sonora") };
  const detalle = (o) => [o.anio, TIPOS[o.tipo] ?? o.tipo, o.pais, o.pista ? t("pista {n} de {total}", { n: o.pista, total: o.total_pistas ?? "?" }) : ""].filter(Boolean).join(" · ");
</script>

{#if c}
  <div class="fondo-modal" use:aBody transition:fade={{ duration: 180 }} onclick={cerrar} role="presentation"></div>
  <div class="modal" use:aBody transition:scale={{ duration: 220, start: 0.94 }} role="dialog" aria-label={t("Completar datos")}>
    <button class="redondo cerrar-modal" onclick={cerrar} aria-label={t("Cerrar")}><Icono nombre="cerrar" tam={22} /></button>
    <h2>{t("Completar datos")}</h2>
    {#if lista.length > 1}<small class="tenue">{t("Canción {k} de {n}", { k: k + 1, n: lista.length })}</small>{/if}
    <div class="actual">
      <Portada url={c.portada} tam="52px" radio="8px" icono="nota" />
      <span class="textos"><b class="cortar">{c.titulo}</b><small class="cortar">{[c.artista, c.album].filter(Boolean).join(" · ")}</small></span>
    </div>

    {#if opciones === null}
      <p class="tenue centro">{t("Buscando en MusicBrainz…")}</p>
      {#each Array(4) as _}<div class="cargando-bloque" style="height:62px;margin:8px 0"></div>{/each}
    {:else if !opciones.length}
      <p class="tenue centro">{error || t("MusicBrainz no encontró esta canción.")}</p>
    {:else}
      <p class="tenue centro">{t("¿De cuál edición es? Se reemplazan título, artista, álbum, año, pista y género.")}</p>
      <label class="con-portada"><input type="checkbox" bind:checked={conPortada} /> {t("Usar también su carátula")}</label>
      <div class="opciones">
        {#each opciones as o (o.mbid_album || o.album)}
          <button class="opcion" disabled={aplicando} onclick={() => elegir(o)}>
            <Portada url={o.miniatura} tam="56px" radio="6px" icono="disco" />
            <span class="textos">
              <b class="cortar">{o.album || o.titulo}</b>
              <small class="cortar">{o.artista_album || o.artista}</small>
              <small class="cortar">{detalle(o)}</small>
            </span>
          </button>
        {/each}
      </div>
    {/if}
    <button class="saltar" disabled={aplicando} onclick={siguiente}>{k + 1 < lista.length ? t("Saltar esta canción") : t("Cerrar")}</button>
  </div>
{/if}

<style>
  .fondo-modal { position: fixed; inset: 0; z-index: 310; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); }
  .modal {
    position: fixed; z-index: 311; left: 50%; top: 50%; transform: translate(-50%, -50%); display: flex; flex-direction: column;
    width: min(480px, calc(100vw - 24px)); max-height: calc(100vh - 32px);
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 24px; padding: 20px 18px 12px;
  }
  .cerrar-modal { position: absolute; top: 10px; right: 10px; }
  h2 { margin: 0 36px 2px 0; font-size: 21px; font-weight: 800; }
  .actual { display: flex; align-items: center; gap: 12px; margin-top: 12px; padding: 8px; border-radius: 12px; background: var(--fondo); }
  .textos { min-width: 0; display: flex; flex-direction: column; flex: 1; }
  .textos small { color: var(--tenue); font-size: 12.5px; }
  .centro { margin: 12px 0 8px; font-size: 13.5px; line-height: 1.4; }
  .con-portada { display: flex; align-items: center; gap: 8px; font-size: 14px; margin-bottom: 8px; }
  .con-portada input { accent-color: var(--cian); width: 18px; height: 18px; }
  .opciones { overflow-y: auto; min-height: 0; flex: 1; }
  .opcion { width: 100%; display: flex; align-items: center; gap: 12px; padding: 7px 6px; border-radius: 12px; text-align: left; }
  .opcion:hover { background: var(--tarjeta-2); }
  .saltar { padding: 12px 0 8px; color: var(--tenue); font-weight: 600; }
</style>
