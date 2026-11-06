<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py, src } from "../lib/api.js";
  import { abrir, atras, aviso, descargar, descargarLink, mostrarHoja, ui } from "../lib/estado.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import { pedirEliminar } from "../lib/eliminar.js";
  import { canciones, t } from "../lib/idioma.svelte.js";
  import { categoriasDe, esDecada, listaCategorias } from "../lib/categorias.js";
  import EditarAlbum from "../componentes/EditarAlbum.svelte";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";

  // Álbum de YouTube Music (e.id, o e.buscar con "álbum artista"), playlist de YouTube Music (e.playlist)
  // o álbum de tu biblioteca (e.local).
  let { e } = $props();
  const a = $derived(e.datos);
  const alArtista = $derived(a?.artista_id ? { id: a.artista_id, nombre: a.artista } : a?.artista_principal ? { nombre: a.artista_principal } : null);
  let completo = $state(e.completo ?? null); // lo que te falta del álbum, según YouTube Music: { encontrado, total, faltantes, id }
  let revision = $state(e.completo ? "lista" : ""); // "" | "buscando" | "lista" | "error"
  let editando = $state(false); // false, o { enLinea } si se abrió para guardar los datos del álbum
  let pedidoCarga = 0;
  let pedidoRevision = 0;
  const tienes = $derived(completo?.encontrado ? completo.total - completo.faltantes.length : 0);

  async function cargar() {
    const yo = ++pedidoCarga;
    try {
      // Primero lo tuyo: es instantáneo y funciona sin internet. Si lo tienes, internet solo agrega lo que falta
      if (!e.local && e.buscar && e.nombre) {
        const { album } = await py("album_local_buscar", { nombre: e.nombre, artista: e.artista });
        if (album) e.local = album;
      }
      if (e.local) {
        const r = await py("album_local", { nombre: e.local.nombre, artista: e.local.artista, grupo: e.local.grupo });
        if (yo !== pedidoCarga) return; // ya se pidió otro (p. ej. se le cambió el nombre al álbum)
        e.datos = { titulo: e.local.nombre, artista: e.local.artista, anio: e.local.anio, tipo: "Álbum",
                    portada: e.local.portada, canciones: r.canciones, local: true, artista_principal: r.artista_principal,
                    categorias: r.categorias, propias: r.propias };
        revisarFaltantes();
      } else if (e.playlist) {
        e.datos = (await py("playlist_yt", { id: e.playlist })).album;
      } else {
        if (!e.id && e.buscar) {
          // Solo se sabe el nombre (canción en vista previa): el primer álbum que encuentre YouTube Music
          const r = await py("buscar", { q: e.buscar, tipo: "albumes" });
          e.id = r.albumes?.[0]?.browse_id;
          if (!e.id) throw new Error("sin álbum");
        }
        e.datos = (await py("album", { browse_id: e.id })).album;
      }
    } catch (err) {
      aviso(e.playlist ? t("No se pudo abrir la playlist") : t("No se pudo abrir el álbum"), "error");
    }
  }
  onMount(() => {
    if (!e.datos) cargar();
    else if (e.local) revisarFaltantes(); // regresas a él: lo que descargaste mientras tanto ya no falta
  });

  /** Python guarda lo de YouTube Music: esto casi siempre es inmediato. Con `forzar` (Actualizar) lo vuelve a pedir. */
  async function revisarFaltantes(forzar = false) {
    const yo = ++pedidoRevision;
    if (forzar || !completo) revision = "buscando";
    let reloj;
    try {
      // Sin esto una red que no responde se veía como un álbum al que no le falta nada, cargando para siempre
      const limite = new Promise((_, no) => (reloj = setTimeout(no, 30000)));
      const r = await Promise.race([py("album_faltantes", { nombre: e.local.nombre, artista: e.local.artista, grupo: e.local.grupo, forzar }), limite]);
      if (yo !== pedidoRevision) return;
      completo = e.completo = r;
      revision = "lista";
    } catch {
      if (yo === pedidoRevision) revision = "error";
    } finally {
      clearTimeout(reloj);
    }
  }

  let version = ui.version;
  $effect(() => { if (ui.version !== version) { version = ui.version; cargar(); } });

  const faltan = $derived(a?.canciones?.filter((c) => !c.local && !c.ruta) ?? []);

  // Las primeras canciones se dejan listas para que suenen en cuanto las toques
  $effect(() => {
    const ids = (a?.canciones ?? []).filter((c) => !c.ruta && c.id).slice(0, 5).map((c) => c.id);
    if (ids.length) py("precargar", { ids }).catch(() => {});
  });
  const duracion = $derived(Math.round((a?.canciones ?? []).reduce((s, c) => s + (c.duracion || 0), 0) / 60));

  function eliminarAlbum() {
    const rutas = new Set(a.canciones.map((c) => c.ruta));
    pedirEliminar({
      objetivo: { album: { nombre: e.local.nombre, grupo: e.local.grupo, artista: e.local.artista } },
      cuantas: a.canciones.length, titulo: t("el álbum “{titulo}”", a), seBorra: (c) => rutas.has(c.ruta),
      alTerminar: (r) => r?.eliminadas && atras(),
    });
  }

  /** Se guardó con otros datos: el álbum puede llamarse distinto, así que se vuelve a buscar con los nuevos. */
  function alGuardarAlbum(nuevo) {
    editando = false;
    e.local = { ...e.local, ...nuevo };
    completo = e.completo = null;
    cargar();
  }

  /** Corregir en qué filtros de Biblioteca sale este álbum: solo se guarda en la app, las etiquetas no se tocan. */
  function elegirCategorias() {
    // Sin décadas: cada canción conserva la de su año, y un disco puede traer pistas de dos
    const actuales = new Set((a.categorias ?? a.canciones.flatMap((c) => [...categoriasDe(c)])).filter((id) => !esDecada(id)));
    const guardar = async (lista) => {
      await py("album_categorias", { album: e.local.nombre, grupo: e.local.grupo, categorias: lista });
      ui.version++;
    };
    const cambiar = (id) => {
      actuales.has(id) ? actuales.delete(id) : actuales.add(id);
      guardar([...actuales]);
    };
    mostrarHoja({
      titulo: t("Categorías de este álbum"), subtitulo: t("Dónde sale en los filtros de tu biblioteca"),
      opciones: [
        ...listaCategorias({ propias: a.propias }).map(({ id, nombre }) => ({ texto: t(nombre), icono: actuales.has(id) ? "check" : "agregar", accion: () => cambiar(id) })),
        ...(a.categorias ? [{ texto: t("Dejar que se deduzcan solas"), icono: "actualizar", accion: () => guardar(null) }] : []),
      ],
    });
  }

  function descargarTodo() {
    if (a.lista) descargarLink(a.lista).catch(() => descargar(faltan, a.titulo));
    else descargar(faltan, a.titulo);
  }
</script>

<div class="vista">
  <button class="redondo relleno volver" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
  {#if a}
    <div class="hero" in:fade={{ duration: 300 }}>
      <div class="ambiente" style:background-image={a.portada ? `url("${src(a.portada)}")` : "none"}></div>
      <div class="tapa"><Portada url={a.portada} radio="12px" sombra objeto etiqueta={{ titulo: a.titulo, artista: a.artista, anio: a.anio, pistas: a.canciones }} /></div>
      <h1>{a.titulo}</h1>
      {#if alArtista}
        <button class="artista" onclick={() => abrir("artista", alArtista)}>{a.artista}</button>
      {:else}
        <p class="artista">{a.artista}</p>
      {/if}
      <p class="meta">{[a.tipo === "Álbum" || a.tipo === "Playlist" ? t(a.tipo) : a.tipo, a.anio, canciones(a.canciones.length), duracion ? `${duracion} min` : ""].filter(Boolean).join(" · ")}</p>
      {#if a.local && completo?.encontrado}
        <div class="avance" title={t("{n} de {total} canciones", { n: tienes, total: completo.total })}>
          <span class="barra"><i style:width="{(tienes / (completo.total || 1)) * 100}%"></i></span>
          <small>{t("{n} de {total} canciones", { n: tienes, total: completo.total })}</small>
        </div>
      {/if}
    </div>
    <div class="acciones">
      <button class="pildora clara" onclick={() => reproducir(a.canciones, 0, a.titulo)}><Icono nombre="play" relleno tam={20} /> {t("Reproducir")}</button>
      <button class="pildora oscura" onclick={() => reproducirAleatorio(a.canciones, a.titulo)}><Icono nombre="aleatorio" tam={20} /> {t("Aleatorio")}</button>
      {#if faltan.length}
        <button class="redondo relleno" onclick={descargarTodo} aria-label={e.playlist ? t("Descargar playlist") : t("Descargar álbum")}><Icono nombre="descargas" tam={22} /></button>
      {/if}
      {#if a.local && a.canciones.length}
        <button class="redondo relleno" onclick={() => (editando = { enLinea: false })} aria-label={t("Editar información")} title={t("Editar información")}><Icono nombre="lapiz" tam={21} /></button>
        <button class="redondo relleno borrar" onclick={eliminarAlbum} aria-label={t("Eliminar álbum")} title={t("Eliminar álbum")}><Icono nombre="basura" tam={22} /></button>
      {/if}
    </div>
    <div class="canciones">
      {#each a.canciones as c, i}
        <FilaCancion cancion={c} numero={c.pista || i + 1} sinPortada alTocar={() => reproducir(a.canciones, i, a.titulo)} />
      {/each}
    </div>
    {#if a.local}
      <div class="titulo-seccion revision">
        <span>
          {#if revision === "buscando"}{t("Revisando qué te falta…")}
          {:else if revision === "error"}{t("No pude revisar este álbum")}
          {:else if !completo?.encontrado}{t("No encontré este álbum en YouTube Music")}
          {:else if completo.faltantes.length}{t("Te faltan de este álbum")}
          {:else}{t("Tienes el álbum completo")}{/if}
        </span>
        {#if revision === "buscando"}
          <span class="girando" aria-hidden="true"></span>
        {:else}
          <button onclick={() => revisarFaltantes(true)}><small>{revision === "lista" ? t("Actualizar") : t("Reintentar")}</small></button>
        {/if}
      </div>
      {#if revision === "buscando" && !completo}
        {#each Array(2) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
      {/if}
      {#if revision !== "buscando" && a.canciones.length}
        <div class="botones-revision">
          {#if completo?.faltantes?.length}
            <button class="pildora oscura chica" onclick={() => descargar(completo.faltantes, a.titulo)}><Icono nombre="descargas" tam={18} /> {t("Descargar todas")}</button>
          {/if}
          <button class="pildora oscura chica" onclick={() => (editando = { enLinea: true })}><Icono nombre="etiqueta" tam={18} /> {t("Guardar datos en tus archivos")}</button>
          <button class="pildora oscura chica" onclick={elegirCategorias}><Icono nombre="ordenar" tam={18} /> {t("Categorías")}</button>
        </div>
      {/if}
      {#each completo?.faltantes ?? [] as c, i (c.id)}
        <FilaCancion cancion={c} sinPortada alTocar={() => reproducir(completo.faltantes, i, a.titulo)} />
      {/each}
    {/if}
  {:else}
    <div class="hero"><div class="cargando-bloque" style="width:62%;aspect-ratio:1;margin:0 auto"></div></div>
  {/if}
</div>

{#if editando}
  <EditarAlbum album={a} enLinea={editando.enLinea} alCerrar={() => (editando = false)} alGuardar={alGuardarAlbum} />
{/if}

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
  .avance { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 10px; color: var(--tenue); }
  .barra { width: 90px; height: 4px; border-radius: 2px; overflow: hidden; background: rgba(255, 255, 255, 0.15); }
  .barra i { display: block; height: 100%; border-radius: 2px; background: var(--cian); }
  .revision { align-items: center; }
  .girando { width: 18px; height: 18px; border-radius: 50%; border: 2.5px solid var(--borde-fuerte); border-top-color: var(--cian); animation: giro 0.8s linear infinite; flex-shrink: 0; }
  @keyframes giro { to { transform: rotate(360deg); } }
  .botones-revision { display: flex; flex-wrap: wrap; gap: 8px; margin: 2px 0 8px; }
  .chica { height: 38px; padding: 0 16px; font-size: 14px; }
  .acciones { display: flex; gap: 10px; justify-content: center; align-items: center; margin: 20px 0 14px; }
  .acciones .pildora { flex: 1; max-width: 170px; }
  .borrar { color: var(--rojo); }
</style>
