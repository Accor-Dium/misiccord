<script>
  import { onMount } from "svelte";
  import { py } from "../lib/api.js";
  import { aBody } from "../lib/aBody.js";
  import { cambiarCategorias, categoriasDe, conteoCategorias, datosCategoria } from "../lib/categorias.js";
  import { atras, aviso, mostrarHoja, ui } from "../lib/estado.svelte.js";
  import { canciones as nCanciones, t } from "../lib/idioma.svelte.js";
  import { coincide, normalizar } from "../lib/ordenar.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import ListaVirtual from "../componentes/ListaVirtual.svelte";
  import Portada from "../componentes/Portada.svelte";
  import { memoria } from "./Biblioteca.svelte";

  // Una categoría o década (e.id). Aquí se decide qué va en cada una: buscas, eliges y mueves, o agregas de tu biblioteca.
  let { e } = $props();
  let b = $state.raw(memoria.datos);
  let q = $state(e.q ?? "");
  $effect(() => { e.q = q; });
  const cfg = $derived(b?.categorias ?? {});
  const categoria = $derived(datosCategoria(e.id, cfg));
  let agregando = $state(false); // eligiendo de la biblioteca lo que todavía no está aquí
  const suyas = $derived(!b ? [] : b.canciones.filter((c) => categoriasDe(c, cfg).has(e.id)));
  const fuera = $derived(!b || !agregando ? [] : b.canciones.filter((c) => !categoriasDe(c, cfg).has(e.id)));
  const fuente = $derived(agregando ? fuera : suyas);
  const vistas = $derived(q.trim() ? fuente.filter((c) => coincide(q, c.titulo, c.artista, c.album)) : fuente);
  const otras = $derived.by(() => {
    const { decadas, categorias } = conteoCategorias(b?.canciones ?? [], cfg);
    return [...categorias, ...decadas].filter((c) => c.id !== e.id);
  });

  async function cargar() {
    b = await py("biblioteca");
  }
  onMount(cargar);
  let version = ui.version;
  $effect(() => { if (ui.version !== version) { version = ui.version; cargar(); } });

  // ---------- Elegir y mover ----------
  let seleccionando = $state(false);
  let elegidas = $state(new Set());
  const todas = $derived(vistas.length > 0 && vistas.every((c) => elegidas.has(c.db_id)));

  function alternar(id) {
    const s = new Set(elegidas);
    s.has(id) ? s.delete(id) : s.add(id);
    elegidas = s;
  }
  function salir() {
    seleccionando = false;
    agregando = false;
    elegidas = new Set();
  }
  function empezarAgregar() {
    editando = false;
    agregando = seleccionando = true;
    elegidas = new Set();
    q = "";
  }
  async function aplicar(cambio) {
    const cambios = b.canciones.filter((c) => elegidas.has(c.db_id)).map((c) => ({ id: c.db_id, categorias: cambiarCategorias(c, cfg, cambio) }));
    try {
      await py("categorias_mover", { canciones: cambios });
      aviso(t("{n} canciones movidas", { n: cambios.length }), "ok");
      salir();
      ui.version++;
    } catch (err) {
      aviso(err.message, "error");
    }
  }
  function elegirDestino(titulo, alElegir) {
    if (!otras.length) return aviso(t("Crea otra categoría primero."));
    mostrarHoja({ titulo, opciones: otras.map((c) => ({ texto: t(c.nombre), icono: "ordenar", accion: () => alElegir(c.id) })) });
  }

  // ---------- Editar ----------
  let editando = $state(false);
  let nombre = $state("");
  let generos = $state([]);
  const generosDisponibles = $derived((b?.generos ?? []).map((g) => ({ nombre: g.nombre, clave: normalizar(g.nombre) })));

  function abrirEdicion() {
    salir();
    nombre = t(categoria.nombre);
    generos = [...(categoria.generos ?? [])];
    editando = true;
  }
  function alternarGenero(clave) {
    generos = generos.includes(clave) ? generos.filter((g) => g !== clave) : [...generos, clave];
  }
  async function guardar() {
    const limpio = nombre.trim();
    if (!limpio) return;
    await py("categoria_guardar", { id: e.id, nombre: limpio, generos });
    e.nombre = limpio;
    editando = false;
    ui.version++;
  }
  function eliminar() {
    mostrarHoja({
      titulo: t("¿Eliminar “{nombre}”? Tus canciones no se borran.", { nombre: t(e.nombre) }),
      opciones: [{
        texto: t("Eliminar categoría"), icono: "basura", peligro: true,
        // Las de la app se ocultan: sus reglas siguen ahí por si la quieres de regreso
        accion: async () => {
          if (categoria.deLaApp) await py("categoria_guardar", { id: e.id, nombre: categoria.nombre, generos: categoria.generos, oculta: true });
          else await py("categoria_borrar", { id: e.id });
          ui.version++;
          atras();
        },
      }],
    });
  }
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
    <button class="redondo relleno" class:activo-cian={editando} onclick={() => (editando ? (editando = false) : abrirEdicion())} aria-label={t("Editar categoría")} title={t("Editar categoría")}><Icono nombre="lapiz" tam={21} /></button>
  </header>
  <div class="cab" data-categoria={e.id}>
    <h1>{t(e.nombre)}</h1>
    <p class="tenue">{nCanciones(suyas.length)}</p>
  </div>

  {#if editando}
    <section class="edicion">
      <input class="nombre" bind:value={nombre} placeholder={t("Nombre de la categoría")} aria-label={t("Nombre de la categoría")} />
      <button class="pildora oscura chica" onclick={empezarAgregar}><Icono nombre="agregar" tam={18} /> {t("Agregar canciones de tu biblioteca")}</button>
      <small class="tenue">{t("Géneros que entran solos")}</small>
      <div class="generos">
        {#each generosDisponibles as g (g.clave)}
          <button class="chip" class:activo={generos.includes(g.clave)} onclick={() => alternarGenero(g.clave)}>{g.nombre}</button>
        {/each}
      </div>
      <div class="botones">
        <button class="pildora cian chica" onclick={guardar}>{t("Guardar")}</button>
        <button class="pildora oscura chica rojo" onclick={eliminar}>{t("Eliminar categoría")}</button>
      </div>
    </section>
  {:else}
    <div class="acciones">
      <button class="pildora clara" disabled={!suyas.length} onclick={() => reproducir(vistas, 0, t(e.nombre))}><Icono nombre="play" relleno tam={20} /> {t("Reproducir")}</button>
      <button class="pildora oscura" disabled={!suyas.length} onclick={() => reproducirAleatorio(vistas, t(e.nombre))}><Icono nombre="aleatorio" tam={20} /> {t("Aleatorio")}</button>
      <button class="redondo relleno" class:activo-cian={agregando} onclick={() => (agregando ? salir() : empezarAgregar())} aria-label={t("Agregar canciones")} title={t("Agregar canciones")}><Icono nombre="agregar" tam={24} /></button>
      <button class="redondo relleno" class:activo-cian={seleccionando && !agregando} onclick={() => (seleccionando ? salir() : (seleccionando = true))} aria-label={t("Seleccionar canciones")} title={t("Seleccionar")}><Icono nombre="seleccionar" tam={22} /></button>
    </div>
    {#if agregando}<p class="tenue pista">{t("Elige qué agregar a “{nombre}”", { nombre: t(e.nombre) })}</p>{/if}
    <form class="buscador" role="search" onsubmit={(ev) => { ev.preventDefault(); document.activeElement?.blur(); }}>
      <Icono nombre="buscar" tam={19} />
      <input bind:value={q} placeholder={t("Busca canciones, artistas o álbumes aquí")} enterkeyhint="search" />
      {#if q}<button type="button" onclick={() => (q = "")} aria-label={t("Borrar búsqueda")}><Icono nombre="cerrar" tam={17} /></button>{/if}
    </form>
    {#if seleccionando}
      <button class="texto-boton" onclick={() => (elegidas = todas ? new Set() : new Set(vistas.map((c) => c.db_id)))}>{todas ? t("Quitar todas") : t("Elegir todas")}</button>
    {/if}
    <ListaVirtual items={vistas} clave={(c) => c.db_id} tipo={seleccionando ? "categoria-eleccion" : "categoria"}>
      {#snippet fila(c)}
        {#if seleccionando}
          <button class="fila-eleccion" class:elegida={elegidas.has(c.db_id)} onclick={() => alternar(c.db_id)}>
            <span class="casilla">{#if elegidas.has(c.db_id)}<Icono nombre="check" tam={16} />{/if}</span>
            <Portada url={c.portada} tam="46px" radio="8px" />
            <span class="textos"><b class="cortar">{c.titulo}</b><small class="cortar">{[c.artista, c.album].filter(Boolean).join(" · ")}</small></span>
          </button>
        {:else}
          <FilaCancion cancion={c} alTocar={() => reproducir(vistas, vistas.indexOf(c), t(e.nombre))} />
        {/if}
      {/snippet}
    </ListaVirtual>
    {#if b && !vistas.length}<p class="vacio">{q.trim() ? t("Nada con “{q}”.", { q: q.trim() }) : t("Nada con este filtro.")}</p>{/if}
  {/if}
</div>

{#if seleccionando && elegidas.size}
  <div class="barra-seleccion" use:aBody>
    <b>{elegidas.size === 1 ? t("1 elegido") : t("{n} elegidos", { n: elegidas.size })}</b>
    <div class="botones">
      {#if agregando}
        <button class="pildora cian chica" onclick={() => aplicar({ poner: e.id })}>{t("Agregar aquí")}</button>
      {:else}
        <button class="pildora oscura chica" onclick={() => elegirDestino(t("Mover a otra categoría"), (id) => aplicar({ poner: id, quitar: e.id }))}>{t("Mover a…")}</button>
        <button class="pildora oscura chica" onclick={() => elegirDestino(t("Agregar a otra categoría"), (id) => aplicar({ poner: id }))}>{t("Agregar a…")}</button>
        <button class="pildora oscura chica rojo" onclick={() => aplicar({ quitar: e.id })}>{t("Quitar de aquí")}</button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  header { display: flex; align-items: center; justify-content: space-between; }
  .cab { text-align: center; margin-top: 8px; }
  h1 { margin: 0; font-size: 30px; font-weight: 800; }
  .cab p { margin: 6px 0 0; }
  .acciones { display: flex; gap: 10px; justify-content: center; align-items: center; margin: 18px 0 12px; }
  .acciones .pildora { flex: 1; max-width: 170px; }
  .buscador { display: flex; align-items: center; gap: 10px; height: 44px; margin-bottom: 10px; padding: 0 12px; border-radius: 12px; background: var(--tarjeta); border: 1px solid var(--borde); color: var(--tenue); }
  .buscador:focus-within { border-color: var(--cian); }
  .buscador input { flex: 1; min-width: 0; height: 100%; border: 0; outline: 0; background: transparent; color: var(--texto); font-size: 15.5px; }
  .buscador button { display: grid; place-items: center; color: var(--tenue); }
  .pista { margin: 0 0 10px; text-align: center; font-size: 14px; }
  .texto-boton { color: var(--cian); font-weight: 600; padding: 4px 0 8px; }
  .fila-eleccion { width: 100%; display: flex; align-items: center; gap: 12px; padding: 7px 6px; border-radius: 12px; text-align: left; }
  .fila-eleccion.elegida { background: rgba(34, 211, 238, 0.08); }
  .casilla { width: 24px; height: 24px; border-radius: 7px; border: 2px solid var(--borde-fuerte); display: grid; place-items: center; flex-shrink: 0; color: #04121a; }
  .elegida .casilla { background: var(--cian); border-color: var(--cian); }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .textos small { color: var(--tenue); }
  .chica { height: 38px; padding: 0 14px; font-size: 14px; }
  .rojo { color: var(--rojo); }
  .activo-cian { color: var(--cian); background: rgba(34, 211, 238, 0.12); }
  .edicion { display: flex; flex-direction: column; gap: 12px; margin-top: 18px; }
  .nombre { height: 46px; padding: 0 14px; border-radius: 12px; outline: 0; border: 1px solid var(--borde-fuerte); background: var(--tarjeta); font-size: 16px; font-weight: 700; }
  .nombre:focus { border-color: var(--cian); }
  .generos { display: flex; flex-wrap: wrap; gap: 8px; }
  .botones { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  /* Va encima del mini reproductor mientras eliges, como en Biblioteca */
  .barra-seleccion {
    position: fixed; z-index: 32; left: 10px; right: 10px; bottom: calc(var(--nav) + var(--seguro-abajo) + 6px);
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding: 10px 14px;
    border-radius: 18px; background: rgba(28, 42, 53, 0.98); backdrop-filter: blur(22px); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
  }
  @media (orientation: landscape) and (max-height: 560px) {
    .barra-seleccion { left: calc(var(--riel) + 10px); right: calc(10px + env(safe-area-inset-right, 0px)); bottom: calc(var(--seguro-abajo) + 8px); }
  }
  @media (min-width: 900px) and (min-height: 561px) {
    .barra-seleccion { left: calc(var(--lateral) + 16px); right: 16px; bottom: 16px; }
  }
</style>
