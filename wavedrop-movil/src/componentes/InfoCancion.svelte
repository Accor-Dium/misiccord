<script>
  import { fade, scale } from "svelte/transition";
  import { py, tiempo } from "../lib/api.js";
  import { aBody } from "../lib/aBody.js";
  import { aviso, completarDatos, ui } from "../lib/estado.svelte.js";
  import { aJpeg } from "../lib/imagen.js";
  import { local, t } from "../lib/idioma.svelte.js";
  import { actualizarCancion } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Información de una canción (⋯ → Información). Si está descargada se pueden editar sus etiquetas y su carátula;
  // si es una vista previa de YouTube Music solo se consulta. Se abre con verInfo(cancion) (estado.svelte.js).
  const c = $derived(ui.info);
  let datos = $state(null);
  let campos = $state({});
  let guardando = $state(false);

  const ETIQUETAS = [
    ["titulo", t("Título")], ["artista", t("Artista")], ["album", t("Álbum")], ["artista_album", t("Artista del álbum")],
    ["anio", t("Año")], ["pista", t("Pista")], ["disco", t("Disco")], ["genero", t("Género")], ["compositor", t("Compositor")],
  ];

  $effect(() => {
    const cancion = ui.info;
    datos = null;
    if (!cancion) return;
    py("info_cancion", {
      ruta: cancion.ruta || null, id: cancion.id, titulo: cancion.titulo, artista: cancion.artista,
      album: cancion.album, anio: cancion.anio, duracion: cancion.duracion, portada: cancion.portada,
    })
      .then((r) => {
        if (ui.info !== cancion) return;
        datos = r;
        campos = { ...r.campos };
      })
      .catch((e) => {
        aviso(e.message, "error");
        cerrar();
      });
  });

  const editable = $derived(!!datos?.editable);
  const cambiado = $derived(!!datos && ETIQUETAS.some(([k]) => (campos[k] ?? "") !== (datos.campos[k] ?? "")));

  function cerrar() {
    ui.info = null;
  }

  async function guardar() {
    guardando = true;
    try {
      const soloCambios = Object.fromEntries(ETIQUETAS.map(([k]) => k).filter((k) => campos[k] !== datos.campos[k]).map((k) => [k, campos[k]]));
      const r = await py("guardar_etiquetas", { ruta: c.ruta, campos: soloCambios });
      datos = { ...datos, campos: { ...campos } };
      if (r.cancion) actualizarCancion(r.cancion);
      ui.version++;
      aviso(t("Etiquetas guardadas"), "ok");
    } catch (e) {
      aviso(e.message, "error");
    } finally {
      guardando = false;
    }
  }

  async function elegirImagen(ev) {
    const archivo = ev.currentTarget.files?.[0];
    ev.currentTarget.value = "";
    if (!archivo) return;
    guardando = true;
    try {
      const r = await py("cambiar_portada", { ruta: c.ruta, imagen: await aJpeg(archivo) });
      datos = { ...datos, portada: r.cancion?.portada ?? datos.portada };
      if (r.cancion) actualizarCancion(r.cancion);
      ui.version++;
      aviso(t("Carátula cambiada"), "ok");
    } catch (e) {
      aviso(e.message || t("No pude usar esa imagen"), "error");
    } finally {
      guardando = false;
    }
  }

  const fecha = (s) => (s ? new Date(s * 1000).toLocaleDateString(local(), { day: "numeric", month: "short", year: "numeric" }) : "—");

  /** Datos técnicos en filas "nombre: valor" (solo los que se conocen). */
  const tecnico = $derived.by(() => {
    const x = datos?.tecnico;
    if (!x) return [];
    const calidad = [x.codec, x.kbps && `${x.kbps} kbps`, x.hz && `${(x.hz / 1000).toFixed(1)} kHz`, x.bits && `${x.bits} bits`,
                     x.canales && (x.canales === 1 ? t("mono") : x.canales === 2 ? t("estéreo") : t("{n} canales", { n: x.canales }))].filter(Boolean).join(" · ");
    // La tercera columna dice si se puede copiar (ubicación y enlace)
    return [
      [t("Fuente"), x.fuente], [t("Formato"), x.formato], [t("Duración"), x.duracion ? tiempo(x.duracion) : null], [t("Calidad"), calidad],
      [t("Tamaño"), x.tamano_mb != null ? `${x.tamano_mb} MB` : null],
      [t("Reproducciones"), x.reproducciones != null ? String(x.reproducciones) : null],
      [t("Última vez"), x.ultima ? fecha(x.ultima) : null], [t("En tu biblioteca desde"), x.agregada ? fecha(x.agregada) : null],
      [t("Ubicación"), x.ruta, true], [t("Enlace"), x.enlace, true],
    ].filter(([, v]) => v);
  });

  async function copiar(texto) {
    try {
      await navigator.clipboard.writeText(texto);
      aviso(t("Copiado"), "ok");
    } catch {}
  }
</script>

{#if c}
  <div class="fondo-modal" use:aBody transition:fade={{ duration: 180 }} onclick={cerrar} role="presentation"></div>
  <div class="modal" use:aBody transition:scale={{ duration: 220, start: 0.94 }} role="dialog" aria-label={t("Información de la canción")}>
    <button class="redondo cerrar-modal" onclick={cerrar} aria-label={t("Cerrar")}><Icono nombre="cerrar" tam={22} /></button>
    <div class="cabeza">
      <div class="tapa">
        <Portada url={datos?.portada ?? c.portada} tam="104px" radio="12px" icono="nota" />
        {#if editable}
          <label class="cambiar" class:ocupado={guardando}>
            <Icono nombre="camara" tam={16} /> {t("Cambiar")}
            <input type="file" accept="image/*" onchange={elegirImagen} disabled={guardando} />
          </label>
        {/if}
      </div>
      <div class="textos">
        <small class="etiqueta">{editable ? t("DESCARGADA") : datos?.descargada ? t("DESCARGADA · SOLO LECTURA") : t("VISTA PREVIA")}</small>
        <b>{c.titulo}</b>
        <span class="tenue">{c.artista}</span>
      </div>
    </div>

    {#if !datos}
      {#each Array(5) as _}<div class="cargando-bloque" style="height:44px;margin:10px 0"></div>{/each}
    {:else}
      <form class="campos" onsubmit={(e) => { e.preventDefault(); if (cambiado) guardar(); }}>
        {#each ETIQUETAS as [clave, texto]}
          {#if editable || campos[clave]}
            <label class:corto={["anio", "pista", "disco"].includes(clave)}>
              <small>{texto}</small>
              {#if editable}
                <input bind:value={campos[clave]} inputmode={["anio", "pista", "disco"].includes(clave) ? "numeric" : "text"} />
              {:else}
                <span>{campos[clave]}</span>
              {/if}
            </label>
          {/if}
        {/each}
        {#if editable}
          <button class="pildora cian ancho" disabled={!cambiado || guardando}>{guardando ? t("Guardando…") : t("Guardar etiquetas")}</button>
        {:else if !datos.descargada}
          <p class="tenue nota">{t("Descárgala para poder editar sus etiquetas y su carátula.")}</p>
        {/if}
      </form>

      {#if editable}
        <button class="pildora oscura completar" onclick={() => { const x = c; cerrar(); completarDatos([x]); }}>
          <Icono nombre="etiqueta" tam={18} /> {t("Completar con MusicBrainz")}
        </button>
      {/if}
      <h3>{t("Detalles")}</h3>
      <dl>
        {#each tecnico as [nombre, valor, copiable]}
          <dt>{nombre}</dt>
          <dd>
            {#if copiable}
              <button class="copiable" onclick={() => copiar(valor)} title={t("Copiar")}>{valor}</button>
            {:else}{valor}{/if}
          </dd>
        {/each}
      </dl>
    {/if}
  </div>
{/if}

<style>
  .fondo-modal { position: fixed; inset: 0; z-index: 300; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); }
  .modal {
    position: fixed; z-index: 301; left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: min(460px, calc(100vw - 24px)); max-height: calc(100vh - 32px); overflow-y: auto;
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 24px; padding: 22px 20px 18px;
  }
  .cerrar-modal { position: absolute; top: 10px; right: 10px; }
  .cabeza { display: flex; gap: 16px; align-items: center; margin-right: 32px; }
  .tapa { position: relative; flex-shrink: 0; }
  .cambiar {
    position: absolute; z-index: 2; left: 50%; bottom: -10px; transform: translateX(-50%); display: inline-flex; align-items: center; gap: 5px;
    padding: 5px 11px; border-radius: 999px; background: #fff; color: #04121a; font-size: 12.5px; font-weight: 700; cursor: pointer;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.4); white-space: nowrap;
  }
  .cambiar.ocupado { opacity: 0.6; pointer-events: none; }
  .cambiar input { display: none; }
  .textos { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .textos b { font-size: 18px; font-weight: 800; overflow-wrap: anywhere; }
  .etiqueta { font-size: 11px; letter-spacing: 1.4px; color: var(--cian); font-weight: 700; }
  .campos { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 24px; }
  .campos label { grid-column: 1 / -1; display: flex; flex-direction: column; gap: 4px; }
  .campos label.corto { grid-column: span 1; }
  .campos small { color: var(--tenue); font-size: 12px; }
  .campos input {
    height: 42px; border-radius: 11px; border: 1px solid var(--borde-fuerte); background: var(--fondo); padding: 0 12px; outline: 0; min-width: 0;
  }
  .campos input:focus { border-color: var(--cian); }
  .campos span { padding: 2px 0 6px; border-bottom: 1px solid var(--borde); overflow-wrap: anywhere; }
  .completar { width: 100%; justify-content: center; margin-top: 10px; height: 42px; font-size: 14.5px; }
  .ancho { grid-column: 1 / -1; justify-content: center; margin-top: 4px; }
  .ancho:disabled { opacity: 0.45; }
  .nota { grid-column: 1 / -1; margin: 4px 0 0; font-size: 13.5px; }
  h3 { margin: 22px 0 8px; font-size: 13px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--cian); }
  dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 7px 14px; margin: 0; font-size: 14px; }
  dt { color: var(--tenue); }
  dd { margin: 0; overflow-wrap: anywhere; }
  .copiable { text-align: left; padding: 0; font: inherit; color: inherit; overflow-wrap: anywhere; font-size: 12.5px; font-family: ui-monospace, monospace; }
  .copiable:hover { color: var(--cian); }
</style>
