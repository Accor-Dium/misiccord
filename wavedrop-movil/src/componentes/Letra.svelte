<script>
  import { py } from "../lib/api.js";
  import { irA, rep } from "../lib/reproductor.svelte.js";

  // Letra sincronizada: resalta la línea actual y se desplaza sola; toca una línea para saltar ahí.
  let estado = $state("cargando");
  let lineas = $state([]);
  let sincronizada = $state(false);
  let contenedor = $state();
  let clave = "";

  $effect(() => {
    const c = rep.actual;
    const ruta = c?.ruta || c?.ruta_previa;
    const k = ruta + "|" + c?.titulo;
    if (!ruta || k === clave) return;
    clave = k;
    estado = "cargando";
    py("letra", { ruta, titulo: c.titulo, artista: c.artista, album: c.album || "" })
      .then((r) => {
        lineas = r.lineas;
        sincronizada = r.tipo === "sincronizada";
        estado = r.lineas.length ? "lista" : r.tipo;
      })
      .catch(() => (estado = "error"));
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
    contenedor.querySelector(`[data-i="${actual}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
</script>

<div class="letra" bind:this={contenedor}>
  {#if estado === "cargando"}
    <p class="aviso">Buscando letra…</p>
  {:else if estado === "instrumental"}
    <p class="aviso">♪ Canción instrumental</p>
  {:else if estado === "lista"}
    {#each lineas as [ms, texto], i}
      <button
        data-i={i}
        class="linea"
        class:actual={i === actual}
        class:pasada={sincronizada && i < actual}
        class:libre={!sincronizada}
        onclick={() => sincronizada && irA(ms / 1000)}
      >{texto || "♪"}</button>
    {/each}
  {:else}
    <p class="aviso">No encontré la letra de esta canción.</p>
  {/if}
</div>

<style>
  .letra {
    height: 100%; overflow-y: auto; padding: 30vh 4px 40vh; scrollbar-width: none;
    mask-image: linear-gradient(transparent, #000 14%, #000 80%, transparent);
  }
  .letra::-webkit-scrollbar { display: none; }
  .linea {
    display: block; width: 100%; text-align: left; font-size: 25px; font-weight: 800; line-height: 1.3;
    padding: 8px 0; color: rgba(255, 255, 255, 0.38); transition: color 0.4s, transform 0.4s var(--curva);
    transform-origin: left center;
  }
  .linea.pasada { color: rgba(255, 255, 255, 0.22); }
  .linea.actual { color: #fff; transform: scale(1.03); }
  .linea.libre { color: rgba(255, 255, 255, 0.85); font-size: 21px; }
  .aviso { text-align: center; color: rgba(255, 255, 255, 0.6); font-size: 18px; }
</style>
