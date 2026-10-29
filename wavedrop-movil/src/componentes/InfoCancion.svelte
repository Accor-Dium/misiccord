<script>
  import { fade, scale } from "svelte/transition";
  import { py, tiempo } from "../lib/api.js";
  import { aBody } from "../lib/aBody.js";
  import { aviso, ui } from "../lib/estado.svelte.js";
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
    ["titulo", "Título"], ["artista", "Artista"], ["album", "Álbum"], ["artista_album", "Artista del álbum"],
    ["anio", "Año"], ["pista", "Pista"], ["disco", "Disco"], ["genero", "Género"], ["compositor", "Compositor"],
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
      aviso("Etiquetas guardadas", "ok");
    } catch (e) {
      aviso(e.message, "error");
    } finally {
      guardando = false;
    }
  }

  /** Cualquier imagen del teléfono o la PC se pasa a JPG de hasta 1200 px (así WebP o fotos enormes también sirven). */
  async function aJpeg(archivo) {
    const imagen = await createImageBitmap(archivo);
    const escala = Math.min(1, 1200 / Math.max(imagen.width, imagen.height));
    const lienzo = document.createElement("canvas");
    lienzo.width = Math.round(imagen.width * escala);
    lienzo.height = Math.round(imagen.height * escala);
    lienzo.getContext("2d").drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
    return lienzo.toDataURL("image/jpeg", 0.9);
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
      aviso("Carátula cambiada", "ok");
    } catch (e) {
      aviso(e.message || "No pude usar esa imagen", "error");
    } finally {
      guardando = false;
    }
  }

  const fecha = (s) => (s ? new Date(s * 1000).toLocaleDateString("es", { day: "numeric", month: "short", year: "numeric" }) : "—");

  /** Datos técnicos en filas "nombre: valor" (solo los que se conocen). */
  const tecnico = $derived.by(() => {
    const t = datos?.tecnico;
    if (!t) return [];
    const calidad = [t.codec, t.kbps && `${t.kbps} kbps`, t.hz && `${(t.hz / 1000).toFixed(1)} kHz`, t.bits && `${t.bits} bits`,
                     t.canales && (t.canales === 1 ? "mono" : t.canales === 2 ? "estéreo" : `${t.canales} canales`)].filter(Boolean).join(" · ");
    return [
      ["Fuente", t.fuente], ["Formato", t.formato], ["Duración", t.duracion ? tiempo(t.duracion) : null], ["Calidad", calidad],
      ["Tamaño", t.tamano_mb != null ? `${t.tamano_mb} MB` : null],
      ["Reproducciones", t.reproducciones != null ? String(t.reproducciones) : null],
      ["Última vez", t.ultima ? fecha(t.ultima) : null], ["En tu biblioteca desde", t.agregada ? fecha(t.agregada) : null],
      ["Ubicación", t.ruta], ["Enlace", t.enlace],
    ].filter(([, v]) => v);
  });

  async function copiar(texto) {
    try {
      await navigator.clipboard.writeText(texto);
      aviso("Copiado", "ok");
    } catch {}
  }
</script>

{#if c}
  <div class="fondo-modal" use:aBody transition:fade={{ duration: 180 }} onclick={cerrar} role="presentation"></div>
  <div class="modal" use:aBody transition:scale={{ duration: 220, start: 0.94 }} role="dialog" aria-label="Información de la canción">
    <button class="redondo cerrar-modal" onclick={cerrar} aria-label="Cerrar"><Icono nombre="cerrar" tam={22} /></button>
    <div class="cabeza">
      <div class="tapa">
        <Portada url={datos?.portada ?? c.portada} tam="104px" radio="12px" icono="nota" />
        {#if editable}
          <label class="cambiar" class:ocupado={guardando}>
            <Icono nombre="camara" tam={16} /> Cambiar
            <input type="file" accept="image/*" onchange={elegirImagen} disabled={guardando} />
          </label>
        {/if}
      </div>
      <div class="textos">
        <small class="etiqueta">{editable ? "DESCARGADA" : datos?.descargada ? "DESCARGADA · SOLO LECTURA" : "VISTA PREVIA"}</small>
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
          <button class="pildora cian ancho" disabled={!cambiado || guardando}>{guardando ? "Guardando…" : "Guardar etiquetas"}</button>
        {:else if !datos.descargada}
          <p class="tenue nota">Descárgala para poder editar sus etiquetas y su carátula.</p>
        {/if}
      </form>

      <h3>Detalles</h3>
      <dl>
        {#each tecnico as [nombre, valor]}
          <dt>{nombre}</dt>
          <dd>
            {#if nombre === "Ubicación" || nombre === "Enlace"}
              <button class="copiable" onclick={() => copiar(valor)} title="Copiar">{valor}</button>
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
