<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { abrir, atras, aviso } from "../lib/estado.svelte.js";
  import { reproducir } from "../lib/reproductor.svelte.js";
  import Icono from "../componentes/Icono.svelte";
  import { local, t } from "../lib/idioma.svelte.js";
  import Portada from "../componentes/Portada.svelte";

  // Lo que escuchaste en el último mes o los últimos 3 meses, con porcentajes.
  // Cuentan las descargadas y las vistas previas (desde que esta versión empezó a anotarlas).
  let { e } = $props();
  let dias = $state(e.dias ?? 30);
  $effect(() => { e.dias = dias; });
  let datos = $state(e.datos ?? null);
  let hover = $state(null); // { tipo: "dia" | "hora", i } para la etiqueta de la barra bajo el dedo o el mouse

  async function cargar() {
    datos = null;
    try {
      datos = e.datos = await py("estadisticas", { dias });
    } catch (err) {
      aviso(t("No pude calcular tus estadísticas"), "error");
    }
  }
  onMount(() => { if (!datos || datos.dias !== dias) cargar(); });

  function cambiar(n) {
    if (n === dias) return;
    dias = n;
    cargar();
  }

  const numero = (n) => new Intl.NumberFormat(local()).format(n);
  /** "+12 %" / "−30 %" contra el periodo anterior del mismo largo (null si antes no había nada). */
  function cambio(actual, anterior) {
    if (!anterior) return null;
    const p = Math.round(((actual - anterior) / anterior) * 100);
    return { texto: `${p > 0 ? "+" : p < 0 ? "−" : ""}${Math.abs(p)} %`, sube: p > 0, baja: p < 0 };
  }
  const tiles = $derived(datos ? [
    [t("Reproducciones"), datos.actual.reproducciones, datos.anterior.reproducciones],
    [t("Minutos"), datos.actual.minutos, datos.anterior.minutos],
    [t("Canciones distintas"), datos.actual.canciones, datos.anterior.canciones],
    [t("Artistas"), datos.actual.artistas, datos.anterior.artistas],
  ] : []);

  const maxDia = $derived(Math.max(1, ...(datos?.por_dia ?? [])));
  const maxHora = $derived(Math.max(1, ...(datos?.por_hora ?? [])));
  const horaPico = $derived(datos ? datos.por_hora.indexOf(Math.max(...datos.por_hora)) : -1);

  function fechaDia(i) {
    const d = new Date(Date.now() - (dias - 1 - i) * 86400000);
    return d.toLocaleDateString(local(), { day: "numeric", month: "short" });
  }
  const veces = (n) => (n === 1 ? t("1 vez") : t("{n} veces", { n }));
  const etiquetaHover = $derived.by(() => {
    if (!hover || !datos) return "";
    if (hover.tipo === "dia") return `${fechaDia(hover.i)}: ${veces(datos.por_dia[hover.i])}`;
    return `${hover.i}:00 – ${hover.i + 1}:00: ${veces(datos.por_hora[hover.i])}`;
  });

  function tocarCancion(c) {
    if (c.local || c.id) reproducir([c], 0, t("Tus estadísticas"));
  }
</script>

<div class="vista">
  <header>
    <button class="redondo relleno" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
    <h1>{t("Tus estadísticas")}</h1>
  </header>

  <div class="chips">
    <button class="chip" class:activo={dias === 30} onclick={() => cambiar(30)}>{t("Último mes")}</button>
    <button class="chip" class:activo={dias === 90} onclick={() => cambiar(90)}>{t("Últimos 3 meses")}</button>
  </div>

  {#if !datos}
    <div class="tiles">{#each Array(4) as _}<div class="cargando-bloque" style="height:92px"></div>{/each}</div>
    {#each Array(5) as _}<div class="cargando-bloque" style="height:40px;margin:12px 0"></div>{/each}
  {:else if !datos.actual.reproducciones}
    <p class="vacio">{t("Todavía no hay nada que contar en este periodo. Escucha un rato y vuelve.")}</p>
  {:else}
    <div in:fade={{ duration: 220 }}>
      <div class="tiles">
        {#each tiles as [nombre, valor, antes]}
          {@const c = cambio(valor, antes)}
          <div class="tile">
            <small>{nombre}</small>
            <b>{numero(valor)}</b>
            {#if c}<span class="delta" class:sube={c.sube} class:baja={c.baja}>{c.texto} <em>{t("vs. periodo anterior")}</em></span>{/if}
          </div>
        {/each}
      </div>

      <h2>{t("Tus artistas")}</h2>
      <ol class="barras">
        {#each datos.artistas as a, i}
          <li>
            <button class="fila" onclick={() => abrir("artista", { nombre: a.nombre })}>
              <span class="pos">{i + 1}</span>
              <span class="nombre cortar">{a.nombre}</span>
              <span class="valor">{a.pct} %</span>
              <span class="pista" aria-hidden="true"><span class="barra" style:width="{(a.pct / datos.artistas[0].pct) * 100}%"></span></span>
              <small class="veces">{veces(a.veces)}</small>
            </button>
          </li>
        {/each}
      </ol>

      <h2>{t("Tus canciones")}</h2>
      <ol class="barras">
        {#each datos.canciones as c, i}
          <li>
            <button class="fila con-tapa" onclick={() => tocarCancion(c)}>
              <span class="pos">{i + 1}</span>
              <span class="tapa"><Portada url={c.portada} tam="40px" radio="6px" icono="nota" /></span>
              <span class="nombre cortar"><b>{c.titulo}</b> <small>{c.artista}</small></span>
              <span class="valor">{c.pct} %</span>
              <span class="pista" aria-hidden="true"><span class="barra" style:width="{(c.pct / datos.canciones[0].pct) * 100}%"></span></span>
              <small class="veces">{veces(c.veces)}</small>
            </button>
          </li>
        {/each}
      </ol>

      {#if datos.generos.length}
        <h2>{t("Géneros")}</h2>
        <p class="tenue nota">{t("De tus canciones descargadas (las vistas previas no traen género).")}</p>
        <ol class="barras">
          {#each datos.generos as g}
            <li>
              <div class="fila sin-pos">
                <span class="nombre cortar">{g.nombre}</span>
                <span class="valor">{g.pct} %</span>
                <span class="pista" aria-hidden="true"><span class="barra" style:width="{(g.pct / datos.generos[0].pct) * 100}%"></span></span>
              </div>
            </li>
          {/each}
        </ol>
      {/if}

      <h2>{t("Cuándo escuchas")}</h2>
      <p class="tenue nota">{horaPico >= 0 ? t("Tu hora favorita: de {a}:00 a {b}:00", { a: horaPico, b: horaPico + 1 }) : ""}</p>
      <div class="columnas horas" role="img" aria-label={t("Reproducciones por hora del día")} onpointerleave={() => (hover = null)}>
        {#each datos.por_hora as n, i}
          <span class="col" class:activa={hover?.tipo === "hora" && hover.i === i}
            onpointerenter={() => (hover = { tipo: "hora", i })} onpointerdown={() => (hover = { tipo: "hora", i })}
            title="{i}:00 – {i + 1}:00: {veces(n)}">
            <span class="llenado" style:height="{(n / maxHora) * 100}%"></span>
          </span>
        {/each}
      </div>
      <div class="eje"><span>0 h</span><span>6 h</span><span>12 h</span><span>18 h</span><span>23 h</span></div>

      <h2>{t("Día a día")}</h2>
      <p class="tenue nota">{datos.descargas ? t("{n} descargas en este periodo", { n: numero(datos.descargas) }) : ""}</p>
      <div class="columnas dias" role="img" aria-label={t("Reproducciones por día")} onpointerleave={() => (hover = null)}>
        {#each datos.por_dia as n, i}
          <span class="col" class:activa={hover?.tipo === "dia" && hover.i === i}
            onpointerenter={() => (hover = { tipo: "dia", i })} onpointerdown={() => (hover = { tipo: "dia", i })}
            title="{fechaDia(i)}: {veces(n)}">
            <span class="llenado" style:height="{(n / maxDia) * 100}%"></span>
          </span>
        {/each}
      </div>
      <div class="eje"><span>{fechaDia(0)}</span><span>{t("hoy")}</span></div>
      <p class="etiqueta-hover" aria-live="polite">{etiquetaHover || " "}</p>
    </div>
  {/if}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 10px) var(--margen) 24px; }
  header { display: flex; align-items: center; gap: 12px; }
  h1 { margin: 0; font-size: 24px; font-weight: 800; }
  .chips { display: flex; gap: 8px; margin: 18px 0 16px; }
  h2 { font-size: 20px; font-weight: 800; margin: 30px 0 10px; letter-spacing: -0.3px; }
  .nota { margin: -4px 0 10px; font-size: 13.5px; min-height: 1em; }
  .tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .tile { background: var(--tarjeta); border-radius: 16px; padding: 14px 16px; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .tile small { color: var(--tenue); font-size: 13px; }
  .tile b { font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.5px; }
  .delta { font-size: 12.5px; font-weight: 700; color: var(--tenue); }
  .delta em { font-style: normal; font-weight: 400; color: var(--tenue); }
  .delta.sube { color: var(--cian); }
  ol { list-style: none; margin: 0; padding: 0; }
  /* Barras horizontales: una sola serie, un solo color; el texto va en los colores de texto, no en el de la barra */
  .fila {
    width: 100%; display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; grid-template-areas: "pos nombre valor" ". pista veces";
    align-items: center; column-gap: 10px; row-gap: 5px; padding: 8px 4px; text-align: left; border-radius: 10px;
  }
  .fila.con-tapa { grid-template-columns: 22px 40px minmax(0, 1fr) auto; grid-template-areas: "pos tapa nombre valor" ". tapa pista veces"; }
  .tapa { grid-area: tapa; }
  button.fila:hover { background: var(--tarjeta); }
  .pos { grid-area: pos; color: var(--tenue); font-variant-numeric: tabular-nums; text-align: center; }
  .nombre { grid-area: nombre; font-weight: 600; }
  .nombre small { color: var(--tenue); font-weight: 400; }
  .valor { grid-area: valor; font-weight: 700; font-variant-numeric: tabular-nums; }
  .veces { grid-area: veces; color: var(--tenue); font-size: 12.5px; text-align: right; }
  .pista { grid-area: pista; height: 6px; border-radius: 3px; background: var(--tarjeta-2); overflow: hidden; }
  .barra { display: block; height: 100%; min-width: 4px; border-radius: 0 3px 3px 0; background: var(--cian); }
  .fila.sin-pos { grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: "nombre valor" "pista pista"; }
  /* Columnas (por hora / por día): barras ancladas abajo, 2 px de separación */
  .columnas { display: flex; align-items: flex-end; gap: 2px; height: 110px; padding: 0 2px; border-bottom: 1px solid var(--borde); touch-action: pan-y; }
  .col { flex: 1; height: 100%; display: flex; align-items: flex-end; cursor: default; }
  .llenado { display: block; width: 100%; min-height: 2px; border-radius: 3px 3px 0 0; background: var(--cian); opacity: 0.75; transition: opacity 0.15s; }
  .col.activa .llenado, .col:hover .llenado { opacity: 1; }
  .eje { display: flex; justify-content: space-between; color: var(--tenue); font-size: 12px; margin-top: 6px; }
  .etiqueta-hover { min-height: 20px; margin: 10px 0 0; font-weight: 600; font-variant-numeric: tabular-nums; }
  @media (min-width: 900px) {
    .tiles { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  }
</style>
