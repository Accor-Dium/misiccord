<script>
  import { onMount } from "svelte";
  import { local as fechaLocal, t } from "../lib/idioma.svelte.js";
  import { py } from "../lib/api.js";
  import { atras } from "../lib/estado.svelte.js";
  import { reproducir } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";

  // Lo que has escuchado, tuyo o en línea, de lo más reciente a lo más viejo y por día. Cada vez que sonó cuenta
  // (a los 30 s, o a la mitad si es corta): si la escuchaste tres veces hoy, sale tres veces.
  let { e } = $props();
  let error = $state(false);
  const canciones = $derived(e.datos ?? []);

  /** "Hoy", "Ayer" o la fecha */
  function dia(segundos) {
    const f = new Date(segundos * 1000);
    const hoy = new Date();
    const ayer = new Date(hoy.getTime() - 86400000);
    const mismo = (a, b) => a.toDateString() === b.toDateString();
    if (mismo(f, hoy)) return t("Hoy");
    if (mismo(f, ayer)) return t("Ayer");
    return f.toLocaleDateString(fechaLocal(), { weekday: "long", day: "numeric", month: "long", year: f.getFullYear() === hoy.getFullYear() ? undefined : "numeric" });
  }
  const hora = (segundos) => new Date(segundos * 1000).toLocaleTimeString(fechaLocal(), { hour: "numeric", minute: "2-digit" });
  const grupos = $derived.by(() => {
    const salida = [];
    for (const c of canciones) {
      const d = dia(c.escuchada);
      if (salida.at(-1)?.dia !== d) salida.push({ dia: d, canciones: [] });
      salida.at(-1).canciones.push(c);
    }
    return salida;
  });

  async function cargar() {
    error = false;
    try {
      e.datos = (await py("historial", { limite: 500 })).canciones;
    } catch {
      error = true;
    }
  }
  onMount(cargar); // siempre de nuevo: lo de hace un momento también debe salir

  function tocar(c) {
    const i = canciones.indexOf(c);
    reproducir(canciones, i, t("Historial"));
  }
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
    <h1>{t("Historial")}</h1>
  </header>
  {#if error}
    <p class="tenue">{t("No se pudo leer el historial.")} <button class="reintentar" onclick={cargar}>{t("Reintentar")}</button></p>
  {:else if !e.datos}
    {#each Array(6) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}
  {/if}
  {#each grupos as g (g.dia)}
    <div class="dia">{g.dia}</div>
    {#each g.canciones as c (c.escuchada + "|" + (c.db_id ?? c.id))}
      <div class="fila">
        <FilaCancion cancion={c} alTocar={() => tocar(c)} />
        <small class="hora tenue">{hora(c.escuchada)}</small>
      </div>
    {/each}
  {:else}
    {#if e.datos && !error}<p class="vacio">{t("Todavía no has escuchado nada. Lo que suene (tuyo o en línea) aparecerá aquí.")}</p>{/if}
  {/each}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 0; }
  header { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
  h1 { margin: 0; font-size: 24px; font-weight: 800; }
  .dia { padding: 18px 0 4px; font-size: 15px; font-weight: 800; color: var(--cian); }
  .dia::first-letter { text-transform: uppercase; }
  .fila { position: relative; }
  /* La hora va arriba a la derecha de la fila, sin empujar sus botones */
  .hora { position: absolute; top: 2px; right: 0; font-size: 11.5px; pointer-events: none; }
  .reintentar { color: var(--cian); font-weight: 700; }
</style>
