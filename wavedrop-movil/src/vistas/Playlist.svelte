<script>
  import { onMount } from "svelte";
  import { py } from "../lib/api.js";
  import { atras, aviso, ui } from "../lib/estado.svelte.js";
  import { canciones as nCanciones, t } from "../lib/idioma.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";

  let { e } = $props();
  const canciones = $derived(e.datos ?? []);

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
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
  </header>
  <div class="cab">
    <div class="mosaico">
      {#each [0, 1, 2, 3] as i}<Portada url={canciones[i]?.portada} radio="0" icono="nota" />{/each}
    </div>
    <h1>{e.nombre}</h1>
    <p class="tenue">{nCanciones(canciones.length)}</p>
  </div>
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
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  .cab { text-align: center; margin-top: 4px; }
  .mosaico { width: 56%; max-width: 260px; margin: 0 auto 18px; display: grid; grid-template-columns: 1fr 1fr; border-radius: 12px; overflow: hidden; box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5); }
  h1 { margin: 0; font-size: 26px; font-weight: 800; }
  .cab p { margin: 6px 0 0; }
  .acciones { display: flex; gap: 12px; justify-content: center; margin: 20px 0 12px; }
  .acciones .pildora { flex: 1; max-width: 170px; }
  .borrar { display: block; margin: 28px auto 8px; color: var(--rojo); font-weight: 600; }
</style>
