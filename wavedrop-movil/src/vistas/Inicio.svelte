<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { alEvento, py } from "../lib/api.js";
  import { abrir, abrirTarjeta, aviso, ui } from "../lib/estado.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import { jalarParaActualizar } from "../lib/jalar.js";
  import { mantener } from "../lib/mantener.js";
  import { menuCancion } from "../lib/menuCancion.js";
  import { reproducir } from "../lib/reproductor.svelte.js";
  import Buscador from "../componentes/Buscador.svelte";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Paginas from "../componentes/Paginas.svelte";
  import Portada from "../componentes/Portada.svelte";
  import Tarjeta from "../componentes/Tarjeta.svelte";

  // Inicio: arriba los chips (Para ti, Tu música y estados de ánimo de YouTube Music).
  // "Para ti" junta tus recomendaciones con las secciones generales de YouTube Music y "Explorar" al final.
  let { e } = $props(); // entrada de la pila: guarda los datos para volver al instante

  let pestana = $state(e.pestana ?? "para_ti"); // "para_ti" | "tu_musica" | params de un estado de ánimo
  $effect(() => { e.pestana = pestana; });

  async function cargar() {
    const r = await py("inicio");
    e.datos = { ...r, secciones: r.secciones ?? e.datos?.secciones ?? null };
  }
  async function cargarLinea(forzar = false) {
    try {
      e.linea = await py("inicio_en_linea", { forzar });
    } catch {
      e.linea ??= { secciones: [], estados: [] };
    }
  }

  onMount(() => {
    if (!e.datos) cargar();
    if (!e.linea) cargarLinea();
    const quitar = alEvento("recomendaciones", ({ secciones }) => {
      e.datos = { ...(e.datos ?? {}), secciones };
    });
    return quitar;
  });

  // Recargar lo local cuando cambia la biblioteca (descargas nuevas, escaneo)
  let version = ui.version;
  $effect(() => {
    if (ui.version !== version) {
      version = ui.version;
      cargar();
    }
  });

  function actualizarRecs() {
    e.datos = { ...(e.datos ?? {}), secciones: null };
    py("recomendaciones");
  }

  // Jalar hacia abajo (en el cel): todo de nuevo, también lo de YouTube Music
  const jalon = $state({ distancia: 0, listo: false, cargando: false });
  async function refrescar() {
    const esperarRecs = new Promise((listo) => {
      const quitar = alEvento("recomendaciones", () => { quitar(); listo(); });
      setTimeout(listo, 15000);
    });
    actualizarRecs();
    await Promise.all([cargar(), cargarLinea(true), esperarRecs, pestanaEstado && abrirEstado(pestanaEstado, true)]);
    aviso(t("Inicio actualizado"), "ok", { duracion: 1600 });
  }

  const d = $derived(e.datos);
  const linea = $derived(e.linea);
  let buscandoAlgo = $state(false);

  // Chips de estados de ánimo: los del primer grupo de YouTube Music ("Estados de ánimo y momentos")
  const estadosChip = $derived(linea?.estados?.[0]?.opciones ?? []);
  const pestanaEstado = $derived(pestana !== "para_ti" && pestana !== "tu_musica" ? pestana : null);
  let tarjetasEstado = $state(e.tarjetasEstado ?? null);
  async function abrirEstado(params, forzar = false) {
    if (!forzar && e.estadoAbierto === params && tarjetasEstado) return;
    tarjetasEstado = null;
    try {
      const r = await py("estado_animo", { params });
      if (pestana === params) {
        tarjetasEstado = r.tarjetas.slice(0, 60);
        e.tarjetasEstado = tarjetasEstado;
        e.estadoAbierto = params;
      }
    } catch (err) {
      aviso(err.message, "error");
    }
  }
  $effect(() => { if (pestanaEstado) abrirEstado(pestanaEstado); });

  // Las primeras recomendaciones se dejan listas para que suenen en cuanto las toques
  $effect(() => {
    const ids = (d?.secciones?.[0]?.canciones ?? []).filter((c) => !c.ruta).slice(0, 4).map((c) => c.id);
    if (ids.length) py("precargar", { ids }).catch(() => {});
  });

  const porPagina = $derived(ui.amplio ? 12 : 9); // 3×3 en el cel, 6×2 en pantalla ancha
  const trozos = (lista, n) => Array.from({ length: Math.ceil(lista.length / n) }, (_, i) => lista.slice(i * n, i * n + n));

  const explorar = [
    { que: "lanzamientos", texto: "Nuevos lanzamientos", icono: "nuevo" },
    { que: "tendencia", texto: "Tendencias", icono: "tendencia" },
    { que: "estados", texto: "Estados de ánimo y géneros", icono: "animo" },
    { que: "estadisticas", texto: "Tus estadísticas", icono: "estadisticas" },
  ];
  function abrirExplorar(x) {
    if (x.que === "estadisticas") abrir("estadisticas");
    else abrir("explorar", { que: x.que, titulo: t(x.texto) });
  }
</script>

<div class="vista" use:jalarParaActualizar={{ alSoltar: refrescar, estado: jalon }}>
  {#if jalon.distancia > 0}
    <div class="jalon" class:listo={jalon.listo} class:cargando={jalon.cargando}
      style:transform="translateY({jalon.distancia}px) rotate({jalon.distancia * 3}deg)" style:opacity={Math.min(1, jalon.distancia / 50)}>
      <Icono nombre="actualizar" tam={20} />
    </div>
  {/if}
  <div style:transform={jalon.distancia ? `translateY(${jalon.distancia * 0.35}px)` : null} class="contenido" class:suelto={!jalon.distancia}>
  <header>
    <h1 class="titulo-vista">{t("Inicio")}</h1>
    <button class="redondo" onclick={() => abrir("ajustes")} aria-label={t("Ajustes")}><Icono nombre="ajustes" tam={24} /></button>
  </header>

  <Buscador {e} bind:activo={buscandoAlgo} />

  {#if !buscandoAlgo}
  <div class="chips" role="tablist">
    <button class="chip" class:activo={pestana === "para_ti"} onclick={() => (pestana = "para_ti")}>{t("Para ti")}</button>
    <button class="chip" class:activo={pestana === "tu_musica"} onclick={() => (pestana = "tu_musica")}>{t("Tu música")}</button>
    {#each estadosChip as x (x.params)}
      <button class="chip suave" class:activo={pestana === x.params} onclick={() => (pestana = x.params)}>{x.titulo}</button>
    {/each}
  </div>

  {#if pestana === "para_ti"}
    <div in:fade={{ duration: 220 }}>
      {#if !d || d.secciones === null}
        <div class="titulo-seccion">{t("Buscando recomendaciones…")}</div>
        <div class="marcacion">
          {#each Array(6) as _}<div class="cargando-bloque" style="aspect-ratio:1"></div>{/each}
        </div>
      {:else if d.secciones.length}
        {#each d.secciones as s, k}
          <div class="titulo-seccion">
            <span>{s.titulo}</span>
            {#if k === 0}<button onclick={actualizarRecs}><small>{t("Actualizar")}</small></button>{/if}
          </div>
          {#if s.artistas?.length}
            <div class="carrusel">
              {#each s.artistas as a}
                <Tarjeta portada={a.miniatura} titulo={a.nombre} redonda icono="persona" ancho="var(--artista)"
                  alTocar={() => abrir("artista", { id: a.browse_id, nombre: a.nombre })} />
              {/each}
            </div>
          {:else if k === 0}
            <!-- Marcación rápida: páginas de 3×3 que se pasan de lado -->
            <Paginas paginas={trozos(s.canciones, porPagina)}>
              {#snippet pagina(grupo, p)}
                <div class="marcacion">
                  {#each grupo as c, i}
                    <button class="mosaico" onclick={() => reproducir(s.canciones, p * porPagina + i, s.titulo)}
                      use:mantener={() => menuCancion(c)}>
                      <Portada url={c.portada} radio="10px" icono="nota" />
                      <span class="sombra"></span>
                      <b class="cortar">{c.titulo}</b>
                    </button>
                  {/each}
                </div>
              {/snippet}
            </Paginas>
          {:else}
            <div class="carrusel">
              {#each s.canciones as c, i}
                <Tarjeta portada={c.portada} titulo={c.titulo} subtitulo={c.artista} icono="nota" alMantener={() => menuCancion(c)}
                  alTocar={() => reproducir(s.canciones, i, s.titulo)} />
              {/each}
            </div>
          {/if}
        {/each}
      {/if}

      <!-- Lo general de YouTube Music (no hace falta cuenta) -->
      {#each linea?.secciones ?? [] as s}
        {#if s.canciones.length}
          <div class="titulo-seccion">
            <span>{s.titulo}</span>
            <button class="pildora-borde" onclick={() => reproducir(s.canciones, 0, s.titulo)}>{t("Reproducir todo")}</button>
          </div>
          <div class="carrusel filas">
            {#each trozos(s.canciones, 4) as columna, j}
              <div class="columna">
                {#each columna as c, i}
                  <FilaCancion cancion={c} alTocar={() => reproducir(s.canciones, j * 4 + i, s.titulo)} />
                {/each}
              </div>
            {/each}
          </div>
        {/if}
        {#if s.tarjetas.length}
          {#if !s.canciones.length}<div class="titulo-seccion"><span>{s.titulo}</span></div>{/if}
          <div class="carrusel">
            {#each s.tarjetas as x}
              <Tarjeta portada={x.miniatura} titulo={x.titulo} subtitulo={x.subtitulo} redonda={x.tipo === "artista"}
                icono={x.tipo === "artista" ? "persona" : x.tipo === "playlist" ? "lista" : "disco"}
                ancho={x.tipo === "artista" ? "var(--artista)" : "160px"} alTocar={() => abrirTarjeta(x)} />
            {/each}
          </div>
        {/if}
      {:else}
        {#if !linea}
          {#each Array(2) as _}
            <div class="cargando-bloque" style="height:22px;width:55%;margin:28px 0 14px"></div>
            <div class="carrusel">{#each Array(4) as _}<div class="cargando-bloque" style="width:148px;aspect-ratio:1"></div>{/each}</div>
          {/each}
        {:else if d && !d.secciones?.length}
          <p class="vacio">{t("Descarga o escucha algunas canciones y aquí aparecerán recomendaciones para ti.")}</p>
        {/if}
      {/each}

      <div class="titulo-seccion"><span>{t("Explorar")}</span></div>
      <div class="explorar">
        {#each explorar as x}
          <button class="caja-explorar" onclick={() => abrirExplorar(x)}>
            <Icono nombre={x.icono} tam={24} />
            <b>{t(x.texto)}</b>
          </button>
        {/each}
      </div>
    </div>
  {:else if pestana === "tu_musica"}
    <div in:fade={{ duration: 220 }}>
      {#if d && !d.total}
        <p class="vacio">{t("Todavía no tienes canciones. Búscalas arriba y descárgalas.")}</p>
      {/if}
      {#if d?.recientes?.length}
        <div class="titulo-seccion">{t("Escuchado recientemente")}</div>
        <div class="carrusel">
          {#each d.recientes as c, i}
            <Tarjeta portada={c.portada} titulo={c.titulo} subtitulo={c.artista} icono="nota" alMantener={() => menuCancion(c)}
              alTocar={() => reproducir(d.recientes, i, t("Escuchado recientemente"))} />
          {/each}
        </div>
      {/if}
      {#if d?.mas_escuchadas?.length}
        <div class="titulo-seccion">{t("Lo que más escuchas")}</div>
        {#each d.mas_escuchadas.slice(0, 6) as c, i}
          <FilaCancion cancion={c} alTocar={() => reproducir(d.mas_escuchadas, i, t("Lo que más escuchas"))} />
        {/each}
      {/if}
      {#if d?.albumes?.length}
        <div class="titulo-seccion">{t("Tus álbumes")} <button onclick={() => abrir("biblioteca_albumes")}><small>{t("Ver todos")}</small></button></div>
        <div class="carrusel">
          {#each d.albumes as a}
            <Tarjeta portada={a.portada} titulo={a.nombre} subtitulo={a.artista}
              alTocar={() => abrir("album", { local: a })} />
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    {#key pestana}
      <div class="rejilla" in:fade={{ duration: 220 }}>
        {#if tarjetasEstado}
          {#each tarjetasEstado as x}
            <Tarjeta portada={x.miniatura} titulo={x.titulo} subtitulo={x.subtitulo} icono="lista" ancho="100%" alTocar={() => abrirTarjeta(x)} />
          {/each}
        {:else}
          {#each Array(6) as _}<div class="cargando-bloque" style="aspect-ratio:1"></div>{/each}
        {/if}
      </div>
    {/key}
  {/if}
  {/if}
  </div>
</div>

<style>
  .vista { position: relative; padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
  .contenido.suelto { transition: transform 0.25s var(--curva); }
  header { display: flex; align-items: center; justify-content: space-between; }
  .chips {
    display: flex; gap: 10px; margin: var(--margen) calc(-1 * var(--margen)) 4px; padding: 0 var(--margen);
    overflow-x: auto; scrollbar-width: none;
  }
  .chips::-webkit-scrollbar { display: none; }
  .chip { flex-shrink: 0; }
  .chip.suave:not(.activo) { background: transparent; border: 1px solid var(--borde-fuerte); }
  .rejilla { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 14px; margin-top: 18px; }

  .marcacion { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .mosaico { position: relative; border-radius: 10px; overflow: hidden; text-align: left; transition: transform 0.15s var(--curva); }
  .mosaico:active { transform: scale(0.96); }
  .mosaico .sombra { position: absolute; z-index: 1; inset: 45% 0 0; background: linear-gradient(transparent, rgba(0, 0, 0, 0.82)); pointer-events: none; }
  .mosaico b { position: absolute; z-index: 2; left: 8px; right: 8px; bottom: 7px; font-size: 13px; font-weight: 700; color: #fff; text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6); }

  .pildora-borde { height: 32px; padding: 0 14px; border-radius: 999px; border: 1px solid var(--borde-fuerte); font-size: 13.5px; font-weight: 700; }
  .pildora-borde:active { background: var(--tarjeta-2); }
  .filas { --hueco: 18px; }
  .columna { width: min(86vw, 420px); }

  .explorar { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .caja-explorar {
    display: flex; flex-direction: column; align-items: flex-start; gap: 16px; padding: 18px 16px; min-height: 104px;
    border-radius: 16px; background: var(--tarjeta-2); text-align: left; transition: background 0.15s, transform 0.15s var(--curva);
  }
  .caja-explorar b { font-size: 15.5px; font-weight: 700; }
  .caja-explorar:active { transform: scale(0.97); }
  .caja-explorar:hover { background: var(--borde-fuerte); }

  .jalon {
    position: absolute; z-index: 5; left: calc(50% - 20px); top: calc(var(--seguro-arriba) - 34px);
    width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center;
    background: var(--tarjeta-2); color: var(--tenue); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4);
  }
  .jalon.listo { color: var(--cian); }
  .jalon.cargando { color: var(--cian); animation: giro 0.8s linear infinite; }
  @keyframes giro { to { rotate: 360deg; } }
  @media (min-width: 900px) {
    .marcacion { grid-template-columns: repeat(6, minmax(0, 1fr)); }
    .explorar { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  }
</style>
