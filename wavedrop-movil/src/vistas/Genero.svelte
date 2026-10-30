<script>
  import { onMount } from "svelte";
  import { py } from "../lib/api.js";
  import { atras, ui } from "../lib/estado.svelte.js";
  import { canciones as nCanciones, t } from "../lib/idioma.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import ListaVirtual from "../componentes/ListaVirtual.svelte";

  // Las canciones de un género de tu biblioteca (no necesita internet).
  let { e } = $props();
  let canciones = $state.raw([]);

  async function cargar() {
    canciones = (await py("genero_local", { nombre: e.nombre })).canciones;
  }
  onMount(cargar);
  let version = ui.version;
  $effect(() => { if (ui.version !== version) { version = ui.version; cargar(); } });
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
    <div class="titulos">
      <h1 class="cortar">{e.nombre}</h1>
      <small class="tenue">{nCanciones(canciones.length)}</small>
    </div>
  </header>
  <div class="acciones">
    <button class="pildora clara" disabled={!canciones.length} onclick={() => reproducir(canciones, 0, e.nombre)}><Icono nombre="play" relleno tam={20} /> {t("Reproducir")}</button>
    <button class="pildora oscura" disabled={!canciones.length} onclick={() => reproducirAleatorio(canciones, e.nombre)}><Icono nombre="aleatorio" tam={20} /> {t("Aleatorio")}</button>
  </div>
  <ListaVirtual items={canciones} clave={(c) => c.db_id} tipo="genero-fila">
    {#snippet fila(c)}
      <FilaCancion cancion={c} alTocar={() => reproducir(canciones, canciones.indexOf(c), e.nombre)} />
    {/snippet}
  </ListaVirtual>
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  header { display: flex; align-items: center; gap: 12px; }
  .titulos { min-width: 0; display: flex; flex-direction: column; }
  h1 { margin: 0; font-size: 24px; font-weight: 800; }
  .acciones { display: flex; gap: 12px; margin: 18px 0 12px; }
  .acciones .pildora { flex: 1; max-width: 170px; }
</style>
