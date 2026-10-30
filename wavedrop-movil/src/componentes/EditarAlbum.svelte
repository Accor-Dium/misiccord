<script>
  import { fade, scale } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { aBody } from "../lib/aBody.js";
  import { aviso, completarDatos } from "../lib/estado.svelte.js";
  import { aJpeg } from "../lib/imagen.js";
  import { t } from "../lib/idioma.svelte.js";
  import { actualizarCancion } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Editar un álbum completo, como en Groove: a mano o con "Actualizar en línea" (MusicBrainz). Al elegir una edición cada
  // canción se empareja con su pista; las que no coinciden del todo se resuelven una por una: otra pista, dejar tu nombre
  // o no incluirla (y entonces se sigue buscando a qué álbum pertenece).
  let { album, alCerrar, alGuardar } = $props();

  let nombre = $state(album.titulo);
  let artista = $state(album.artista);
  let anio = $state(album.anio || "");
  let genero = $state(album.canciones.find((c) => c.genero)?.genero ?? "");
  // destino: "mio" (dejar mi nombre), "fuera" (no incluirla) o el índice de una pista del álbum
  let filas = $state(album.canciones.map((c) => ({ c, pista: c.pista ?? "", disco: "", titulo: c.titulo, artista: c.artista, destino: "mio", estado: "" })));
  let online = $state(null); // la edición elegida con sus pistas
  let usarPortada = $state(true);
  let imagenNueva = $state(null);
  let guardando = $state(false);

  // ---------- Buscar en línea ----------
  let buscando = $state(false); // ventana de resultados abierta
  let qNombre = $state(album.titulo);
  let qArtista = $state(album.artista);
  let opciones = $state(null); // null = buscando
  let error = $state("");
  let cargandoPistas = $state(false);

  async function buscar() {
    buscando = true;
    opciones = null;
    error = "";
    try {
      opciones = (await py("album_opciones", { nombre: qNombre, artista: qArtista })).opciones;
    } catch (e) {
      error = e.message;
      opciones = [];
    }
  }

  function ponerPista(f, j, estado) {
    const p = online.pistas[j];
    f.destino = String(j);
    f.pista = p.pista;
    f.disco = online.discos > 1 ? p.disco : "";
    f.titulo = p.titulo;
    f.artista = p.artista;
    f.estado = estado;
  }

  async function elegir(o) {
    cargandoPistas = true;
    try {
      const r = await py("album_detalle", { mbid: o.mbid_album, canciones: filas.map((f) => ({ titulo: f.c.titulo, duracion: f.c.duracion })) });
      online = r.detalle;
      nombre = online.album;
      artista = online.artista_album || artista;
      anio = online.anio || anio;
      genero = online.genero || genero;
      imagenNueva = null;
      filas.forEach((f, i) => {
        const par = r.parejas[i];
        if (par.pista !== null) ponerPista(f, par.pista, par.estado);
        else cambiarDestino(f, "mio", "ninguna");
      });
      buscando = false;
    } catch (e) {
      aviso(e.message, "error");
    } finally {
      cargandoPistas = false;
    }
  }

  function cambiarDestino(f, valor, estado) {
    if (valor === "fuera") {
      f.destino = "fuera";
      f.estado = "fuera";
    } else if (valor === "mio") {
      f.destino = "mio";
      f.titulo = f.c.titulo;
      f.artista = f.c.artista;
      f.pista = f.c.pista ?? "";
      f.disco = "";
      f.estado = estado ?? "propio";
    } else {
      ponerPista(f, Number(valor), "elegida");
    }
  }

  /** Escribir el nombre a mano ya resuelve la duda: se queda en su pista, con lo que escribiste. */
  function resolver(f) {
    if (f.estado === "parecida" || f.estado === "ninguna") f.estado = "propio";
  }

  const ocupada = (j, yo) => filas.some((f) => f !== yo && f.destino === String(j));
  const nombrePista = (p) => `${online.discos > 1 ? `${p.disco}-` : ""}${p.pista}. ${p.titulo}`;
  const TIPOS = { Album: t("Álbum"), Single: t("Sencillo"), Compilation: t("Recopilatorio"), Live: t("En vivo"), Soundtrack: t("Banda sonora") };
  const ESTADOS = {
    exacta: ["bien", t("Coincide")], parecida: ["duda", t("Parecida")], ninguna: ["mal", t("Sin coincidencia")],
    elegida: ["bien", t("Elegida por ti")], propio: ["bien", t("Con tu nombre")], fuera: ["mal", t("No se incluye")],
  };
  const pendientes = $derived(filas.filter((f) => f.estado === "ninguna" || f.estado === "parecida").length);
  const incluidas = $derived(filas.filter((f) => f.destino !== "fuera"));

  async function elegirImagen(ev) {
    const archivo = ev.currentTarget.files?.[0];
    ev.currentTarget.value = "";
    if (!archivo) return;
    try {
      imagenNueva = await aJpeg(archivo);
    } catch {
      aviso(t("No pude usar esa imagen"), "error");
    }
  }

  async function guardar() {
    guardando = true;
    try {
      const canciones = incluidas.map((f) => ({
        ruta: f.c.ruta,
        campos: {
          titulo: f.titulo.trim() || f.c.titulo, artista: f.artista, album: nombre.trim(), artista_album: artista.trim(),
          anio: String(anio).trim(), genero: genero.trim(), pista: String(f.pista ?? "").trim(),
          ...(f.disco ? { disco: String(f.disco) } : {}),
        },
      }));
      const portada = imagenNueva ? { imagen: imagenNueva }
        : online && usarPortada ? { mbid_album: online.mbid_album, mbid_grupo: online.mbid_grupo } : {};
      const r = await py("album_guardar", { canciones, ...portada });
      r.canciones.forEach(actualizarCancion);
      if (r.fallidas.length) aviso(t("No se pudieron guardar {n}: {error}", { n: r.fallidas.length, error: r.fallidas[0].error }), "error");
      else aviso(t("Álbum guardado"), "ok");
      const fuera = filas.filter((f) => f.destino === "fuera").map((f) => f.c);
      alGuardar({ nombre: nombre.trim(), artista: artista.trim(), grupo: artista.trim(), anio: String(anio).trim(), portada: r.canciones[0]?.portada ?? album.portada });
      if (fuera.length) completarDatos(fuera); // las que no eran de este álbum: se sigue buscando el suyo
    } catch (e) {
      aviso(e.message, "error");
    } finally {
      guardando = false;
    }
  }
</script>

<div class="fondo-modal" use:aBody transition:fade={{ duration: 180 }} onclick={alCerrar} role="presentation"></div>
<div class="modal" use:aBody transition:scale={{ duration: 220, start: 0.96 }} role="dialog" aria-label={t("Editar información del álbum")}>
  <div class="cabeza">
    <h2>{t("Editar información del álbum")}</h2>
    <button class="en-linea" onclick={buscar}>{t("Actualizar en línea")}</button>
  </div>

  <div class="cuerpo">
    {#if buscando}
      <form class="busqueda" onsubmit={(ev) => { ev.preventDefault(); buscar(); }}>
        <input bind:value={qNombre} placeholder={t("Álbum")} aria-label={t("Álbum")} />
        <input bind:value={qArtista} placeholder={t("Artista")} aria-label={t("Artista")} />
        <button class="pildora oscura">{t("Buscar")}</button>
      </form>
      {#if opciones === null}
        <p class="tenue">{t("Buscando en MusicBrainz…")}</p>
        {#each Array(4) as _}<div class="cargando-bloque" style="height:66px;margin:8px 0"></div>{/each}
      {:else if !opciones.length}
        <p class="tenue">{error || t("MusicBrainz no encontró este álbum. Prueba con otro nombre.")}</p>
      {:else}
        <p class="tenue">{t("Elige tu edición: cambian las pistas entre una y otra.")}</p>
        {#each opciones as o (o.mbid_album)}
          <button class="opcion" disabled={cargandoPistas} onclick={() => elegir(o)}>
            <Portada url={o.miniatura} tam="56px" radio="6px" icono="disco" />
            <span class="textos">
              <b class="cortar">{o.album}</b>
              <small class="cortar">{o.artista_album}</small>
              <small class="cortar">{[o.anio, TIPOS[o.tipo] ?? o.tipo, o.pais, t("{n} pistas", { n: o.pistas })].filter(Boolean).join(" · ")}</small>
            </span>
          </button>
        {/each}
      {/if}
      <button class="volver" onclick={() => (buscando = false)}>{t("Volver sin cambiar nada")}</button>
    {:else}
      <div class="datos">
        <div class="campos">
          <label><small>{t("Álbum")}</small><input bind:value={nombre} /></label>
          <label><small>{t("Artista del álbum")}</small><input bind:value={artista} /></label>
          <div class="dos">
            <label><small>{t("Género")}</small><input bind:value={genero} /></label>
            <label><small>{t("Año")}</small><input bind:value={anio} inputmode="numeric" /></label>
          </div>
        </div>
        <div class="tapa">
          {#if imagenNueva}
            <img src={imagenNueva} alt="" />
          {:else}
            <Portada url={online && usarPortada ? online.miniatura : album.portada} radio="10px" icono="disco" />
          {/if}
          <label class="lapiz" title={t("Cambiar carátula")}>
            <Icono nombre="lapiz" tam={18} />
            <input type="file" accept="image/*" onchange={elegirImagen} />
          </label>
        </div>
      </div>
      {#if online && !imagenNueva}
        <label class="marca"><input type="checkbox" bind:checked={usarPortada} /> {t("Usar la carátula de esta edición")}</label>
      {/if}
      {#if online}
        <p class="tenue resumen">
          {t("Esta edición tiene {n} pistas; tienes {m}.", { n: online.pistas.length, m: filas.length })}
          {#if pendientes}<b class="aviso-duda">{t("Por revisar: {n}", { n: pendientes })}</b>{/if}
        </p>
      {/if}

      <div class="titulos" aria-hidden="true"><small>{t("Pista")}</small><small>{t("Título")}</small><small>{t("Intérprete")}</small></div>
      {#each filas as f (f.c.ruta)}
        <div class="fila" class:fuera={f.destino === "fuera"}>
          <div class="renglon">
            <input class="pista" bind:value={f.pista} inputmode="numeric" aria-label={t("Pista")} disabled={f.destino === "fuera"} />
            <input bind:value={f.titulo} oninput={() => resolver(f)} aria-label={t("Título")} disabled={f.destino === "fuera"} />
            <input bind:value={f.artista} aria-label={t("Intérprete")} disabled={f.destino === "fuera"} />
          </div>
          {#if online}
            <div class="decision">
              <span class="estado {ESTADOS[f.estado]?.[0] ?? ''}">{ESTADOS[f.estado]?.[1] ?? ""}</span>
              {#if f.titulo !== f.c.titulo && f.destino !== "fuera"}<small class="tuyo cortar">{t("Tu archivo: {titulo}", { titulo: f.c.titulo })}</small>{/if}
              <select value={f.destino} onchange={(ev) => cambiarDestino(f, ev.target.value)} aria-label={t("Qué hacer con {titulo}", { titulo: f.c.titulo })}>
                <optgroup label={t("Es esta pista")}>
                  {#each online.pistas as p, j}<option value={String(j)} disabled={ocupada(j, f)}>{nombrePista(p)}</option>{/each}
                </optgroup>
                <optgroup label={t("Otra opción")}>
                  <option value="mio">{t("Dejarla con mi nombre")}</option>
                  <option value="fuera">{t("No incluirla y buscar su álbum")}</option>
                </optgroup>
              </select>
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </div>

  {#if !buscando}
    <div class="pie">
      <button class="pildora cian" disabled={guardando || !nombre.trim() || !incluidas.length} onclick={guardar}>{guardando ? t("Guardando…") : t("Guardar")}</button>
      <button class="pildora oscura" disabled={guardando} onclick={alCerrar}>{t("Cancelar")}</button>
    </div>
  {/if}
</div>

<style>
  .fondo-modal { position: fixed; inset: 0; z-index: 300; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); }
  .modal {
    position: fixed; z-index: 301; left: 50%; top: 50%; transform: translate(-50%, -50%); display: flex; flex-direction: column;
    width: min(760px, calc(100vw - 16px)); max-height: calc(100vh - 24px);
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 20px;
  }
  .cabeza { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 14px; padding: 18px 18px 10px; }
  h2 { margin: 0; font-size: 20px; font-weight: 800; }
  .en-linea { color: var(--cian); font-weight: 700; font-size: 14.5px; }
  .cuerpo { flex: 1; min-height: 0; overflow-y: auto; padding: 4px 18px 10px; }
  input:not([type]), select, .busqueda input {
    width: 100%; min-width: 0; height: 40px; padding: 0 10px; border-radius: 9px; border: 1px solid var(--borde-fuerte); background: var(--fondo); color: inherit; font: inherit; font-size: 14.5px; outline: 0;
  }
  input:focus, select:focus { border-color: var(--cian); }
  input:disabled { opacity: 0.45; }
  label small, .titulos small { color: var(--tenue); font-size: 12px; }
  label { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  .datos { display: grid; grid-template-columns: minmax(0, 1fr) 170px; gap: 14px; }
  .campos { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .dos { display: grid; grid-template-columns: 1fr 90px; gap: 8px; }
  .tapa { position: relative; align-self: start; }
  .tapa img { display: block; width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 10px; }
  .lapiz { position: absolute; left: 8px; bottom: 8px; width: 34px; height: 34px; border-radius: 8px; display: grid; place-items: center; background: rgba(0, 0, 0, 0.6); color: #fff; cursor: pointer; }
  .lapiz input { display: none; }
  .marca { flex-direction: row; align-items: center; gap: 8px; margin-top: 8px; font-size: 13.5px; }
  .marca input { accent-color: var(--cian); width: 17px; height: 17px; }
  .resumen { margin: 10px 0 0; font-size: 13.5px; }
  .aviso-duda { color: #fbbf24; font-weight: 600; }
  .titulos { display: grid; grid-template-columns: 54px minmax(0, 1fr) minmax(0, 1fr); gap: 8px; margin-top: 12px; }
  .fila { padding: 5px 0 7px; border-bottom: 1px solid var(--borde); }
  .fila.fuera { opacity: 0.6; }
  .renglon { display: grid; grid-template-columns: 54px minmax(0, 1fr) minmax(0, 1fr); gap: 8px; }
  .pista { text-align: center; padding: 0 4px; }
  .decision { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; margin-top: 5px; }
  .estado { font-size: 12px; font-weight: 700; flex-shrink: 0; }
  .estado.bien { color: #4ade80; }
  .estado.duda { color: #fbbf24; }
  .estado.mal { color: var(--rojo); }
  .tuyo { color: var(--tenue); font-size: 12.5px; min-width: 0; flex: 1; }
  .decision select { flex: 1 1 200px; width: auto; height: 34px; font-size: 13.5px; max-width: 100%; }
  .busqueda { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 8px; margin-bottom: 8px; }
  .busqueda .pildora { height: 40px; padding: 0 14px; font-size: 14px; }
  .opcion { width: 100%; display: flex; align-items: center; gap: 12px; padding: 7px 6px; border-radius: 12px; text-align: left; }
  .opcion:hover { background: var(--tarjeta-2); }
  .textos { min-width: 0; display: flex; flex-direction: column; flex: 1; }
  .textos small { color: var(--tenue); font-size: 12.5px; }
  .volver { display: block; margin: 10px auto 4px; color: var(--tenue); font-weight: 600; }
  .pie { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 12px 18px 16px; border-top: 1px solid var(--borde); }
  .pie .pildora { justify-content: center; height: 44px; }
  .pie .pildora:disabled { opacity: 0.45; }
  @media (max-width: 560px) {
    .datos { grid-template-columns: minmax(0, 1fr) 110px; }
    .titulos { display: none; }
    .renglon { grid-template-columns: 46px minmax(0, 1fr); }
    .renglon input:last-child { grid-column: 2; }
    .busqueda { grid-template-columns: 1fr; }
  }
</style>
