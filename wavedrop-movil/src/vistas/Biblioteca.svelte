<script module>
  // Lo último que respondió Python, por carpeta: volver a la pestaña no espera nada. Va aquí y no en `e` porque
  // irPestana crea una entrada nueva, y porque `nav` es estado profundo: miles de canciones en Proxies tardan
  // segundos en ordenarse en el cel.
  const memoria = new Map(); // carpeta → { datos, carpetas, version }
</script>

<script>
  import { onMount } from "svelte";
  import { fade, scale } from "svelte/transition";
  import { alEvento, py } from "../lib/api.js";
  import { abrir, aviso, completarDatos, mostrarHoja, ui } from "../lib/estado.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import { aBody } from "../lib/aBody.js";
  import { pedirEliminar } from "../lib/eliminar.js";
  import { compartir } from "../lib/compartir.js";
  import { menuCancion } from "../lib/menuCancion.js";
  import { canciones, t } from "../lib/idioma.svelte.js";
  import { agrupar, agruparLista, coincide, ORDENES, ORDENES_LISTA } from "../lib/ordenar.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import ListaVirtual from "../componentes/ListaVirtual.svelte";
  import Portada from "../componentes/Portada.svelte";
  import Tarjeta from "../componentes/Tarjeta.svelte";

  let { e } = $props();
  let pestana = $state(e.pestana ?? (e.vista === "biblioteca_albumes" ? "albumes" : "canciones"));
  $effect(() => { e.pestana = pestana; });
  let creando = $state(false);
  let nombre = $state("");
  // Filtro por carpeta de música ("" = todas); se recuerda al volver a esta vista
  let filtro = $state(e.filtro ?? "");
  let b = $state.raw(memoria.get(filtro)?.datos ?? null);
  const idDe = (c) => c.db_id;

  // ---------- Buscar, ordenar y agrupar ----------
  // Lo tuyo se filtra al instante; lo que no tienes se busca en YouTube Music cuando dejas de escribir.
  let consulta = $state(e.q ?? "");
  $effect(() => { e.q = consulta; });
  const texto = $derived(consulta.trim());

  let orden = $state(leerOrden());
  function leerOrden() {
    try { return localStorage.getItem("misiccord_orden") || "titulo"; } catch { return "titulo"; }
  }
  function ponerOrden(o) {
    orden = o;
    try { localStorage.setItem("misiccord_orden", o); } catch {}
  }
  // Álbumes, artistas, playlists y géneros: cada pestaña recuerda el suyo
  let ordenLista = $state(leerOrdenLista());
  function leerOrdenLista() {
    try { return JSON.parse(localStorage.getItem("misiccord_ordenes") || "{}"); } catch { return {}; }
  }
  function ponerOrdenLista(o) {
    ordenLista = { ...ordenLista, [pestana]: o };
    try { localStorage.setItem("misiccord_ordenes", JSON.stringify(ordenLista)); } catch {}
  }
  const ordenDe = (tab) => ordenLista[tab] ?? "nombre";
  function opcionesOrden() {
    const enCanciones = pestana === "canciones";
    const lista = enCanciones ? ORDENES : ORDENES_LISTA[pestana];
    const elegido = enCanciones ? orden : ordenDe(pestana);
    mostrarHoja({
      titulo: t("Ordenar y agrupar"),
      opciones: lista.map(([id, nombre]) => ({
        texto: nombre, icono: elegido === id ? "check" : "ordenar", accion: () => (enCanciones ? ponerOrden(id) : ponerOrdenLista(id)),
      })),
    });
  }

  const cancionesVistas = $derived(b ? (texto ? b.canciones.filter((c) => coincide(texto, c.titulo, c.artista, c.album)) : b.canciones) : []);
  const grupos = $derived(agrupar(cancionesVistas, orden));
  const plana = $derived(grupos.flatMap((g) => g.canciones)); // en el orden en que se ven: así suena la cola
  const gruposAlbumes = $derived(agruparLista(b ? b.albumes.filter((a) => !texto || coincide(texto, a.nombre, a.artista)) : [], ordenDe("albumes")));
  const gruposArtistas = $derived(agruparLista(b ? b.artistas.filter((a) => !texto || coincide(texto, a.nombre)) : [], ordenDe("artistas")));
  const gruposPlaylists = $derived(agruparLista(b ? b.playlists.filter((x) => !texto || coincide(texto, x.nombre)) : [], ordenDe("playlists")));
  const gruposGeneros = $derived(agruparLista(b ? (b.generos ?? []).filter((x) => !texto || coincide(texto, x.nombre)) : [], ordenDe("generos")));
  const gruposVistos = $derived({ canciones: grupos, albumes: gruposAlbumes, artistas: gruposArtistas, playlists: gruposPlaylists, generos: gruposGeneros }[pestana]);
  const cuantos = $derived(pestana === "canciones" ? plana.length : gruposVistos.reduce((n, g) => n + g.items.length, 0));
  const porLetra = $derived(pestana === "canciones" ? orden === "titulo" || orden === "artista" : ["nombre", "artista"].includes(ordenDe(pestana)));

  let enLinea = $state([]);
  let buscandoLinea = $state(false);
  let pedidoLinea = 0;
  let esperaLinea;
  $effect(() => {
    const consultaLinea = texto;
    clearTimeout(esperaLinea);
    if (consultaLinea.length < 2) {
      enLinea = [];
      buscandoLinea = false;
      return;
    }
    esperaLinea = setTimeout(async () => {
      const yo = ++pedidoLinea;
      buscandoLinea = true;
      try {
        const r = await py("buscar", { q: consultaLinea, tipo: "canciones" });
        // Solo las que no tienes descargadas (las tuyas ya salen arriba)
        if (yo === pedidoLinea) enLinea = (r.canciones ?? []).filter((c) => !c.ruta).slice(0, 8);
      } catch {
        if (yo === pedidoLinea) enLinea = [];
      } finally {
        if (yo === pedidoLinea) buscandoLinea = false;
      }
    }, 450);
  });

  // Índice A–Z a un lado (ordenado por nombre, sin búsqueda): toca o desliza el dedo para saltar a una letra
  const indice = $derived(!texto && porLetra && cuantos > 25 ? gruposVistos.map((g) => g.titulo) : []);
  // Mientras el dedo está en el índice, una burbuja grande junto a él muestra la letra (el dedo tapa la del índice)
  let enIndice = null; // pointerId del dedo que arrastra (otro dedo o el mouse que pasa no cuentan)
  let burbuja = $state(null); // { letra, y, x }
  function tocarIndice(ev) {
    if (ev.type === "pointerdown") {
      enIndice = ev.pointerId;
      try { ev.currentTarget.setPointerCapture(ev.pointerId); } catch {}
    }
    if (enIndice !== ev.pointerId) return;
    // Con el dedo capturado, elementFromPoint fuera de las letras no da nada: se busca la más cercana por altura
    const spans = [...ev.currentTarget.querySelectorAll("[data-letra]")];
    let cerca = null, distancia = Infinity;
    for (const sp of spans) {
      const caja = sp.getBoundingClientRect();
      const d = Math.abs(caja.top + caja.height / 2 - ev.clientY);
      if (d < distancia) { distancia = d; cerca = sp; }
    }
    const letra = cerca?.dataset.letra;
    if (!letra) return;
    const caja = cerca.getBoundingClientRect();
    if (burbuja?.letra !== letra) {
      document.getElementById(`grupo-${letra}`)?.scrollIntoView({ block: "start" });
      navigator.vibrate?.(8);
    }
    burbuja = { letra, y: caja.top + caja.height / 2, x: caja.left };
  }
  function soltarIndice(ev) {
    if (enIndice !== ev.pointerId) return;
    enIndice = null;
    burbuja = null;
  }

  let pedido = 0;

  async function cargar() {
    const yo = ++pedido;
    const pedida = ui.version;
    const [datos, c] = await Promise.all([py("biblioteca", { carpeta: filtro }), py("carpetas_biblioteca")]);
    if (yo !== pedido) return;
    carpetas = c;
    if (filtro && !c.carpetas.some((x) => x.ruta === filtro)) { // la carpeta filtrada se quitó
      filtro = "";
      e.filtro = "";
      return cargar();
    }
    b = datos;
    memoria.set(filtro, { datos, carpetas: c, version: pedida });
  }
  function filtrar(ruta) {
    if (ruta === filtro) return;
    filtro = ruta;
    e.filtro = ruta;
    b = memoria.get(ruta)?.datos ?? b;
    salirSeleccion();
    cargar();
  }
  onMount(() => { if (memoria.get(filtro)?.version !== ui.version) cargar(); });
  let version = ui.version;
  $effect(() => { if (ui.version !== version) { version = ui.version; cargar(); } });

  async function crear() {
    if (!nombre.trim()) return;
    try {
      await py("crear_playlist", { nombre: nombre.trim() });
      aviso(t("Playlist “{nombre}” creada", { nombre: nombre.trim() }), "ok");
      nombre = "";
      creando = false;
      cargar();
    } catch {
      aviso(t("Ya existe una playlist con ese nombre"), "error");
    }
  }

  // ---------- Carpetas de música que ya tienes ----------
  let panelCarpetas = $state(false);
  let carpetas = $state(memoria.get(filtro)?.carpetas ?? null); // { carpetas: [...], android }
  let explorando = $state(null);    // Android: { ruta, padre, carpetas } mientras eliges una carpeta
  let escaneando = $state(false);
  let revisadas = $state(0);

  onMount(() => {
    const quitar = [
      alEvento("escaneo", (d) => { revisadas = d.revisadas; }),
      alEvento("biblioteca", () => { escaneando = false; if (panelCarpetas) cargarCarpetas(); }),
    ];
    return () => quitar.forEach((f) => f());
  });

  async function cargarCarpetas() {
    carpetas = await py("carpetas_biblioteca");
  }
  function abrirPanel() {
    panelCarpetas = true;
    explorando = null;
    cargarCarpetas();
  }
  async function agregarCarpeta(ruta) {
    try {
      carpetas = await py("agregar_carpeta_biblioteca", { ruta });
      explorando = null;
      revisadas = 0;
      escaneando = true;
      aviso(t("Leyendo tu música…"), "ok");
    } catch (err) {
      aviso(err.message, "error");
    }
  }
  async function elegirCarpetaMusica() {
    if (!carpetas.android) {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const ruta = await open({ directory: true, title: t("¿Dónde está tu música?") });
      if (ruta) agregarCarpeta(ruta);
      return;
    }
    // Android: leer carpetas públicas pide "Acceso a todos los archivos"
    const { invoke } = await import("@tauri-apps/api/core");
    if (!(await invoke("permiso_archivos", { pedir: false }))) {
      aviso(t("Activa “Permitir acceso a todos los archivos” para Misiccord y regresa a la app"));
      await invoke("permiso_archivos", { pedir: true });
      const alVolver = async () => {
        if (document.visibilityState !== "visible") return;
        document.removeEventListener("visibilitychange", alVolver);
        if (await invoke("permiso_archivos", { pedir: false })) irA();
        else aviso(t("Sin ese permiso no puedo leer tu música"), "error");
      };
      document.addEventListener("visibilitychange", alVolver);
      return;
    }
    irA();
  }
  async function irA(ruta) {
    try {
      explorando = await py("subcarpetas", { ruta });
    } catch (err) {
      aviso(err.message, "error");
    }
  }
  async function quitarCarpeta(c) {
    carpetas = await py("quitar_carpeta_biblioteca", { ruta: c.ruta });
    aviso(t("Carpeta quitada; tus archivos siguen donde estaban"), "ok");
  }
  const nombreCarpeta = (ruta) => ruta.split(/[\\/]/).filter(Boolean).pop() || ruta;

  // ---------- Lista o cuadrícula ----------
  // Cada pestaña recuerda la suya (los álbumes empiezan en cuadrícula, lo demás en lista)
  const VISTAS_INICIALES = { canciones: "lista", albumes: "cuadricula", artistas: "lista", playlists: "lista", generos: "lista" };
  let vistas = $state(leerVistas());
  function leerVistas() {
    try { return { ...VISTAS_INICIALES, ...JSON.parse(localStorage.getItem("misiccord_vista_biblioteca") || "{}") }; }
    catch { return { ...VISTAS_INICIALES }; }
  }
  const enCuadricula = $derived(vistas[pestana] === "cuadricula");
  // Cuántas columnas tiene el mosaico: cada pestaña recuerda las suyas
  const MAX_COLUMNAS = 8;
  let columnas = $state(leerColumnas());
  function leerColumnas() {
    try { return JSON.parse(localStorage.getItem("misiccord_columnas") || "{}"); } catch { return {}; }
  }
  const nColumnas = $derived(columnas[pestana] ?? (ui.amplio ? 6 : pestana === "albumes" ? 2 : 3));
  function cambiarColumnas(paso) {
    columnas = { ...columnas, [pestana]: Math.max(2, Math.min(MAX_COLUMNAS, nColumnas + paso)) };
    try { localStorage.setItem("misiccord_columnas", JSON.stringify(columnas)); } catch {}
  }
  // ListaVirtual mide por tipo: con otras columnas la fila mide distinto
  const tipoFila = $derived(`${pestana}-${enCuadricula ? `cuadricula-${nColumnas}` : "lista"}${seleccionando ? "-eleccion" : ""}`);
  function alternarVista() {
    vistas = { ...vistas, [pestana]: enCuadricula ? "lista" : "cuadricula" };
    try { localStorage.setItem("misiccord_vista_biblioteca", JSON.stringify(vistas)); } catch {}
  }

  const pestanas = [["canciones", t("Canciones")], ["albumes", t("Álbumes")], ["artistas", t("Artistas")], ["generos", t("Géneros")], ["playlists", t("Playlists")]];

  // ---------- El encabezado reaparece al subir ----------
  // Al bajar se esconde para dejarle lugar a la lista; con el primer gesto hacia arriba regresa, estés donde estés.
  let cabeceraVisible = $state(true);
  let altoCabecera = $state(0);
  onMount(() => {
    const principal = document.querySelector("main");
    let ultimo = principal.scrollTop;
    function alDesplazar() {
      const y = principal.scrollTop;
      if (Math.abs(y - ultimo) < 6 || enIndice !== null) return;
      cabeceraVisible = y < ultimo || y < altoCabecera;
      ultimo = y;
    }
    principal.addEventListener("scroll", alDesplazar, { passive: true });
    return () => principal.removeEventListener("scroll", alDesplazar);
  });

  // ---------- Selección múltiple para compartir/exportar o borrar ----------
  // Se pueden juntar canciones, álbumes, artistas y playlists (cambiando de pestaña sin perder lo elegido).
  // Borrar solo aplica a canciones sueltas.
  let seleccionando = $state(false);
  let elegidas = $state(new Set());              // db_id de canciones
  let elegidos = $state(new Set());              // claves "album:…", "artista:…", "playlist:…"
  const totalElegido = $derived(elegidas.size + elegidos.size);

  function salirSeleccion() {
    seleccionando = false;
    elegidas = new Set();
    elegidos = new Set();
  }
  const claveAlbum = (a) => `album:${a.nombre}|${a.grupo}|${a.artista}`;
  function alternarElegido(clave) {
    const s = new Set(elegidos);
    s.has(clave) ? s.delete(clave) : s.add(clave);
    elegidos = s;
  }

  const contador = $derived(
    pestana === "canciones" ? (texto ? t("{n} de {total} canciones", { n: plana.length, total: b?.canciones.length ?? 0 }) : canciones(plana.length))
    : pestana === "albumes" ? t("{n} álbumes", { n: cuantos })
    : pestana === "artistas" ? t("{n} artistas", { n: cuantos })
    : pestana === "generos" ? t("{n} géneros", { n: cuantos })
    : t("{n} playlists", { n: cuantos }));

  let preparando = $state(false);
  async function compartirElegidas() {
    preparando = true;
    try {
      const lista = [];
      const grupos = [];
      const sueltas = b.canciones.filter((c) => elegidas.has(c.db_id));
      if (sueltas.length) {
        lista.push(...sueltas);
        grupos.push({ carpeta: "", rutas: sueltas.map((c) => c.ruta), lista: false });
      }
      for (const a of b.albumes.filter((x) => elegidos.has(claveAlbum(x)))) {
        const { canciones } = await py("album_local", { nombre: a.nombre, artista: a.artista, grupo: a.grupo });
        lista.push(...canciones);
        grupos.push({ carpeta: a.artista ? `${a.artista} - ${a.nombre}` : a.nombre, rutas: canciones.map((c) => c.ruta), lista: false });
      }
      for (const a of b.artistas.filter((x) => elegidos.has(`artista:${x.nombre}`))) {
        const { canciones } = await py("artista_local", { nombre: a.nombre });
        lista.push(...canciones);
        grupos.push({ carpeta: a.nombre, rutas: canciones.map((c) => c.ruta), lista: false });
      }
      for (const p of b.playlists.filter((x) => elegidos.has(`playlist:${x.id}`))) {
        const { canciones } = await py("playlist", { id: p.id });
        const suyas = canciones.filter((c) => c.ruta);
        lista.push(...suyas);
        grupos.push({ carpeta: p.nombre, rutas: suyas.map((c) => c.ruta), lista: true });
      }
      const titulo = totalElegido === 1 && sueltas.length === 1
        ? sueltas[0].titulo
        : t("Compartir {n}", { n: totalElegido === 1 ? t("1 elemento") : t("{n} elementos", { n: totalElegido }) });
      await compartir(lista, { titulo, grupos: grupos.filter((g) => g.rutas.length) });
    } catch (err) {
      aviso(err.message, "error");
    } finally {
      preparando = false;
    }
  }
  function alternarElegida(id) {
    const s = new Set(elegidas);
    s.has(id) ? s.delete(id) : s.add(id);
    elegidas = s;
  }
  const todas = $derived(plana.length > 0 && elegidas.size === plana.length);
  function alternarTodas() {
    elegidas = todas ? new Set() : new Set(plana.map((c) => c.db_id));
  }
  function eliminarElegidas() {
    const rutas = new Set(b.canciones.filter((c) => elegidas.has(c.db_id)).map((c) => c.ruta));
    pedirEliminar({
      objetivo: { db_ids: [...elegidas] }, cuantas: elegidas.size,
      titulo: elegidas.size === 1 ? t("la canción elegida") : canciones(elegidas.size),
      seBorra: (c) => rutas.has(c.ruta),
      alTerminar: (r) => r && salirSeleccion(),
    });
  }

  function opcionesArtista(a) {
    mostrarHoja({
      titulo: a.nombre, subtitulo: t("{n} descargadas", { n: canciones(a.canciones) }),
      opciones: [
        { texto: t("Reproducir"), icono: "play",
          accion: async () => reproducir((await py("artista_local", { nombre: a.nombre })).canciones, 0, a.nombre) },
        { texto: t("Ver en YouTube Music"), icono: "persona", accion: () => abrir("artista", { nombre: a.nombre }) },
        { texto: t("Eliminar todas sus canciones"), icono: "basura", peligro: true, accion: () => pedirEliminar({
            objetivo: { artista: a.nombre }, cuantas: a.canciones, titulo: t("todo de {nombre}", a),
            seBorra: (c) => (c.artista || "").toLowerCase().startsWith(a.nombre.toLowerCase()) }) },
      ],
    });
  }
</script>

<div class="vista" style:--columnas={nColumnas} style:--arriba="{cabeceraVisible ? altoCabecera : 0}px">
  <div class="cabecera" class:oculta={!cabeceraVisible} bind:clientHeight={altoCabecera}>
  <header>
    <h1 class="titulo-vista">{t("Biblioteca")}</h1>
    <div class="botones">
      <button class="redondo" onclick={() => abrir("estadisticas")} aria-label={t("Tus estadísticas")} title={t("Tus estadísticas")}><Icono nombre="estadisticas" tam={24} /></button>
      <button class="redondo" onclick={alternarVista} aria-label={enCuadricula ? t("Ver como lista") : t("Ver como cuadrícula")}
        title={enCuadricula ? t("Ver como lista") : t("Ver como cuadrícula")}><Icono nombre={enCuadricula ? "lista" : "cuadricula"} tam={22} /></button>
      <button class="redondo" onclick={abrirPanel} aria-label={t("Carpetas de música")} title={t("Carpetas de música")}><Icono nombre="carpeta" tam={24} /></button>
      <button class="redondo" class:activo-cian={seleccionando} onclick={() => (seleccionando ? salirSeleccion() : (seleccionando = true))}
        aria-label={t("Compartir o exportar")} title={t("Compartir o exportar")}><Icono nombre="compartir" tam={22} /></button>
    </div>
  </header>
  <form class="buscador" role="search" onsubmit={(ev) => { ev.preventDefault(); document.activeElement?.blur(); }}>
    <Icono nombre="buscar" tam={19} />
    <input bind:value={consulta} placeholder={t("Busca en tu biblioteca y en YouTube Music")} enterkeyhint="search" />
    {#if buscandoLinea}<span class="girando"></span>{/if}
    {#if consulta}<button type="button" onclick={() => (consulta = "")} aria-label={t("Borrar búsqueda")}><Icono nombre="cerrar" tam={17} /></button>{/if}
  </form>
  {#if escaneando}
    <p class="tenue leyendo">{t("Leyendo tu música…")} {revisadas ? t("{n} canciones revisadas", { n: revisadas }) : ""}</p>
  {/if}
  <div class="chips">
    {#each pestanas as [id, texto]}
      <button class="chip" class:activo={pestana === id} onclick={() => (pestana = id)}>{texto}</button>
    {/each}
  </div>
  {#if carpetas?.carpetas.length > 1}
    <div class="chips carpetas" role="group" aria-label={t("Filtrar por carpeta")}>
      <button class="chip" class:activo={!filtro} onclick={() => filtrar("")}>{t("Todas")}</button>
      {#each carpetas.carpetas as c (c.ruta)}
        <button class="chip" class:activo={filtro === c.ruta} onclick={() => filtrar(c.ruta)} title={c.ruta}>
          <Icono nombre="carpeta" tam={14} /> {nombreCarpeta(c.ruta)} <small>{c.canciones}</small>
        </button>
      {/each}
    </div>
  {/if}
  {#if b}
    <div class="acciones">
      {#if seleccionando && pestana === "canciones"}
        <button class="texto-boton" onclick={alternarTodas}>{todas ? t("Quitar todas") : t("Elegir todas")}</button>
        <button class="pildora oscura chica" onclick={salirSeleccion}>{t("Listo")}</button>
      {:else}
        <span class="tenue contador">{contador}</span>
        <div class="botones">
          {#if enCuadricula}
            <div class="columnas" role="group" aria-label={t("Columnas")}>
              <button onclick={() => cambiarColumnas(-1)} disabled={nColumnas <= 2} aria-label={t("Menos columnas")}>−</button>
              <span>{nColumnas}</span>
              <button onclick={() => cambiarColumnas(1)} disabled={nColumnas >= MAX_COLUMNAS} aria-label={t("Más columnas")}>+</button>
            </div>
          {/if}
          <button class="redondo" onclick={opcionesOrden} aria-label={t("Ordenar y agrupar")} title={t("Ordenar y agrupar")}>
            <Icono nombre="ordenar" tam={22} />
          </button>
          {#if pestana === "canciones"}
            <button class="redondo" onclick={() => (seleccionando = true)} aria-label={t("Seleccionar canciones")} title={t("Seleccionar")}>
              <Icono nombre="seleccionar" tam={22} />
            </button>
            {#if enCuadricula}
              <button class="redondo" disabled={!plana.length} onclick={() => reproducirAleatorio(plana, t("Tu biblioteca"))} aria-label={t("Aleatorio")} title={t("Aleatorio")}>
                <Icono nombre="aleatorio" tam={22} />
              </button>
            {:else}
              <button class="pildora oscura chica" disabled={!plana.length} onclick={() => reproducirAleatorio(plana, t("Tu biblioteca"))}>
                <Icono nombre="aleatorio" tam={18} /> {t("Aleatorio")}
              </button>
            {/if}
          {:else if pestana === "playlists" && !seleccionando}
            <button class="redondo" class:activo-cian={creando} onclick={() => (creando = !creando)} aria-label={t("Nueva playlist")} title={t("Nueva playlist")}>
              <Icono nombre="agregar" tam={24} />
            </button>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
  </div>

  <div class:con-indice={!seleccionando && indice.length > 4}>
  {#if !b}
    {#each Array(6) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
  {:else if pestana === "canciones"}
    <div in:fade={{ duration: 220 }}>
      {#if b.canciones.length}
        {#if seleccionando}
          <ListaVirtual items={plana} clave={idDe} tipo={tipoFila} clase={enCuadricula ? "mosaico-biblioteca" : ""}>
            {#snippet fila(c)}
              {#if enCuadricula}
                <div class="eleccion-tarjeta" class:elegida={elegidas.has(c.db_id)}>
                  <Tarjeta portada={c.portada} titulo={c.titulo} subtitulo={c.artista} icono="nota" ancho="100%" alTocar={() => alternarElegida(c.db_id)} />
                  <span class="casilla">{#if elegidas.has(c.db_id)}<Icono nombre="check" tam={16} />{/if}</span>
                </div>
              {:else}
                <button class="fila-eleccion" class:elegida={elegidas.has(c.db_id)} onclick={() => alternarElegida(c.db_id)}>
                  <span class="casilla">{#if elegidas.has(c.db_id)}<Icono nombre="check" tam={16} />{/if}</span>
                  <Portada url={c.portada} tam="46px" radio="8px" />
                  <span class="textos"><b class="cortar">{c.titulo}</b><small class="cortar">{c.artista}</small></span>
                </button>
              {/if}
            {/snippet}
          </ListaVirtual>
        {:else}
          {#each grupos as g (g.titulo)}
            <!-- El salto del índice va al ancla: un encabezado fijo (sticky) que ya pasó no deja regresar a él -->
            <span class="ancla" id="grupo-{g.titulo}"></span>
            <div class="grupo">{g.titulo}</div>
            <ListaVirtual items={g.canciones} clave={idDe} tipo={tipoFila} clase={enCuadricula ? "mosaico-biblioteca" : ""}>
              {#snippet fila(c)}
                {#if enCuadricula}
                  <Tarjeta portada={c.portada} titulo={c.titulo} subtitulo={c.artista} icono="nota" ancho="100%"
                    alTocar={() => reproducir(plana, plana.indexOf(c), "Tu biblioteca")} alMantener={() => menuCancion(c)} />
                {:else}
                  <FilaCancion cancion={c} alTocar={() => reproducir(plana, plana.indexOf(c), "Tu biblioteca")} />
                {/if}
              {/snippet}
            </ListaVirtual>
          {:else}
            <p class="vacio">{t("Nada en tu biblioteca con “{q}”.", { q: texto })}</p>
          {/each}
        {/if}
      {:else}
        <p class="vacio">{t("Aún no tienes canciones descargadas.")}</p>
      {/if}
      {#if !seleccionando && texto.length >= 2 && (enLinea.length || buscandoLinea)}
        <div class="titulo-seccion">{t("En YouTube Music")} <small>{t("no las tienes")}</small></div>
        {#each enLinea as c, i (c.id)}
          <FilaCancion cancion={c} alTocar={() => reproducir(enLinea, i, t("Búsqueda “{q}”", { q: texto }))} />
        {:else}
          {#each Array(3) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
        {/each}
      {/if}
    </div>
  {:else if pestana === "albumes"}
    <div in:fade={{ duration: 220 }}>
      {#each gruposAlbumes as g (g.titulo)}
        <span class="ancla" id="grupo-{g.titulo}"></span>
        <div class="grupo">{g.titulo}</div>
        <ListaVirtual items={g.items} clave={claveAlbum} tipo={tipoFila} clase={enCuadricula ? "mosaico-biblioteca" : ""}>
          {#snippet fila(a)}
            {#if !enCuadricula}
              {#if seleccionando}
                <button class="fila-eleccion" class:elegida={elegidos.has(claveAlbum(a))} onclick={() => alternarElegido(claveAlbum(a))}>
                  <span class="casilla">{#if elegidos.has(claveAlbum(a))}<Icono nombre="check" tam={16} />{/if}</span>
                  <Portada url={a.portada} tam="46px" radio="8px" />
                  <span class="textos"><b class="cortar">{a.nombre}</b><small class="cortar">{a.artista}</small></span>
                </button>
              {:else}
                <button class="fila-artista" onclick={() => abrir("album", { local: a })}>
                  <Portada url={a.portada} tam="54px" radio="10px" />
                  <span class="textos"><b class="cortar">{a.nombre}</b><small class="cortar">{a.artista}</small></span>
                </button>
              {/if}
            {:else if seleccionando}
              <div class="eleccion-tarjeta" class:elegida={elegidos.has(claveAlbum(a))}>
                <Tarjeta portada={a.portada} titulo={a.nombre} subtitulo={a.artista} ancho="100%" alTocar={() => alternarElegido(claveAlbum(a))} />
                <span class="casilla">{#if elegidos.has(claveAlbum(a))}<Icono nombre="check" tam={16} />{/if}</span>
              </div>
            {:else}
              <Tarjeta portada={a.portada} titulo={a.nombre} subtitulo={a.artista} ancho="100%" alTocar={() => abrir("album", { local: a })} />
            {/if}
          {/snippet}
        </ListaVirtual>
      {:else}
        <p class="vacio">{texto ? t("Ningún álbum con “{q}”.", { q: texto }) : t("Sin álbumes todavía.")}</p>
      {/each}
    </div>
  {:else if pestana === "artistas"}
    <div in:fade={{ duration: 220 }}>
      {#each gruposArtistas as g (g.titulo)}
        <span class="ancla" id="grupo-{g.titulo}"></span>
        <div class="grupo">{g.titulo}</div>
        <ListaVirtual items={g.items} clave={(a) => a.nombre} tipo={tipoFila} clase={enCuadricula ? "mosaico-biblioteca" : ""}>
          {#snippet fila(a)}
            {#if enCuadricula}
              {#if seleccionando}
                <div class="eleccion-tarjeta" class:elegida={elegidos.has(`artista:${a.nombre}`)}>
                  <Tarjeta redonda icono="persona" titulo={a.nombre} subtitulo={canciones(a.canciones)} ancho="100%" alTocar={() => alternarElegido(`artista:${a.nombre}`)} />
                  <span class="casilla">{#if elegidos.has(`artista:${a.nombre}`)}<Icono nombre="check" tam={16} />{/if}</span>
                </div>
              {:else}
                <Tarjeta redonda icono="persona" titulo={a.nombre} subtitulo={canciones(a.canciones)} ancho="100%"
                  alTocar={() => abrir("artista", { nombre: a.nombre })} alMantener={() => opcionesArtista(a)} />
              {/if}
            {:else if seleccionando}
              <button class="fila-eleccion" class:elegida={elegidos.has(`artista:${a.nombre}`)} onclick={() => alternarElegido(`artista:${a.nombre}`)}>
                <span class="casilla">{#if elegidos.has(`artista:${a.nombre}`)}<Icono nombre="check" tam={16} />{/if}</span>
                <span class="avatar chico"><Icono nombre="persona" tam={20} /></span>
                <span class="textos"><b class="cortar">{a.nombre}</b><small>{canciones(a.canciones)}</small></span>
              </button>
            {:else}
              <div class="fila-con-menu">
                <button class="fila-artista" onclick={() => abrir("artista", { nombre: a.nombre })}>
                  <span class="avatar"><Icono nombre="persona" tam={22} /></span>
                  <span class="textos"><b class="cortar">{a.nombre}</b><small>{canciones(a.canciones)}</small></span>
                </button>
                <button class="mas" aria-label={t("Opciones de {nombre}", a)} onclick={() => opcionesArtista(a)}><Icono nombre="mas" tam={22} /></button>
              </div>
            {/if}
          {/snippet}
        </ListaVirtual>
      {:else}
        <p class="vacio">{texto ? t("Ningún artista con “{q}”.", { q: texto }) : t("Sin artistas todavía.")}</p>
      {/each}
    </div>
  {:else if pestana === "generos"}
    <div in:fade={{ duration: 220 }}>
      {#each gruposGeneros as g (g.titulo)}
        <span class="ancla" id="grupo-{g.titulo}"></span>
        <div class="grupo">{g.titulo}</div>
        <div class:mosaico-biblioteca={enCuadricula}>
          {#each g.items as x (x.nombre)}
            {#if enCuadricula}
              <Tarjeta portada={x.portada} titulo={x.nombre} subtitulo={canciones(x.canciones)} icono="nota" ancho="100%" alTocar={() => abrir("genero", { nombre: x.nombre })} />
            {:else}
              <button class="fila-artista" onclick={() => abrir("genero", { nombre: x.nombre })}>
                <Portada url={x.portada} tam="54px" radio="10px" icono="nota" />
                <span class="textos"><b class="cortar">{x.nombre}</b><small>{canciones(x.canciones)}</small></span>
              </button>
            {/if}
          {/each}
        </div>
      {:else}
        <p class="vacio">{texto ? t("Ningún género con “{q}”.", { q: texto }) : t("Tus canciones todavía no traen género. Puedes completarlo desde su información.")}</p>
      {/each}
    </div>
  {:else}
    <div in:fade={{ duration: 220 }}>
      {#if creando}
        <form class="nueva" onsubmit={(ev) => { ev.preventDefault(); crear(); }}>
          <input bind:value={nombre} placeholder={t("Nombre de la playlist")} />
          <button class="pildora cian chica">{t("Crear")}</button>
        </form>
      {/if}
      <!-- Me gusta va siempre primero: no es una playlist que se borre, guarda también canciones no descargadas -->
      {#if !seleccionando}
        <div class:mosaico-biblioteca={enCuadricula}>
          {#if enCuadricula}
            <button class="tarjeta-lista" onclick={() => abrir("me_gusta")}>
              <span class="cubierta me-gusta"><Icono nombre="corazon" relleno tam={34} /></span>
              <b class="cortar">{t("Me gusta")}</b><small>{canciones(b.me_gusta ?? 0)}</small>
            </button>
          {:else}
            <button class="fila-artista" onclick={() => abrir("me_gusta")}>
              <span class="avatar cuadro me-gusta"><Icono nombre="corazon" relleno tam={22} /></span>
              <span class="textos"><b class="cortar">{t("Me gusta")}</b><small>{canciones(b.me_gusta ?? 0)}</small></span>
            </button>
          {/if}
        </div>
      {/if}
      {#each gruposPlaylists as g (g.titulo)}
        <span class="ancla" id="grupo-{g.titulo}"></span>
        <div class="grupo">{g.titulo}</div>
        <div class:mosaico-biblioteca={enCuadricula}>
          {#each g.items as p (p.id)}
            {#if enCuadricula}
              <button class="tarjeta-lista" class:eleccion-tarjeta={seleccionando} class:elegida={elegidos.has(`playlist:${p.id}`)}
                onclick={() => (seleccionando ? alternarElegido(`playlist:${p.id}`) : abrir("playlist", { id: p.id, nombre: p.nombre }))}>
                <span class="cubierta"><Icono nombre="lista" tam={34} /></span>
                <b class="cortar">{p.nombre}</b><small>{canciones(p.canciones)}</small>
                {#if seleccionando}<span class="casilla">{#if elegidos.has(`playlist:${p.id}`)}<Icono nombre="check" tam={16} />{/if}</span>{/if}
              </button>
            {:else if seleccionando}
              <button class="fila-eleccion" class:elegida={elegidos.has(`playlist:${p.id}`)} onclick={() => alternarElegido(`playlist:${p.id}`)}>
                <span class="casilla">{#if elegidos.has(`playlist:${p.id}`)}<Icono nombre="check" tam={16} />{/if}</span>
                <span class="avatar chico cuadro"><Icono nombre="lista" tam={20} /></span>
                <span class="textos"><b class="cortar">{p.nombre}</b><small>{canciones(p.canciones)}</small></span>
              </button>
            {:else}
              <button class="fila-artista" onclick={() => abrir("playlist", { id: p.id, nombre: p.nombre })}>
                <span class="avatar cuadro"><Icono nombre="lista" tam={22} /></span>
                <span class="textos"><b class="cortar">{p.nombre}</b><small>{canciones(p.canciones)}</small></span>
              </button>
            {/if}
          {/each}
        </div>
      {:else}
        {#if !creando}<p class="vacio">{t("Crea tus playlists con el botón +.")}</p>{/if}
      {/each}
    </div>
  {/if}
  </div>
</div>

{#if !seleccionando && indice.length > 4}
  <div class="indice" use:aBody role="navigation" aria-label={t("Saltar a una letra")}
    onpointerdown={tocarIndice} onpointermove={tocarIndice} onpointerup={soltarIndice} onpointercancel={soltarIndice}>
    {#each indice as letra}<span data-letra={letra} class:tocada={burbuja?.letra === letra}>{letra}</span>{/each}
  </div>
  {#if burbuja}
    <div class="burbuja" use:aBody style:top="{burbuja.y}px" style:left="{burbuja.x}px" transition:fade={{ duration: 120 }} aria-hidden="true">
      <span>{burbuja.letra}</span>
    </div>
  {/if}
{/if}

{#if panelCarpetas}
  <div class="fondo-modal" use:aBody transition:fade={{ duration: 180 }} onclick={() => (panelCarpetas = false)} role="presentation"></div>
  <div class="modal" use:aBody transition:scale={{ duration: 220, start: 0.94 }} role="dialog" aria-label={t("Carpetas de música")}>
    <button class="redondo cerrar-modal" onclick={() => (panelCarpetas = false)} aria-label={t("Cerrar")}><Icono nombre="cerrar" tam={22} /></button>
    {#if explorando}
      <h2>{t("Elige tu carpeta de música")}</h2>
      <!-- ruta "" = la lista de almacenamientos (interno y tarjetas SD) -->
      <p class="tenue ruta-actual">{explorando.ruta || t("¿En qué almacenamiento está tu música?")}</p>
      <div class="lista-carpetas">
        {#if explorando.padre != null}
          <button class="fila-carpeta" onclick={() => irA(explorando.padre)}><Icono nombre="atras" tam={20} /><span>{t("Subir")}</span></button>
        {/if}
        {#each explorando.carpetas as c}
          <button class="fila-carpeta" onclick={() => irA(c.ruta)}><Icono nombre="carpeta" tam={20} /><span class="cortar">{c.nombre}</span></button>
        {:else}
          <p class="tenue">{t("No hay más carpetas aquí.")}</p>
        {/each}
      </div>
      {#if explorando.ruta}
        <button class="pildora cian ancho" onclick={() => agregarCarpeta(explorando.ruta)}>{t("Usar esta carpeta")}</button>
      {/if}
    {:else}
      <h2>{t("Carpetas de música")}</h2>
      <p class="tenue">{t("Misiccord escucha estas carpetas, con todas sus subcarpetas, para armar tu biblioteca.")}</p>
      {#if escaneando}<p class="leyendo">{t("Leyendo…")} {revisadas ? canciones(revisadas) : ""}</p>{/if}
      <div class="lista-carpetas">
        {#each carpetas?.carpetas ?? [] as c (c.ruta)}
          <div class="fila-carpeta quieta">
            <Icono nombre="carpeta" tam={20} />
            <span class="textos">
              <b class="cortar">{nombreCarpeta(c.ruta)}</b>
              <small class="cortar">{c.existe ? canciones(c.canciones) : t("No se encuentra")}{c.descargas ? ` · ${t("descargas")}` : ""}</small>
              <small class="cortar ruta">{c.ruta}</small>
            </span>
            {#if !c.descargas}
              <button class="redondo" onclick={() => quitarCarpeta(c)} aria-label={t("Quitar {nombre}", { nombre: nombreCarpeta(c.ruta) })}><Icono nombre="cerrar" tam={18} /></button>
            {/if}
          </div>
        {/each}
      </div>
      <button class="pildora cian ancho" disabled={!carpetas} onclick={elegirCarpetaMusica}><Icono nombre="agregar" tam={18} /> {t("Agregar carpeta…")}</button>
    {/if}
  </div>
{/if}

{#if seleccionando}
  <div class="barra-seleccion" use:aBody>
    <div class="cuenta">
      <b>{totalElegido === 1 ? t("1 elegido") : t("{n} elegidos", { n: totalElegido })}</b>
      <small class="tenue">{t("Canciones, álbumes, artistas o playlists")}</small>
    </div>
    <div class="botones">
      {#if elegidas.size && !elegidos.size}
        <button class="redondo" onclick={() => completarDatos(b.canciones.filter((c) => elegidas.has(c.db_id)))} aria-label={t("Completar datos")} title={t("Completar datos")}><Icono nombre="etiqueta" tam={20} /></button>
        <button class="redondo rojo-texto" onclick={eliminarElegidas} aria-label={t("Eliminar")} title={t("Eliminar")}><Icono nombre="basura" tam={20} /></button>
      {/if}
      <button class="pildora cian chica" disabled={!totalElegido || preparando} onclick={compartirElegidas}>
        <Icono nombre="compartir" tam={18} /> {preparando ? t("Preparando…") : t("Compartir")}
      </button>
    </div>
  </div>
{/if}

<style>
  .vista { padding: 0 var(--margen); }
  /* Se queda pegada arriba: al bajar se esconde y al subir regresa */
  .cabecera {
    position: sticky; top: 0; z-index: 6; margin: 0 calc(-1 * var(--margen)); padding: calc(var(--seguro-arriba) + 14px) var(--margen) 2px;
    background: var(--fondo); transition: transform 0.25s var(--curva);
  }
  .cabecera.oculta { transform: translateY(-100%); }
  header { display: flex; align-items: center; justify-content: space-between; }
  .chips { display: flex; gap: 8px; margin: var(--margen) calc(-1 * var(--margen)) 10px; padding: 0 var(--margen); overflow-x: auto; scrollbar-width: none; }
  /* Segunda fila de chips (carpetas): más chica para que se note que es un filtro */
  .chips.carpetas { margin-top: -2px; }
  .carpetas .chip { height: 32px; padding: 0 14px; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; background: transparent; border: 1px solid var(--borde-fuerte); }
  .carpetas .chip.activo { background: var(--cian); border-color: var(--cian); color: #04121a; }
  .carpetas .chip small { opacity: 0.65; }
  .buscador {
    display: flex; align-items: center; gap: 10px; height: 44px; margin-top: 12px; padding: 0 12px; border-radius: 12px;
    background: var(--tarjeta); border: 1px solid var(--borde); color: var(--tenue);
  }
  .buscador:focus-within { border-color: var(--cian); }
  .buscador input { flex: 1; min-width: 0; height: 100%; border: 0; outline: 0; background: transparent; color: var(--texto); font-size: 15.5px; }
  .buscador button { display: grid; place-items: center; color: var(--tenue); }
  .girando { width: 16px; height: 16px; border-radius: 50%; border: 2.5px solid var(--borde-fuerte); border-top-color: var(--cian); animation: giro 0.8s linear infinite; flex-shrink: 0; }
  @keyframes giro { to { transform: rotate(360deg); } }
  /* Encabezado de cada grupo (letra, álbum o periodo): se queda arriba mientras pasan sus canciones */
  .grupo {
    position: sticky; top: var(--arriba, 0px); z-index: 2; background: var(--fondo); padding: 10px 0 4px; margin-top: 4px;
    font-size: 15px; font-weight: 800; color: var(--cian); transition: top 0.25s var(--curva);
  }
  .ancla { display: block; height: 0; scroll-margin-top: var(--arriba, 0px); }
  .contador { font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .columnas { display: inline-flex; align-items: center; gap: 2px; height: 34px; padding: 0 3px; border-radius: 999px; background: var(--tarjeta); flex-shrink: 0; }
  .columnas button { width: 28px; height: 28px; border-radius: 50%; font-size: 18px; font-weight: 700; line-height: 1; }
  .columnas button:disabled { opacity: 0.3; }
  .columnas span { min-width: 16px; text-align: center; font-size: 13.5px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .con-indice { padding-right: 16px; } /* que el índice no tape el ⋯ de las filas */
  .indice {
    position: fixed; z-index: 20; right: 2px; top: calc(var(--seguro-arriba) + 170px);
    bottom: calc(var(--nav) + var(--mini) + var(--seguro-abajo) + 18px);
    display: flex; flex-direction: column; justify-content: space-evenly; align-items: center; padding: 2px 3px;
    touch-action: none; user-select: none; -webkit-user-select: none;
  }
  .indice span { font-size: 11px; font-weight: 800; color: var(--cian); padding: 0 4px; line-height: 1; cursor: pointer; transition: transform 0.12s; }
  .indice span.tocada { transform: scale(1.5); color: #fff; }
  /* La burbuja sale a la izquierda del dedo, a la altura de la letra */
  .burbuja {
    position: fixed; z-index: 40; width: 64px; height: 64px; margin: -32px 0 0 -84px; pointer-events: none;
    display: grid; place-items: center; border-radius: 50% 50% 8px 50%; transform: rotate(-45deg);
    background: var(--cian); color: #04121a; font-size: 30px; font-weight: 800; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
  }
  .burbuja span { transform: rotate(45deg); }
  @media (min-width: 900px) {
    .indice { right: 10px; top: 200px; bottom: calc(var(--mini) + 30px); }
  }
  /* Cuadrícula: las columnas las eliges tú (--columnas, en .vista). Es global porque también la usa la caja de ListaVirtual */
  :global(.mosaico-biblioteca) { display: grid; grid-template-columns: repeat(var(--columnas, 3), minmax(0, 1fr)); gap: 16px 12px; margin: 6px 0 12px; }
  :global(.mosaico-biblioteca .tarjeta b) { font-size: 13.5px; margin-top: 6px; }
  :global(.mosaico-biblioteca .tarjeta small) { font-size: 12.5px; }
  @media (min-width: 900px) { :global(.mosaico-biblioteca) { gap: 22px 18px; } }
  .tarjeta-lista { position: relative; display: flex; flex-direction: column; gap: 4px; text-align: left; min-width: 0; }
  .tarjeta-lista b { margin-top: 6px; font-size: 13.5px; font-weight: 700; width: 100%; }
  .tarjeta-lista small { color: var(--tenue); font-size: 12.5px; }
  .cubierta { aspect-ratio: 1; border-radius: 12px; background: var(--tarjeta-2); display: grid; place-items: center; color: var(--tenue); }
  .cubierta.me-gusta { background: linear-gradient(135deg, #ff4d6d, #7c3aed); color: #fff; }
  .acciones { display: flex; justify-content: space-between; align-items: center; margin: 6px 0 8px; }
  .chica { height: 38px; padding: 0 16px; font-size: 14px; }
  .fila-artista { width: 100%; display: flex; align-items: center; gap: 14px; padding: 8px 0; text-align: left; }
  .avatar { width: 54px; height: 54px; border-radius: 50%; background: var(--tarjeta-2); display: grid; place-items: center; color: var(--tenue); flex-shrink: 0; }
  .avatar.cuadro { border-radius: 10px; }
  .avatar.me-gusta { background: linear-gradient(135deg, #ff4d6d, #7c3aed); color: #fff; }
  .textos { min-width: 0; display: flex; flex-direction: column; }
  .textos small { color: var(--tenue); }
  .botones { display: flex; align-items: center; gap: 6px; }
  .texto-boton { color: var(--cian); font-weight: 600; padding: 8px 0; }
  .fila-eleccion { width: 100%; display: flex; align-items: center; gap: 12px; padding: 7px 6px; border-radius: 12px; text-align: left; transition: background 0.15s; }
  .fila-eleccion.elegida { background: rgba(34, 211, 238, 0.08); }
  .casilla { width: 24px; height: 24px; border-radius: 7px; border: 2px solid var(--borde-fuerte); display: grid; place-items: center; flex-shrink: 0; color: #04121a; transition: background 0.15s, border-color 0.15s; }
  .elegida .casilla { background: var(--cian); border-color: var(--cian); }
  .fila-eleccion .textos { flex: 1; }
  .fila-con-menu { display: flex; align-items: center; }
  .fila-con-menu .fila-artista { flex: 1; min-width: 0; }
  .mas { width: 40px; height: 44px; display: grid; place-items: center; color: var(--tenue); flex-shrink: 0; }
  /* Va encima del mini reproductor mientras eliges */
  .barra-seleccion {
    position: fixed; z-index: 32; left: 10px; right: 10px; bottom: calc(var(--nav) + var(--seguro-abajo) + 6px);
    height: var(--mini); display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 12px 0 18px;
    border-radius: 18px; background: rgba(28, 42, 53, 0.98); backdrop-filter: blur(22px); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
  }
  .rojo-texto { color: var(--rojo); }
  .cian:disabled { opacity: 0.45; }
  .cuenta { display: flex; flex-direction: column; min-width: 0; }
  .cuenta small { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .activo-cian { color: var(--cian); background: rgba(34, 211, 238, 0.12); }
  .avatar.chico { width: 46px; height: 46px; }
  .eleccion-tarjeta { position: relative; border-radius: 14px; transition: opacity 0.15s; }
  .eleccion-tarjeta .casilla { position: absolute; z-index: 2; top: 8px; right: 8px; background: rgba(0, 0, 0, 0.45); border-color: #fff; pointer-events: none; }
  .eleccion-tarjeta.elegida .casilla { background: var(--cian); border-color: var(--cian); }
  .eleccion-tarjeta:not(.elegida) { opacity: 0.85; }
  @media (min-width: 900px) {
    .barra-seleccion { left: calc(var(--lateral) + 16px); right: 16px; bottom: 16px; }
  }
  .leyendo { margin: 6px 0 0; font-size: 13px; color: var(--cian); }
  .fondo-modal { position: fixed; inset: 0; z-index: 300; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); }
  .modal {
    position: fixed; z-index: 301; left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: min(420px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto;
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 24px; padding: 22px 20px 20px;
  }
  .modal h2 { margin: 0 36px 0 0; font-size: 21px; font-weight: 800; }
  .modal p { margin: 6px 0 12px; font-size: 14px; line-height: 1.45; }
  .cerrar-modal { position: absolute; top: 10px; right: 10px; }
  .lista-carpetas { max-height: 46vh; overflow-y: auto; margin-bottom: 14px; }
  .fila-carpeta { width: 100%; display: flex; align-items: center; gap: 12px; padding: 10px 6px; border-radius: 12px; text-align: left; color: var(--tenue); }
  button.fila-carpeta:hover, button.fila-carpeta:active { background: var(--tarjeta-2); }
  .fila-carpeta span:not(.textos) { color: var(--texto, inherit); }
  .fila-carpeta .textos { flex: 1; color: inherit; }
  .fila-carpeta .textos b { color: var(--texto, inherit); }
  .ruta, .ruta-actual { font-size: 12px; overflow-wrap: anywhere; }
  .ancho { width: 100%; justify-content: center; }
  .nueva { display: flex; gap: 10px; margin: 4px 0 12px; }
  .nueva input { flex: 1; min-width: 0; height: 44px; border-radius: 12px; border: 1px solid var(--borde-fuerte); background: var(--tarjeta); padding: 0 14px; outline: 0; }
</style>
