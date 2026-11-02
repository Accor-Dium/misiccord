<script>
  import { onMount } from "svelte";
  import { py } from "../lib/api.js";
  import { atras, abrir, mostrarHoja } from "../lib/estado.svelte.js";
  import { canciones as nCanciones, t } from "../lib/idioma.svelte.js";
  import { agrupar, coincide, normalizar } from "../lib/ordenar.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import ListaVirtual from "../componentes/ListaVirtual.svelte";
  import Portada from "../componentes/Portada.svelte";

  // Todas las canciones de un artista: lo tuyo y lo de YouTube Music juntos. Por defecto por disco, del más nuevo al más
  // viejo, como en Spotify. El buscador filtra aquí mismo: solo canciones de este artista.
  // Se abre con e.lista (la lista de YouTube Music), e.nombre, e.tuyas y e.discos (de la página del artista).
  let { e } = $props();
  let enLinea = $state.raw(e.enLinea ?? null);
  let cargando = $state(!e.enLinea);
  let error = $state(false);
  let q = $state(e.q ?? "");
  $effect(() => { e.q = q; });

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
  const todas = $derived.by(() => {
    if (!enLinea) return [];
    const titulos = new Set(enLinea.map((c) => normalizar(c.titulo)));
    const vistos = new Set();
    return [...tuyas.filter((c) => !titulos.has(normalizar(c.titulo))), ...enLinea].filter((c) => {
      const clave = c.db_id ?? c.id;
      return !vistos.has(clave) && vistos.add(clave); // YouTube repite alguna: las listas van con clave
    });
  });
  const vistas = $derived(q.trim() ? todas.filter((c) => coincide(q, c.titulo, c.album)) : todas);
  const discos = $derived(new Map((e.discos ?? []).map((d) => [normalizar(d.titulo), d])));

  /** Por disco: el año y la carátula salen de la discografía; lo que no esté ahí va al final. */
  function porDisco(canciones) {
    const grupos = new Map();
    for (const c of canciones) {
      const clave = normalizar(c.album);
      if (!grupos.has(clave)) {
        const d = discos.get(clave);
        grupos.set(clave, { titulo: c.album || t("Sin álbum"), canciones: [], anio: d?.anio || c.anio || "", portada: d?.miniatura ?? c.portada, id: d?.browse_id });
      }
      grupos.get(clave).canciones.push(c);
    }
    return [...grupos.values()].sort((x, y) => String(y.anio).localeCompare(String(x.anio)) || x.titulo.localeCompare(y.titulo));
  }
  const grupos = $derived(
    orden === "discos" ? porDisco(vistas)
    : orden === "duracion" ? (vistas.length ? [{ titulo: "", canciones: [...vistas].sort((x, y) => (y.duracion ?? 0) - (x.duracion ?? 0)) }] : [])
    : agrupar(vistas, orden));
  const plana = $derived(grupos.flatMap((g) => g.canciones)); // en el orden en que se ven: así suena la cola
  const conDisco = $derived(orden === "discos" || orden === "album");

  async function cargar() {
    cargando = true;
    error = false;
    try {
      enLinea = e.enLinea = (await py("artista_canciones", { lista: e.lista })).canciones;
    } catch {
      error = true;
    } finally {
      cargando = false;
    }
  }
  onMount(() => { if (!e.enLinea) cargar(); });
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
    <button class="redondo relleno" onclick={opcionesOrden} aria-label={t("Ordenar y agrupar")} title={t("Ordenar y agrupar")}><Icono nombre="ordenar" tam={22} /></button>
  </header>
  <h1>{e.nombre}</h1>
  <p class="tenue cuenta">{q.trim() ? t("{n} de {total} canciones", { n: vistas.length, total: todas.length }) : nCanciones(todas.length)}</p>
  <div class="acciones">
    <button class="pildora clara" disabled={!plana.length} onclick={() => reproducir(plana, 0, e.nombre)}><Icono nombre="play" relleno tam={20} /> {t("Reproducir")}</button>
    <button class="pildora oscura" disabled={!plana.length} onclick={() => reproducirAleatorio(plana, e.nombre)}><Icono nombre="aleatorio" tam={20} /> {t("Aleatorio")}</button>
  </div>
  <form class="buscador" role="search" onsubmit={(ev) => { ev.preventDefault(); document.activeElement?.blur(); }}>
    <Icono nombre="buscar" tam={19} />
    <input bind:value={q} placeholder={t("Busca en las canciones de {nombre}", { nombre: e.nombre })} enterkeyhint="search" />
    {#if q}<button type="button" onclick={() => (q = "")} aria-label={t("Borrar búsqueda")}><Icono nombre="cerrar" tam={17} /></button>{/if}
  </form>

  {#if cargando}
    {#each Array(6) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
  {:else if error}
    <p class="tenue">{t("No se pudieron traer sus canciones.")} <button class="reintentar" onclick={cargar}>{t("Reintentar")}</button></p>
  {:else}
    {#each grupos as g (g.titulo)}
      {#if orden === "discos"}
        <button class="disco" disabled={!g.id} onclick={() => abrir("album", { id: g.id })}>
          <Portada url={g.portada} tam="52px" radio="8px" icono="disco" />
          <span class="textos"><b class="cortar">{g.titulo}</b><small>{[g.anio, nCanciones(g.canciones.length)].filter(Boolean).join(" · ")}</small></span>
        </button>
      {:else if g.titulo}
        <div class="grupo">{g.titulo}</div>
      {/if}
      <ListaVirtual items={g.canciones} clave={(c) => c.db_id ?? c.id} tipo={conDisco ? "artista-disco" : "artista-canciones"}>
        {#snippet fila(c)}
          <FilaCancion cancion={c} sinPortada={conDisco} alTocar={() => reproducir(plana, plana.indexOf(c), e.nombre)} />
        {/snippet}
      </ListaVirtual>
    {:else}
      <p class="tenue">{t("Nada con “{q}”.", { q: q.trim() })}</p>
    {/each}
  {/if}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  header { display: flex; align-items: center; justify-content: space-between; }
  h1 { margin: 10px 0 0; font-size: 30px; font-weight: 800; text-align: center; }
  .cuenta { margin: 6px 0 0; text-align: center; }
  .acciones { display: flex; gap: 12px; justify-content: center; margin: 16px 0 12px; }
  .acciones .pildora { flex: 1; max-width: 170px; }
  .buscador { display: flex; align-items: center; gap: 10px; height: 44px; margin-bottom: 8px; padding: 0 12px; border-radius: 12px; background: var(--tarjeta); border: 1px solid var(--borde); color: var(--tenue); }
  .buscador:focus-within { border-color: var(--cian); }
  .buscador input { flex: 1; min-width: 0; height: 100%; border: 0; outline: 0; background: transparent; color: var(--texto); font-size: 15.5px; }
  .buscador button { display: grid; place-items: center; color: var(--tenue); }
  .disco { width: 100%; display: flex; align-items: center; gap: 12px; margin-top: 18px; padding: 4px 0; text-align: left; }
  .disco:disabled { opacity: 1; cursor: default; }
  .textos { min-width: 0; display: flex; flex-direction: column; }
  .textos b { font-size: 16.5px; font-weight: 800; }
  .textos small { color: var(--tenue); font-size: 13.5px; }
  .grupo { padding: 14px 0 4px; font-size: 15px; font-weight: 800; color: var(--cian); }
  .reintentar { color: var(--cian); font-weight: 700; }
</style>
