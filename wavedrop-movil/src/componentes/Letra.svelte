<script>
  import { t } from "../lib/idioma.svelte.js";
  import { py } from "../lib/api.js";
  import { ui } from "../lib/estado.svelte.js";
  import { irA, rep } from "../lib/reproductor.svelte.js";

  // Letra sincronizada: resalta la línea actual y se desplaza sola; toca una línea para saltar ahí.
  // Arriba dice el idioma original y deja prender o apagar la romanización y la traducción (Ajustes → Letras).
  let estado = $state("cargando");
  let lineas = $state([]);
  let sincronizada = $state(false);
  let info = $state({ idioma: "", nombre: "", fuente: "", romanizacion: null });
  let traduccion = $state(null);
  let estadoTraduccion = $state(""); // "" | "cargando" | "error"
  let errorTraduccion = $state("");
  let contenedor = $state();
  let alto = $state(0);
  let clave = "";

  // Interruptores de la barra (por defecto los de Ajustes; se recuerdan mientras la app está abierta)
  let verRom = $state(ui.letra.romanizar);
  let verTrad = $state(true);
  $effect(() => { verRom = ui.letra.romanizar; });

  $effect(() => {
    const c = rep.actual;
    const ruta = c?.ruta || null;
    const k = (ruta || c?.id) + "|" + c?.titulo;
    if (!c || (!ruta && !c.id) || k === clave) return;
    clave = k;
    estado = "cargando";
    traduccion = null;
    estadoTraduccion = "";
    py("letra", { ruta, id: c.id, titulo: c.titulo, artista: c.artista, album: c.album || "", duracion: c.duracion })
      .then((r) => {
        if (clave !== k) return;
        lineas = r.lineas;
        sincronizada = r.tipo === "sincronizada";
        info = { idioma: r.idioma, nombre: r.idioma_nombre, fuente: r.fuente, romanizacion: r.romanizacion ?? null };
        estado = r.lineas.length ? "lista" : r.tipo;
      })
      .catch(() => (estado = "error"));
  });

  const destino = $derived(ui.letra.traducirA);
  const sePuedeTraducir = $derived(estado === "lista" && !!destino && !!info.idioma && info.idioma !== destino);

  // La traducción se pide solo si está prendida (cuesta del límite diario gratis)
  $effect(() => {
    if (!sePuedeTraducir || !verTrad || traduccion || estadoTraduccion) return;
    const k = clave;
    estadoTraduccion = "cargando";
    py("letra_traduccion", { lineas: lineas.map(([, t]) => t), origen: info.idioma, destino })
      .then((r) => {
        if (clave !== k) return;
        traduccion = r.traduccion;
        estadoTraduccion = "";
      })
      .catch((e) => {
        if (clave !== k) return;
        estadoTraduccion = "error";
        errorTraduccion = e.message;
      });
  });
  // Si cambias el idioma en Ajustes, se vuelve a traducir
  let destinoAnterior = destino;
  $effect(() => {
    if (destino === destinoAnterior) return;
    destinoAnterior = destino;
    traduccion = null;
    estadoTraduccion = "";
  });

  const actual = $derived.by(() => {
    if (!sincronizada) return -1;
    const ms = rep.pos * 1000 + 150;
    let i = -1;
    for (let j = 0; j < lineas.length; j++) {
      if (lineas[j][0] <= ms) i = j;
      else break;
    }
    return i;
  });

  $effect(() => {
    if (actual < 0 || !contenedor) return;
    const linea = contenedor.querySelector(`[data-i="${actual}"]`);
    // Solo se mueve la caja de la letra: scrollIntoView también corría al reproductor entero (y se cortaba arriba)
    if (linea) contenedor.scrollTo({ top: linea.offsetTop - contenedor.clientHeight / 2 + linea.offsetHeight / 2, behavior: "smooth" });
  });
</script>

<div class="caja">
  {#if estado === "lista" && (info.nombre || info.romanizacion || sePuedeTraducir)}
    <div class="barra-letra">
      {#if info.nombre}<span class="idioma">{info.nombre}</span>{/if}
      {#if info.romanizacion}
        <button class="interruptor" class:on={verRom} onclick={() => (verRom = !verRom)} aria-pressed={verRom}>{t("Romanización")}</button>
      {/if}
      {#if sePuedeTraducir}
        <button class="interruptor" class:on={verTrad} onclick={() => (verTrad = !verTrad)} aria-pressed={verTrad}>
          {estadoTraduccion === "cargando" && verTrad ? t("Traduciendo…") : t("Traducción")}
        </button>
      {/if}
    </div>
    {#if verTrad && estadoTraduccion === "error"}<p class="error-traduccion">{errorTraduccion}</p>{/if}
  {/if}

  <div class="letra" bind:this={contenedor} bind:clientHeight={alto}>
    <!-- Espacio para que la primera y la última línea puedan quedar al centro. Va medido en px con el alto real de la
         caja: con padding en vh la caja crecía más que su lugar y en el cel tapaba la barra para adelantar -->
    <div class="hueco" style:height="{Math.round(alto * 0.4)}px"></div>
    {#if estado === "cargando"}
      <p class="aviso">{t("Buscando letra…")}</p>
    {:else if estado === "instrumental"}
      <p class="aviso">♪ {t("Canción instrumental")}</p>
    {:else if estado === "lista"}
      {#each lineas as [ms, texto], i}
        <button
          data-i={i}
          class="linea"
          class:actual={i === actual}
          class:pasada={sincronizada && i < actual}
          class:libre={!sincronizada}
          onclick={() => sincronizada && irA(ms / 1000)}
        >
          {texto || "♪"}
          {#if verRom && info.romanizacion?.[i]}<span class="extra rom">{info.romanizacion[i]}</span>{/if}
          {#if verTrad && traduccion?.[i]}<span class="extra trad">{traduccion[i]}</span>{/if}
        </button>
      {/each}
      {#if info.fuente}<p class="fuente">{t("Letra de {fuente}", { fuente: info.fuente })}</p>{/if}
    {:else}
      <p class="aviso">{t("No encontré la letra de esta canción.")}</p>
    {/if}
    <div class="hueco" style:height="{Math.round(alto * 0.55)}px"></div>
  </div>
</div>

<style>
  .caja { height: 100%; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
  .barra-letra { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 2px 0 8px; }
  .idioma { font-size: 12px; letter-spacing: 1.2px; text-transform: uppercase; font-weight: 700; color: rgba(255, 255, 255, 0.6); margin-right: auto; }
  .interruptor {
    height: 30px; padding: 0 12px; border-radius: 999px; font-size: 13px; font-weight: 700;
    background: rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.7); transition: background 0.2s, color 0.2s;
  }
  .interruptor.on { background: #fff; color: #04121a; }
  .error-traduccion { margin: 0 0 6px; font-size: 13px; color: rgba(255, 255, 255, 0.6); }
  .letra {
    flex: 1; min-height: 0; overflow-y: auto; padding: 0 4px; scrollbar-width: none; position: relative;
    /* Abajo se desvanece antes y más fuerte: si no, las líneas se encimaban con el título de la canción */
    mask-image: linear-gradient(transparent, #000 12%, #000 58%, rgba(0, 0, 0, 0.35) 78%, transparent 94%);
  }
  .hueco { flex-shrink: 0; pointer-events: none; }
  .letra::-webkit-scrollbar { display: none; }
  .linea {
    display: block; width: 100%; text-align: left; font-size: 25px; font-weight: 800; line-height: 1.3;
    padding: 8px 0; color: rgba(255, 255, 255, 0.38); transition: color 0.4s, transform 0.4s var(--curva);
    transform-origin: left center;
  }
  .linea.pasada { color: rgba(255, 255, 255, 0.22); }
  .linea.actual { color: #fff; transform: scale(1.03); }
  .linea.libre { color: rgba(255, 255, 255, 0.85); font-size: 21px; }
  /* Romanización y traducción: más chicas, debajo de la línea; se encienden con ella */
  .extra { display: block; font-size: 16px; font-weight: 600; line-height: 1.35; margin-top: 3px; }
  .rom { opacity: 0.85; }
  .trad { font-style: italic; font-weight: 500; opacity: 0.75; }
  .aviso { text-align: center; color: rgba(255, 255, 255, 0.6); font-size: 18px; }
  .fuente { margin-top: 24px; font-size: 12.5px; color: rgba(255, 255, 255, 0.4); }
</style>
