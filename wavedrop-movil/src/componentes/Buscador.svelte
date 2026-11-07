<script>
  import { t } from "../lib/idioma.svelte.js";
  import { fade } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { abrir, aviso, descargarLink, ui } from "../lib/estado.svelte.js";
  import { reproducir, reproducirConRadio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "./FilaCancion.svelte";
  import Icono from "./Icono.svelte";
  import Tarjeta from "./Tarjeta.svelte";

  // Búsqueda en vivo (en Inicio): lo de tu biblioteca sale al instante y lo de YouTube Music en cuanto
  // dejas de escribir. `e` es la entrada de la pila de Inicio: ahí se guarda la búsqueda para volver a ella.
  let { e, activo = $bindable(false) } = $props();
  let q = $state(e.q ?? "");
  let tipo = $state(e.tipo ?? "todo");
  let buscando = $state(false);
  let locales = $state(e.locales ?? []);
  const r = $derived(e.busqueda);
  const texto = $derived(q.trim());
  const esLink = $derived(/^https?:\/\//.test(texto));
  let enfocado = $state(false);
  const verHistorial = $derived(enfocado && !texto && historial.length > 0);
  $effect(() => { activo = texto.length > 0 || verHistorial; });

  // Lo que has buscado: sale al tocar la caja vacía. Se guarda en este dispositivo al darle Enter o al abrir un
  // resultado (no cada letra que tecleas). Lo más reciente primero, sin repetir, hasta 15.
  const LLAVE = "misiccord_busquedas";
  let historial = $state(leerHistorial());
  function leerHistorial() {
    try { return JSON.parse(localStorage.getItem(LLAVE) || "[]"); } catch { return []; }
  }
  function guardarHistorial(lista) {
    historial = lista;
    try { localStorage.setItem(LLAVE, JSON.stringify(lista)); } catch {}
  }
  function recordar(consulta = texto) {
    const limpia = consulta.trim();
    if (!limpia || /^https?:\/\//.test(limpia)) return;
    guardarHistorial([limpia, ...historial.filter((h) => h.toLowerCase() !== limpia.toLowerCase())].slice(0, 15));
  }
  function olvidar(h) {
    guardarHistorial(historial.filter((x) => x !== h));
  }
  function buscarDeNuevo(h) {
    q = h;
    alEscribir();
    clearTimeout(espera);
    buscar(h);
    recordar(h);
  }
  /** Abrir un resultado también deja la búsqueda en el historial */
  const yRecordar = (f) => () => { recordar(); f(); };
  let reinicio = ui.reinicio;
  $effect(() => {
    if (ui.reinicio === reinicio) return;
    reinicio = ui.reinicio;
    q = "";
    alEscribir();
  });

  let pedido = 0; // solo vale la respuesta de lo último que escribiste
  let espera = null;

  function alEscribir() {
    clearTimeout(espera);
    e.q = q;
    if (!texto || esLink) {
      e.busqueda = null;
      locales = e.locales = [];
      buscando = false;
      return;
    }
    buscarLocal(texto);
    // YouTube Music cuando dejas de teclear un momento (no en cada letra)
    espera = setTimeout(() => buscar(texto), texto.length < 3 ? 600 : 350);
  }

  async function buscarLocal(consulta) {
    const yo = ++pedidoLocal;
    try {
      const b = await py("biblioteca", { q: consulta });
      if (yo === pedidoLocal) locales = e.locales = b.canciones.slice(0, 4);
    } catch {}
  }
  let pedidoLocal = 0;

  async function buscar(consulta = texto) {
    if (!consulta || esLink) return;
    const yo = ++pedido;
    buscando = true;
    try {
      const res = await py("buscar", { q: consulta, tipo });
      if (yo !== pedido) return; // ya escribiste otra cosa
      e.busqueda = { ...res, q: consulta };
      e.tipo = tipo;
      // Las primeras canciones se dejan listas para que suenen en cuanto las toques
      const ids = (res.canciones ?? []).filter((c) => !c.ruta).slice(0, 5).map((c) => c.id);
      if (ids.length) py("precargar", { ids }).catch(() => {});
    } catch {
      if (yo === pedido) aviso(t("No se pudo buscar. ¿Hay conexión a internet?"), "error");
    } finally {
      if (yo === pedido) buscando = false;
    }
  }

  function cambiarTipo(nuevo) {
    tipo = nuevo;
    if (texto) buscar();
  }

  function limpiar() {
    q = "";
    alEscribir();
  }

  const tipos = [["todo", t("Todo")], ["canciones", t("Canciones")], ["albumes", t("Álbumes")], ["artistas", t("Artistas")]];
</script>

<form class="caja" onsubmit={(ev) => { ev.preventDefault(); clearTimeout(espera); buscar(); recordar(); document.activeElement?.blur(); }}>
  <Icono nombre={esLink ? "link" : "buscar"} tam={20} />
  <input bind:value={q} oninput={alEscribir} placeholder={t("Busca canciones, artistas, álbumes o pega un link")} enterkeyhint="search"
    onfocus={() => (enfocado = true)} onblur={() => setTimeout(() => (enfocado = false), 150)} />
  {#if buscando}<span class="girando"></span>{/if}
  {#if q}<button type="button" onclick={limpiar} aria-label={t("Borrar búsqueda")}><Icono nombre="cerrar" tam={18} /></button>{/if}
</form>

{#if activo}
  <div class="resultados" in:fade={{ duration: 160 }}>
    {#if verHistorial}
      <!-- pointerdown sin quitar el foco: si no, la caja se suelta antes del toque y el historial desaparece -->
      <div class="titulo-seccion">
        {t("Búsquedas recientes")}
        <button onpointerdown={(ev) => ev.preventDefault()} onclick={() => guardarHistorial([])}><small>{t("Borrar todo")}</small></button>
      </div>
      <ul class="historial">
        {#each historial as h (h)}
          <li>
            <button class="volver-a" onpointerdown={(ev) => ev.preventDefault()} onclick={() => buscarDeNuevo(h)}>
              <Icono nombre="reloj" tam={19} /><span class="cortar">{h}</span>
            </button>
            <button class="quitar" onpointerdown={(ev) => ev.preventDefault()} onclick={() => olvidar(h)} aria-label={t("Quitar “{q}” del historial", { q: h })}>
              <Icono nombre="cerrar" tam={16} />
            </button>
          </li>
        {/each}
      </ul>
    {:else if esLink}
      <div class="link">
        <p>{t("¿Descargar todas las canciones de este link? Funciona con playlists y álbumes de YouTube, YT Music, Spotify, Tidal y SoundCloud.")}</p>
        <button class="pildora cian" onclick={() => descargarLink(texto).then(limpiar).catch(() => aviso(t("No pude leer ese link"), "error"))}>
          <Icono nombre="descargas" tam={20} /> Descargar playlist
        </button>
      </div>
    {:else}
      <div class="chips">
        {#each tipos as [id, nombre]}
          <button class="chip" class:activo={tipo === id} onclick={() => cambiarTipo(id)}>{nombre}</button>
        {/each}
      </div>

      {#if locales.length && tipo !== "albumes" && tipo !== "artistas"}
        <div class="titulo-seccion">{t("En tu biblioteca")}</div>
        {#each locales as c, i}
          <FilaCancion cancion={c} alTocar={yRecordar(() => reproducir(locales, i, t("Tu biblioteca")))} />
        {/each}
      {/if}

      {#if r}
        <div class:viejo={buscando && r.q !== texto}>
          {#if r.artistas?.length}
            {#if tipo === "todo"}<div class="titulo-seccion">{t("Artistas")}</div>{/if}
            <div class={tipo === "todo" ? "carrusel" : "rejilla"}>
              {#each r.artistas as a}
                <Tarjeta portada={a.miniatura} titulo={a.nombre} redonda icono="persona" ancho={tipo === "todo" ? "var(--artista)" : "100%"}
                  alTocar={yRecordar(() => abrir("artista", { id: a.browse_id, nombre: a.nombre }))} />
              {/each}
            </div>
          {/if}
          {#if r.canciones?.length}
            {#if tipo === "todo"}<div class="titulo-seccion">{t("Canciones")}</div>{/if}
            {#each r.canciones as c, i (c.id)}
              <!-- Como en Inicio: la que tocas y detrás su radio (no las demás que se llaman igual) -->
              <FilaCancion cancion={c} alTocar={yRecordar(() => reproducirConRadio(c))} />
            {/each}
          {/if}
          {#if r.albumes?.length}
            {#if tipo === "todo"}<div class="titulo-seccion">{t("Álbumes")}</div>{/if}
            <div class={tipo === "todo" ? "carrusel" : "rejilla"}>
              {#each r.albumes as a}
                <Tarjeta portada={a.miniatura} titulo={a.titulo} subtitulo={[a.tipo, a.anio].filter(Boolean).join(" · ")}
                  ancho={tipo === "todo" ? "148px" : "100%"} alTocar={yRecordar(() => abrir("album", { id: a.browse_id }))} />
              {/each}
            </div>
          {/if}
          {#if !buscando && !r.canciones?.length && !r.albumes?.length && !r.artistas?.length}
            <p class="vacio">{t("Sin resultados para “{q}”.", r)}</p>
          {/if}
        </div>
      {:else if buscando && !locales.length}
        {#each Array(5) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
      {/if}
    {/if}
  </div>
{/if}

<style>
  .caja {
    position: sticky; top: calc(var(--seguro-arriba) + 6px); z-index: 5; margin-top: 14px;
    display: flex; align-items: center; gap: 10px; height: 50px; padding: 0 14px; border-radius: 14px;
    background: var(--texto); color: #04121a; box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
  }
  .caja input { flex: 1; min-width: 0; height: 100%; border: 0; outline: 0; background: transparent; color: #04121a; font-size: 16px; }
  .caja input::placeholder { color: #5b6b78; }
  .girando { width: 18px; height: 18px; border-radius: 50%; border: 2.5px solid rgba(4, 18, 26, 0.2); border-top-color: #04121a; animation: giro 0.8s linear infinite; flex-shrink: 0; }
  @keyframes giro { to { transform: rotate(360deg); } }
  .chips { display: flex; gap: 8px; margin: 16px calc(-1 * var(--margen)) 4px; padding: 0 var(--margen); overflow-x: auto; scrollbar-width: none; }
  .rejilla { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 14px; margin-top: 16px; }
  .link { margin-top: 20px; padding: 18px; border-radius: var(--radio); background: var(--tarjeta); }
  .link p { margin: 0 0 14px; color: var(--tenue); line-height: 1.5; }
  .historial { list-style: none; margin: 0; padding: 0; }
  .historial li { display: flex; align-items: center; gap: 4px; }
  .volver-a { flex: 1; min-width: 0; display: flex; align-items: center; gap: 14px; padding: 12px 0; color: var(--texto); font-size: 15.5px; text-align: left; }
  .volver-a :global(svg) { flex-shrink: 0; color: var(--tenue); }
  .quitar { display: grid; place-items: center; width: 36px; height: 36px; color: var(--tenue); }
  .quitar:hover, .volver-a:hover { color: var(--texto); }
  /* Mientras llegan los resultados de lo nuevo que escribiste, los anteriores se atenúan (no parpadean) */
  .viejo { opacity: 0.55; transition: opacity 0.2s; }
</style>
