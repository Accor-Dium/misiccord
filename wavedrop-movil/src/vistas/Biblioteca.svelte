<script>
  import { onMount } from "svelte";
  import { fade, scale } from "svelte/transition";
  import { alEvento, py } from "../lib/api.js";
  import { abrir, aviso, mostrarHoja, ui } from "../lib/estado.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import { aBody } from "../lib/aBody.js";
  import { pedirEliminar } from "../lib/eliminar.js";
  import { compartir } from "../lib/compartir.js";
  import { canciones, t } from "../lib/idioma.svelte.js";
  import { agrupar, agruparPorLetra, coincide, ORDENES } from "../lib/ordenar.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";
  import Tarjeta from "../componentes/Tarjeta.svelte";

  let { e } = $props();
  let pestana = $state(e.pestana ?? (e.vista === "biblioteca_albumes" ? "albumes" : "canciones"));
  $effect(() => { e.pestana = pestana; });
  let creando = $state(false);
  let nombre = $state("");
  const b = $derived(e.datos);

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
  function opcionesOrden() {
    mostrarHoja({
      titulo: t("Ordenar y agrupar canciones"),
      opciones: ORDENES.map(([id, nombre]) => ({ texto: nombre, icono: orden === id ? "check" : "ordenar", accion: () => ponerOrden(id) })),
    });
  }

  const cancionesVistas = $derived(b ? (texto ? b.canciones.filter((c) => coincide(texto, c.titulo, c.artista, c.album)) : b.canciones) : []);
  const grupos = $derived(agrupar(cancionesVistas, orden));
  const plana = $derived(grupos.flatMap((g) => g.canciones)); // en el orden en que se ven: así suena la cola
  const albumesVistos = $derived(b ? b.albumes.filter((a) => !texto || coincide(texto, a.nombre, a.artista)) : []);
  const gruposArtistas = $derived(agruparPorLetra(b ? b.artistas.filter((a) => !texto || coincide(texto, a.nombre)) : [], (a) => a.nombre));
  const playlistsVistas = $derived(b ? b.playlists.filter((x) => !texto || coincide(texto, x.nombre)) : []);

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

  // Índice A–Z a un lado (por título o artista, sin búsqueda): toca o desliza el dedo para saltar a una letra
  const indice = $derived(!texto && (orden === "titulo" || orden === "artista") && plana.length > 25 ? grupos.map((g) => g.titulo) : []);
  let enIndice = false;
  function tocarIndice(ev) {
    if (ev.type === "pointerdown") {
      enIndice = true;
      ev.currentTarget.setPointerCapture(ev.pointerId);
    }
    if (!enIndice) return;
    const letra = document.elementFromPoint(ev.clientX, ev.clientY)?.closest?.("[data-letra]")?.dataset.letra;
    if (letra) document.getElementById(`grupo-${letra}`)?.scrollIntoView({ block: "start" });
  }

  // Filtro por carpeta de música ("" = todas); se recuerda al volver a esta vista
  let filtro = $state(e.filtro ?? "");
  let pedido = 0;

  async function cargar() {
    const yo = ++pedido;
    const [datos, c] = await Promise.all([py("biblioteca", { carpeta: filtro }), py("carpetas_biblioteca")]);
    if (yo !== pedido) return;
    carpetas = c;
    if (filtro && !c.carpetas.some((x) => x.ruta === filtro)) { // la carpeta filtrada se quitó
      filtro = "";
      e.filtro = "";
      return cargar();
    }
    e.datos = datos;
  }
  function filtrar(ruta) {
    if (ruta === filtro) return;
    filtro = ruta;
    e.filtro = ruta;
    salirSeleccion();
    cargar();
  }
  onMount(() => { if (!e.datos) cargar(); });
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
  let carpetas = $state(null);      // { carpetas: [...], android }
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

  const pestanas = [["canciones", t("Canciones")], ["albumes", t("Álbumes")], ["artistas", t("Artistas")], ["playlists", t("Playlists")]];

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

<div class="vista">
  <header>
    <h1 class="titulo-vista">{t("Biblioteca")}</h1>
    <div class="botones">
      <button class="redondo" onclick={() => abrir("estadisticas")} aria-label={t("Tus estadísticas")} title={t("Tus estadísticas")}><Icono nombre="estadisticas" tam={24} /></button>
      <button class="redondo" onclick={abrirPanel} aria-label={t("Carpetas de música")} title={t("Carpetas de música")}><Icono nombre="carpeta" tam={24} /></button>
      <button class="redondo" class:activo-cian={seleccionando} onclick={() => (seleccionando ? salirSeleccion() : (seleccionando = true))}
        aria-label={t("Compartir o exportar")} title={t("Compartir o exportar")}><Icono nombre="compartir" tam={22} /></button>
      {#if pestana === "playlists"}
        <button class="redondo" onclick={() => (creando = !creando)} aria-label={t("Nueva playlist")}><Icono nombre="agregar" tam={26} /></button>
      {/if}
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

  {#if !b}
    {#each Array(6) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
  {:else if pestana === "canciones"}
    <div in:fade={{ duration: 220 }} class:con-indice={!seleccionando && indice.length > 4}>
      {#if b.canciones.length}
        {#if seleccionando}
          <div class="acciones">
            <button class="texto-boton" onclick={alternarTodas}>{todas ? t("Quitar todas") : t("Elegir todas")}</button>
            <button class="pildora oscura chica" onclick={salirSeleccion}>{t("Listo")}</button>
          </div>
          {#each plana as c (c.db_id)}
            <button class="fila-eleccion" class:elegida={elegidas.has(c.db_id)} onclick={() => alternarElegida(c.db_id)}>
              <span class="casilla">{#if elegidas.has(c.db_id)}<Icono nombre="check" tam={16} />{/if}</span>
              <Portada url={c.portada} tam="46px" radio="8px" />
              <span class="textos"><b class="cortar">{c.titulo}</b><small class="cortar">{c.artista}</small></span>
            </button>
          {/each}
        {:else}
          <div class="acciones">
            <span class="tenue">{texto ? t("{n} de {total} canciones", { n: plana.length, total: b.canciones.length }) : canciones(plana.length)}</span>
            <div class="botones">
              <button class="redondo" onclick={opcionesOrden} aria-label={t("Ordenar y agrupar")} title={t("Ordenar y agrupar")}>
                <Icono nombre="ordenar" tam={22} />
              </button>
              <button class="redondo" onclick={() => (seleccionando = true)} aria-label={t("Seleccionar canciones")} title={t("Seleccionar")}>
                <Icono nombre="seleccionar" tam={22} />
              </button>
              <button class="pildora oscura chica" disabled={!plana.length} onclick={() => reproducirAleatorio(plana, t("Tu biblioteca"))}>
                <Icono nombre="aleatorio" tam={18} /> {t("Aleatorio")}
              </button>
            </div>
          </div>
          {#each grupos as g (g.titulo)}
            <div class="grupo" id="grupo-{g.titulo}">{g.titulo}</div>
            {#each g.canciones as c (c.db_id)}
              <FilaCancion cancion={c} alTocar={() => reproducir(plana, plana.indexOf(c), "Tu biblioteca")} />
            {/each}
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
    <div class="rejilla" in:fade={{ duration: 220 }}>
      {#each albumesVistos as a}
        {#if seleccionando}
          <div class="eleccion-tarjeta" class:elegida={elegidos.has(claveAlbum(a))}>
            <Tarjeta portada={a.portada} titulo={a.nombre} subtitulo={a.artista} ancho="100%" alTocar={() => alternarElegido(claveAlbum(a))} />
            <span class="casilla">{#if elegidos.has(claveAlbum(a))}<Icono nombre="check" tam={16} />{/if}</span>
          </div>
        {:else}
          <Tarjeta portada={a.portada} titulo={a.nombre} subtitulo={a.artista} ancho="100%" alTocar={() => abrir("album", { local: a })} />
        {/if}
      {:else}
        <p class="vacio">{texto ? t("Ningún álbum con “{q}”.", { q: texto }) : t("Sin álbumes todavía.")}</p>
      {/each}
    </div>
  {:else if pestana === "artistas"}
    <div in:fade={{ duration: 220 }}>
      {#each gruposArtistas as g (g.titulo)}
        <div class="grupo">{g.titulo}</div>
        {#each g.items as a}
          {#if seleccionando}
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
        {/each}
      {:else}
        <p class="vacio">{texto ? t("Ningún artista con “{q}”.", { q: texto }) : t("Sin artistas todavía.")}</p>
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
      <button class="fila-artista" onclick={() => abrir("me_gusta")}>
        <span class="avatar cuadro me-gusta"><Icono nombre="corazon" relleno tam={22} /></span>
        <span class="textos"><b class="cortar">{t("Me gusta")}</b><small>{canciones(b.me_gusta ?? 0)}</small></span>
      </button>
      {/if}
      {#each playlistsVistas as p}
        {#if seleccionando}
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
      {:else}
        {#if !creando}<p class="vacio">{t("Crea tus playlists con el botón +.")}</p>{/if}
      {/each}
    </div>
  {/if}
</div>

{#if pestana === "canciones" && !seleccionando && indice.length > 4}
  <div class="indice" use:aBody role="navigation" aria-label={t("Saltar a una letra")}
    onpointerdown={tocarIndice} onpointermove={tocarIndice} onpointerup={() => (enIndice = false)} onpointercancel={() => (enIndice = false)}>
    {#each indice as letra}<span data-letra={letra}>{letra}</span>{/each}
  </div>
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
        <button class="redondo rojo-texto" onclick={eliminarElegidas} aria-label={t("Eliminar")} title={t("Eliminar")}><Icono nombre="basura" tam={20} /></button>
      {/if}
      <button class="pildora cian chica" disabled={!totalElegido || preparando} onclick={compartirElegidas}>
        <Icono nombre="compartir" tam={18} /> {preparando ? t("Preparando…") : t("Compartir")}
      </button>
    </div>
  </div>
{/if}

<style>
  .vista { padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
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
    position: sticky; top: 0; z-index: 2; background: var(--fondo); padding: 10px 0 4px; margin-top: 4px;
    font-size: 15px; font-weight: 800; color: var(--cian); scroll-margin-top: 0;
  }
  .con-indice { padding-right: 16px; } /* que el índice no tape el ⋯ de las filas */
  .indice {
    position: fixed; z-index: 20; right: 2px; top: calc(var(--seguro-arriba) + 170px);
    bottom: calc(var(--nav) + var(--mini) + var(--seguro-abajo) + 18px);
    display: flex; flex-direction: column; justify-content: space-evenly; align-items: center; padding: 2px 3px;
    touch-action: none; user-select: none; -webkit-user-select: none;
  }
  .indice span { font-size: 11px; font-weight: 800; color: var(--cian); padding: 0 4px; line-height: 1; cursor: pointer; }
  @media (min-width: 900px) {
    .indice { right: 10px; top: 200px; bottom: calc(var(--mini) + 30px); }
  }
  .rejilla { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 14px; margin-top: 8px; }
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
