<script>
  import { onMount } from "svelte";
  import { py, tiempo } from "../lib/api.js";
  import { abrir, atras, descargar, mostrarHoja } from "../lib/estado.svelte.js";
  import { canciones as nCanciones, t } from "../lib/idioma.svelte.js";
  import { agrupar, coincide, normalizar } from "../lib/ordenar.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import ListaVirtual from "../componentes/ListaVirtual.svelte";
  import Portada from "../componentes/Portada.svelte";

  // Las canciones de un artista, como en Musicolet: arriba la tira de sus álbumes (tocar uno filtra la lista),
  // los conteos, y el buscador abajo. Es la misma vista para los dos "Ver todas" de la página del artista:
  // - e.soloTuyas (Ver todas de "En tu biblioteca"): solo lo tuyo, al instante y sin internet. Trae e.albumesTuyos.
  // - si no (Ver todas de "Populares"): lo tuyo y lo de YouTube Music juntos. Trae e.lista y e.discos.
  //   Cada disco de la discografía se pide entero (Thriller con sus 9 y Thriller 40 con las suyas, aunque se repitan):
  //   la lista de YouTube trae solo una versión de cada canción, repartida entre ediciones. Sin discografía, esa lista.
  let { e } = $props();
  const soloTuyas = $derived(!!e.soloTuyas);
  const discografia = $derived.by(() => {
    if (e.soloTuyas) return [];
    const v = new Set();
    return (e.discos ?? []).filter((d) => d.browse_id && !v.has(d.browse_id) && v.add(d.browse_id));
  });
  let enLinea = $state.raw(e.enLinea ?? null); // solo sin discografía
  let porDisco = $state.raw(e.porDisco ?? {}); // browse_id → canciones (las que ya llegaron)
  let cargando = $state(!e.soloTuyas && !e.enLinea && !e.porDisco);
  let error = $state(false);
  const listos = $derived(Object.keys(porDisco).length);
  let q = $state(e.q ?? "");
  $effect(() => { e.q = q; });
  let sel = $state(e.sel ?? null); // el álbum elegido en la tira (su clave), o null = todos
  $effect(() => { e.sel = sel; });
  let abiertos = $state(e.abiertos ?? false); // la tira desplegada: todos los álbumes en rejilla
  $effect(() => { e.abiertos = abiertos; });
  let tira = $state();
  /** Recorre la tira casi una pantalla hacia un lado */
  function recorrer(lado) {
    tira?.scrollBy({ left: lado * tira.clientWidth * 0.85, behavior: "smooth" });
  }

  const ORDENES = [["discos", t("Álbum")], ["titulo", t("Título (A–Z)")], ["album", t("Álbum (A–Z)")], ["duracion", t("Duración")]];
  let orden = $state(leerOrden());
  function leerOrden() {
    try { return localStorage.getItem("misiccord_orden_artista") || "discos"; } catch { return "discos"; }
  }
  function ponerOrden(o) {
    orden = o;
    try { localStorage.setItem("misiccord_orden_artista", o); } catch {}
  }
  function opcionesOrden() {
    mostrarHoja({
      titulo: t("Ordenar y agrupar"),
      opciones: ORDENES.map(([id, nombre]) => ({ texto: nombre, icono: orden === id ? "check" : "ordenar", accion: () => ponerOrden(id) })),
    });
  }

  const tuyas = $derived(e.tuyas ?? []);
  const filtrar = (lista) => (q.trim() ? lista.filter((c) => coincide(q, c.titulo, c.album)) : lista);
  /** Cada disco que ya llegó, con todas sus pistas como en su página. Un mismo video puede ser dos pistas
   *  (Rubber Soul Super Deluxe: 68 pistas, 44 videos): la fila se distingue por su lugar en el disco. */
  const completos = $derived(discografia.filter((d) => porDisco[d.browse_id]).map((d) => (
    { d, canciones: porDisco[d.browse_id].map((c, i) => ({ ...c, claveFila: `${d.browse_id}#${i}` })) }
  )));
  const deYouTube = $derived(soloTuyas ? [] : enLinea ?? completos.flatMap((x) => x.canciones));
  // Las tuyas que YouTube no trae (otra versión, otro nombre) también cuentan
  const sueltas = $derived.by(() => {
    const titulos = new Set(deYouTube.map((c) => normalizar(c.titulo)));
    return tuyas.filter((c) => !titulos.has(normalizar(c.titulo)));
  });
  // De dónde sacar año y carátula de un álbum que solo se conoce por nombre
  // (y cómo abrirlo: tu álbum si lo tienes, si no el de YouTube Music con el mismo nombre)
  const conocidos = $derived.by(() => {
    const m = new Map();
    for (const d of e.discos ?? []) m.set(normalizar(d.titulo), { anio: d.anio, portada: d.miniatura, id: d.browse_id });
    for (const a of e.albumesTuyos ?? []) {
      const clave = normalizar(a.nombre);
      m.set(clave, { ...m.get(clave), anio: a.anio || m.get(clave)?.anio, portada: a.portada ?? m.get(clave)?.portada, local: a });
    }
    return m;
  });

  /** Agrupa por el nombre del álbum de cada canción */
  function porNombre(canciones) {
    const grupos = new Map();
    for (const c of canciones) {
      const clave = normalizar(c.album);
      if (!grupos.has(clave)) {
        const d = conocidos.get(clave);
        grupos.set(clave, { clave: "n|" + clave, titulo: c.album || t("Sin álbum"), canciones: [], anio: d?.anio || c.anio || "", portada: d?.portada ?? c.portada, id: d?.id, local: d?.local });
      }
      grupos.get(clave).canciones.push(c);
    }
    return [...grupos.values()];
  }
  /** Los álbumes, del más nuevo al más viejo: cada disco de la discografía entero, y lo tuyo que no esté en ninguno.
   *  Es la tira de arriba y, ordenado por álbum, la lista misma. */
  const albumes = $derived(
    (enLinea ? porNombre([...sueltas, ...enLinea]) : [
      ...completos.map(({ d, canciones }) => ({ clave: d.browse_id, titulo: d.titulo, tipo: d.tipo, canciones, anio: d.anio, portada: d.miniatura, id: d.browse_id })),
      ...porNombre(sueltas),
    ]).sort((x, y) => String(y.anio).localeCompare(String(x.anio)) || x.titulo.localeCompare(y.titulo)));
  const elegido = $derived(sel ? albumes.find((g) => g.clave === sel) ?? null : null);

  // Sin agrupar por disco, la misma grabación (mismo video) sale una vez aunque venga en dos ediciones
  const todas = $derived.by(() => {
    const vistos = new Set();
    return [...(elegido ? elegido.canciones : [...sueltas, ...deYouTube])].filter((c) => {
      const clave = c.db_id ?? c.id;
      return !vistos.has(clave) && vistos.add(clave);
    });
  });
  const vistas = $derived(filtrar(todas));
  const grupos = $derived(
    orden === "discos" ? (elegido ? [elegido] : albumes).map((g) => ({ ...g, canciones: filtrar(g.canciones) })).filter((g) => g.canciones.length)
    : orden === "duracion" ? (vistas.length ? [{ titulo: "", canciones: [...vistas].sort((x, y) => (y.duracion ?? 0) - (x.duracion ?? 0)) }] : [])
    : agrupar(vistas, orden));
  const plana = $derived(grupos.flatMap((g) => g.canciones)); // en el orden en que se ven: así suena la cola
  const conDisco = $derived(orden === "discos" || orden === "album");
  const duracion = $derived(plana.reduce((s, c) => s + (c.duracion || 0), 0));

  /** 4:21:14, como Musicolet */
  function largo(segundos) {
    const s = Math.round(segundos);
    return s < 3600 ? tiempo(s) : `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  }

  /** Como en la página del álbum: lo tuyo si es tuyo, si no el de YouTube Music */
  function abrirDisco(g) {
    if (g.local) abrir("album", { local: g.local });
    else if (g.id) abrir("album", { id: g.id });
  }
  /** Lo que te falta de ese disco (sin repetir: en un disco el mismo video puede ser dos pistas) */
  function faltanDe(g) {
    const vistos = new Set();
    return g.canciones.filter((c) => !c.local && !c.ruta && c.id && !vistos.has(c.id) && vistos.add(c.id));
  }

  /** La lista de YouTube con una versión de cada canción: sin discografía, o si no llegó ningún disco */
  async function traerLista() {
    cargando = true;
    try {
      enLinea = e.enLinea = (await py("artista_canciones", { lista: e.lista })).canciones;
    } catch {
      error = true;
    } finally {
      cargando = false;
    }
  }

  async function cargar() {
    error = false;
    if (!discografia.length) return traerLista();
    // De 4 en 4: cada disco aparece en cuanto llega. Los que ya están (al volver a esta vista) no se piden otra vez
    const pendientes = discografia.filter((d) => !porDisco[d.browse_id]);
    let fallas = 0;
    cargando = !listos;
    async function trabajador() {
      for (let d = pendientes.shift(); d; d = pendientes.shift()) {
        try {
          const { canciones } = await py("disco_canciones", { browse_id: d.browse_id });
          porDisco = e.porDisco = { ...porDisco, [d.browse_id]: canciones };
          if (enLinea) enLinea = e.enLinea = null; // Reintentar sí funcionó: ya no hace falta la lista de antes
          cargando = false;
        } catch {
          fallas++;
        }
      }
    }
    await Promise.all(Array.from({ length: 4 }, trabajador));
    cargando = false;
    // Ninguno llegó (sin internet, o Python todavía sin disco_canciones porque no se reinició): mejor la lista de antes que nada
    if (fallas && !listos && e.lista) return traerLista();
    error = fallas > 0;
  }
  onMount(() => {
    if (soloTuyas || e.enLinea) return;
    if (!discografia.length || listos < discografia.length) cargar();
  });
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
    <h1 class="cortar">{e.nombre}</h1>
  </header>

  {#if albumes.length > 1}
    <!-- En escritorio no hay cómo deslizar con el dedo: flechas para recorrerla y "Ver todos" para verlos todos de golpe -->
    <div class="titulo-tira">
      {t("Álbumes")}
      <span class="controles">
        {#if !abiertos}
          <button class="redondo chico solo-raton" onclick={() => recorrer(-1)} aria-label={t("Anteriores")} title={t("Anteriores")}><Icono nombre="atras" tam={18} /></button>
          <button class="redondo chico solo-raton" onclick={() => recorrer(1)} aria-label={t("Siguientes")} title={t("Siguientes")}><Icono nombre="atras" tam={18} clase="volteado" /></button>
        {/if}
        <button class="ver-todos" onclick={() => (abiertos = !abiertos)}>{abiertos ? t("Ver menos") : t("Ver todos")}</button>
      </span>
    </div>
    <div class="tira" class:abierta={abiertos} bind:this={tira} role="listbox" aria-label={t("Álbumes")}>
      <button class="mosaico todos" class:activo={!elegido} role="option" aria-selected={!elegido} onclick={() => (sel = null)}>
        <span class="nombre-todos">{t("Todos los álbumes")}</span>
      </button>
      {#each albumes as g (g.clave)}
        <button class="mosaico" class:activo={elegido?.clave === g.clave} role="option" aria-selected={elegido?.clave === g.clave}
          title={g.titulo} onclick={() => (sel = elegido?.clave === g.clave ? null : g.clave)}>
          <Portada url={g.portada} tam="100%" radio="0" icono="disco" />
          <span class="nombre">{g.titulo}</span>
        </button>
      {/each}
    </div>
  {/if}

  <div class="resumen">
    <p class="tenue">
      {#if albumes.length}{elegido ? `${t("1 de {n} álbumes", { n: albumes.length })}` : t("{n} álbumes", { n: albumes.length })}{/if}
      {#if !enLinea && discografia.length && listos < discografia.length && !error}
        <span class="chico"> · {t("Trayendo discos: {n} de {total}", { n: listos, total: discografia.length })}</span>
      {/if}
    </p>
    <p class="tenue">
      {nCanciones(plana.length)}
      {#if duracion}<span class="reloj"><Icono nombre="reloj" tam={15} /> {largo(duracion)}</span>{/if}
    </p>
  </div>

  <div class="barra">
    <button class="redondo" disabled={!plana.length} onclick={() => reproducir(plana, 0, e.nombre)} aria-label={t("Reproducir")} title={t("Reproducir")}><Icono nombre="play" relleno tam={22} /></button>
    <button class="redondo" disabled={!plana.length} onclick={() => reproducirAleatorio(plana, e.nombre)} aria-label={t("Aleatorio")} title={t("Aleatorio")}><Icono nombre="aleatorio" tam={22} /></button>
    <button class="redondo" onclick={opcionesOrden} aria-label={t("Ordenar y agrupar")} title={t("Ordenar y agrupar")}><Icono nombre="ordenar" tam={22} /></button>
  </div>

  <!-- Lo tuyo se ve desde el principio; los bloques de carga, solo si todavía no hay nada que enseñar -->
  {#if cargando && !grupos.length}
    {#each Array(6) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
  {:else}
    {#if error}
      <p class="tenue">
        {!enLinea && listos ? t("Faltaron {n} discos.", { n: discografia.length - listos }) : t("No se pudieron traer sus canciones.")}
        <button class="reintentar" onclick={cargar}>{t("Reintentar")}</button>
      </p>
    {/if}
    {#each grupos as g (g.clave ?? g.titulo)}
      {#if orden === "discos"}
        {@const faltan = faltanDe(g)}
        <div class="grupo disco">
          <button class="abrir-disco" disabled={!g.local && !g.id} onclick={() => abrirDisco(g)} title={g.local || g.id ? t("Ver álbum") : null}>
            <span class="cortar">{g.titulo}</span><small>{[g.tipo === "Sencillo" ? t("Sencillo") : "", g.anio].filter(Boolean).join(" · ")}</small>
          </button>
          {#if faltan.length}
            <button class="redondo bajar" onclick={() => descargar(faltan, g.titulo)} aria-label={t("Descargar álbum")} title={t("Descargar álbum")}><Icono nombre="descargas" tam={19} /></button>
          {/if}
        </div>
      {:else if g.titulo}
        <div class="grupo">{g.titulo}</div>
      {/if}
      <ListaVirtual items={g.canciones} clave={(c) => c.claveFila ?? c.db_id ?? c.id} tipo="artista-canciones">
        {#snippet fila(c)}
          <FilaCancion cancion={c} alTocar={() => reproducir(plana, plana.indexOf(c), e.nombre)} />
        {/snippet}
      </ListaVirtual>
    {:else}
      {#if q.trim()}<p class="tenue">{t("Nada con “{q}”.", { q: q.trim() })}</p>{/if}
    {/each}
  {/if}

  <div class="pie">
  <form class="buscador" role="search" onsubmit={(ev) => { ev.preventDefault(); document.activeElement?.blur(); }}>
    <Icono nombre="buscar" tam={19} />
    <input bind:value={q} placeholder={t("Buscar en esta lista…")} enterkeyhint="search" />
    {#if q}<button type="button" onclick={() => (q = "")} aria-label={t("Borrar búsqueda")}><Icono nombre="cerrar" tam={17} /></button>{/if}
  </form>
  </div>
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  header { display: flex; align-items: center; gap: 12px; }
  h1 { margin: 0; min-width: 0; font-size: 24px; font-weight: 800; }
  .titulo-tira { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 18px 0 10px; font-size: 16px; font-weight: 800; }
  .controles { display: flex; align-items: center; gap: 4px; }
  .redondo.chico { width: 32px; height: 32px; background: var(--tarjeta); }
  .controles :global(.volteado) { transform: scaleX(-1); }
  .ver-todos { margin-left: 4px; font-size: 13.5px; font-weight: 700; color: var(--tenue); }
  .ver-todos:hover { color: var(--texto); }
  /* Las flechas, solo con ratón: con el dedo la tira se desliza sola */
  @media (hover: none) { .solo-raton { display: none; } }
  .tira.abierta { flex-wrap: wrap; overflow: visible; margin: 0; padding: 0 0 4px; }
  /* La tira de álbumes: deslizable, con la orilla de la pantalla como en los carruseles */
  .tira {
    display: flex; gap: 10px; overflow-x: auto; scrollbar-width: none;
    margin: 0 calc(-1 * var(--margen)); padding: 0 var(--margen) 4px; scroll-padding: 0 var(--margen);
  }
  .tira::-webkit-scrollbar { display: none; }
  .mosaico {
    position: relative; flex: 0 0 92px; width: 92px; height: 92px; border-radius: 10px; overflow: hidden;
    border: 2px solid var(--borde); background: var(--tarjeta); padding: 0;
  }
  .mosaico.activo { border-color: var(--cian); }
  .mosaico::after { content: ""; position: absolute; z-index: 2; left: 8px; right: 8px; bottom: 5px; height: 3px; border-radius: 2px; background: transparent; }
  .mosaico.activo::after { background: var(--cian); }
  .mosaico :global(.portada) { position: absolute; inset: 0; }
  .nombre {
    position: absolute; z-index: 1; left: 0; right: 0; bottom: 0; padding: 18px 6px 11px; text-align: center;
    font-size: 12.5px; font-weight: 800; line-height: 1.15; color: #fff;
    background: linear-gradient(to bottom, transparent, rgba(0, 0, 0, 0.82) 55%);
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }
  .todos { display: grid; place-items: center; }
  .nombre-todos { padding: 0 8px; font-size: 13.5px; font-weight: 800; line-height: 1.2; }
  .resumen { margin: 12px 0 0; }
  .resumen p { margin: 4px 0 0; font-size: 15px; }
  .chico { font-size: 12.5px; }
  .reloj { display: inline-flex; align-items: center; gap: 4px; margin-left: 14px; }
  .barra { display: flex; justify-content: flex-end; gap: 6px; margin: 6px 0 2px; padding-bottom: 8px; border-bottom: 1px solid var(--borde); }
  .grupo { display: flex; align-items: baseline; gap: 8px; padding: 14px 0 4px; font-size: 15px; font-weight: 800; color: var(--cian); }
  .grupo small { color: var(--tenue); font-size: 12.5px; font-weight: 600; }
  .grupo.disco { align-items: center; justify-content: space-between; padding: 10px 0 2px; }
  .abrir-disco { min-width: 0; display: flex; align-items: baseline; gap: 8px; padding: 4px 0; color: inherit; font: inherit; text-align: left; }
  .abrir-disco:not(:disabled):hover span { text-decoration: underline; }
  .abrir-disco:disabled { opacity: 1; cursor: default; }
  .abrir-disco small { flex-shrink: 0; }
  .redondo.bajar { flex-shrink: 0; width: 36px; height: 36px; color: var(--tenue); }
  .redondo.bajar:hover { color: var(--texto); }
  .reintentar { color: var(--cian); font-weight: 700; }
  /* El buscador va abajo y se queda a la mano, como en Musicolet: encima de las pestañas y del reproductor chico */
  /* El pie con el buscador: sticky cuenta desde el padding de main, que ya deja libre el lugar de las pestañas y del
     reproductor chico; se baja hasta tocarlos para que el degradado tape la lista que pasa por debajo */
  .pie {
    position: sticky; bottom: -28px; z-index: 4;
    margin: 6px calc(-1 * var(--margen)) 0; padding: 30px var(--margen) 28px;
    background: linear-gradient(to bottom, transparent, var(--fondo) 55%);
    pointer-events: none;
  }
  .buscador {
    pointer-events: auto;
    display: flex; align-items: center; gap: 10px; height: 46px; padding: 0 14px; border-radius: 14px;
    background: var(--tarjeta); border: 1px solid var(--borde); color: var(--tenue);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
  }
  .buscador:focus-within { border-color: var(--cian); }
  .buscador input { flex: 1; min-width: 0; height: 100%; border: 0; outline: 0; background: transparent; color: var(--texto); font-size: 15.5px; }
  .buscador button { display: grid; place-items: center; color: var(--tenue); }
</style>
