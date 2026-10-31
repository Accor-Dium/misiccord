<script>
  import { onMount } from "svelte";
  import { py } from "../lib/api.js";
  import { atras, aviso, ui } from "../lib/estado.svelte.js";
  import { aJpeg } from "../lib/imagen.js";
  import { canciones as nCanciones, t } from "../lib/idioma.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";

  let { e } = $props();
  const canciones = $derived(e.datos ?? []);
  let editando = $state(false);
  let nombre = $state(e.nombre);

  async function cargar() {
    e.datos = (await py("playlist", { id: e.id })).canciones;
  }
  onMount(() => { if (!e.datos) cargar(); });
  let version = ui.version;
  $effect(() => { if (ui.version !== version) { version = ui.version; cargar(); } });

  async function quitar(c) {
    await py("quitar_de_playlist", { id: e.id, db_ids: [c.db_id] });
    aviso(t("Se quitó “{titulo}”", c));
    cargar();
  }

  async function borrar() {
    await py("borrar_playlist", { id: e.id });
    aviso(t("Playlist “{nombre}” eliminada", e));
    ui.version++;
    atras();
  }

  // ---------- Editar ----------
  async function terminar() {
    const limpio = nombre.trim();
    if (limpio && limpio !== e.nombre) {
      try {
        await py("renombrar_playlist", { id: e.id, nombre: limpio });
        e.nombre = limpio;
        ui.version++;
      } catch {
        aviso(t("Ya existe una playlist con ese nombre"), "error");
        return;
      }
    }
    editando = false;
  }

  async function ponerPortada(imagen) {
    try {
      e.portada = (await py("portada_playlist", { id: e.id, imagen })).portada;
      ui.version++;
    } catch (err) {
      aviso(err.message, "error");
    }
  }

  async function elegirImagen(ev) {
    const archivo = ev.currentTarget.files?.[0];
    ev.currentTarget.value = "";
    if (!archivo) return;
    try {
      ponerPortada(await aJpeg(archivo));
    } catch {
      aviso(t("No pude usar esa imagen"), "error");
    }
  }

  let arrastre = $state(null); // { desde, sobre, y0, dy, alto }, como en Cola.svelte

  function agarrar(ev, i) {
    ev.preventDefault();
    ev.currentTarget.setPointerCapture(ev.pointerId);
    arrastre = { desde: i, sobre: i, y0: ev.clientY, dy: 0, alto: ev.currentTarget.closest(".orden").offsetHeight };
  }
  function arrastrar(ev) {
    if (!arrastre) return;
    arrastre.dy = ev.clientY - arrastre.y0;
    arrastre.sobre = Math.max(0, Math.min(canciones.length - 1, arrastre.desde + Math.round(arrastre.dy / arrastre.alto)));
  }
  function soltar() {
    if (!arrastre) return;
    const { desde, sobre } = arrastre;
    arrastre = null;
    if (sobre === desde) return;
    const lista = [...canciones];
    lista.splice(sobre, 0, lista.splice(desde, 1)[0]);
    e.datos = lista;
    py("ordenar_playlist", { id: e.id, db_ids: lista.map((c) => c.db_id) }).catch((err) => aviso(err.message, "error"));
  }
  /** La fila que arrastras sigue al dedo y las demás le hacen espacio. */
  function corrimiento(i) {
    const a = arrastre;
    if (!a) return 0;
    if (i === a.desde) return a.dy;
    if (a.desde < a.sobre && i > a.desde && i <= a.sobre) return -a.alto;
    if (a.desde > a.sobre && i < a.desde && i >= a.sobre) return a.alto;
    return 0;
  }
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
    {#if editando}
      <button class="pildora cian chica" onclick={terminar}>{t("Listo")}</button>
    {:else}
      <button class="redondo relleno" onclick={() => { nombre = e.nombre; editando = true; }} aria-label={t("Editar playlist")} title={t("Editar playlist")}><Icono nombre="lapiz" tam={21} /></button>
    {/if}
  </header>
  <div class="cab">
    {#if e.portada}
      <div class="tapa"><Portada url={e.portada} radio="12px" icono="lista" sombra /></div>
    {:else}
      <div class="mosaico">
        {#each [0, 1, 2, 3] as i}<Portada url={canciones[i]?.portada} radio="0" icono="nota" />{/each}
      </div>
    {/if}
    {#if editando}
      <div class="botones-tapa">
        <label class="pildora oscura chica"><Icono nombre="camara" tam={18} /> {t("Cambiar carátula")}<input type="file" accept="image/*" hidden onchange={elegirImagen} /></label>
        {#if e.portada}<button class="pildora oscura chica" onclick={() => ponerPortada(null)}>{t("Quitar carátula")}</button>{/if}
      </div>
      <input class="nombre" bind:value={nombre} placeholder={t("Nombre de la playlist")} aria-label={t("Nombre de la playlist")} />
    {:else}
      <h1>{e.nombre}</h1>
    {/if}
    <p class="tenue">{nCanciones(canciones.length)}</p>
  </div>
  {#if editando}
    {#each canciones as c, i (c.db_id)}
      <div class="orden" class:levantada={arrastre?.desde === i} style:transform="translateY({corrimiento(i)}px)"
        style:transition={arrastre && arrastre.desde !== i ? "transform 0.15s" : null}>
        <Portada url={c.portada} tam="44px" radio="8px" icono="nota" />
        <span class="textos"><b class="cortar">{c.titulo}</b><small class="cortar">{c.artista}</small></span>
        <button class="asa" aria-label={t("Mover {titulo}", c)}
          onpointerdown={(ev) => agarrar(ev, i)} onpointermove={arrastrar} onpointerup={soltar} onpointercancel={() => (arrastre = null)}>
          <Icono nombre="arrastrar" tam={20} />
        </button>
      </div>
    {/each}
  {:else}
    <div class="acciones">
      <button class="pildora clara" disabled={!canciones.length} onclick={() => reproducir(canciones, 0, e.nombre)}><Icono nombre="play" relleno tam={20} /> {t("Reproducir")}</button>
      <button class="pildora oscura" disabled={!canciones.length} onclick={() => reproducirAleatorio(canciones, e.nombre)}><Icono nombre="aleatorio" tam={20} /> {t("Aleatorio")}</button>
    </div>
    {#each canciones as c, i}
      <FilaCancion cancion={c} alTocar={() => reproducir(canciones, i, e.nombre)}
        extras={[{ texto: t("Quitar de esta playlist"), icono: "cerrar", accion: () => quitar(c) }]} />
    {:else}
      <p class="vacio">{t("Agrega canciones desde el menú ⋯ de cualquier canción de tu biblioteca.")}</p>
    {/each}
    <button class="borrar" onclick={borrar}>{t("Eliminar playlist")}</button>
  {/if}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  header { display: flex; align-items: center; justify-content: space-between; }
  .cab { text-align: center; margin-top: 4px; }
  .mosaico { width: 56%; max-width: 260px; margin: 0 auto 18px; display: grid; grid-template-columns: 1fr 1fr; border-radius: 12px; overflow: hidden; box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5); }
  .tapa { width: 56%; max-width: 260px; margin: 0 auto 18px; }
  h1 { margin: 0; font-size: 26px; font-weight: 800; }
  .cab p { margin: 6px 0 0; }
  .acciones { display: flex; gap: 12px; justify-content: center; margin: 20px 0 12px; }
  .acciones .pildora { flex: 1; max-width: 170px; }
  .borrar { display: block; margin: 28px auto 8px; color: var(--rojo); font-weight: 600; }
  .chica { height: 38px; padding: 0 16px; font-size: 14px; }
  .botones-tapa { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-bottom: 12px; }
  .botones-tapa label { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
  .nombre {
    width: 100%; height: 46px; box-sizing: border-box; padding: 0 14px; border-radius: 12px; outline: 0; text-align: center;
    border: 1px solid var(--borde-fuerte); background: var(--tarjeta); font-size: 18px; font-weight: 700;
  }
  .nombre:focus { border-color: var(--cian); }
  .orden { position: relative; display: flex; align-items: center; gap: 12px; padding: 7px 0; background: var(--fondo); }
  .orden.levantada { z-index: 2; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45); }
  .orden:first-of-type { margin-top: 14px; }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; text-align: left; }
  .textos small { color: var(--tenue); }
  .asa { width: 44px; height: 44px; display: grid; place-items: center; color: var(--tenue); touch-action: none; cursor: grab; flex-shrink: 0; }
</style>
