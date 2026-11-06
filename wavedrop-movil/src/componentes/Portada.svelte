<script>
  import { src, tiempo } from "../lib/api.js";
  import { colorDe } from "../lib/colorPortada.svelte.js";
  import { ui } from "../lib/estado.svelte.js";
  import Icono from "./Icono.svelte";

  // Portada con aparición suave y un icono si no hay imagen.
  // objeto: en lo que se ve grande se dibuja como estuche de CD o vinilo si así está en Ajustes (en listas estorbaría).
  // giro (true/false): en vinilo se ve el disco entero, girando mientras sea true, en vez de la funda; en cassette giran los carretes.
  // etiqueta ({ titulo, artista, anio, pistas: [{ titulo, duracion }] }): lo que se imprime en la etiqueta del cassette cuando se ve grande.
  let { url = null, tam = "100%", radio = "10px", redonda = false, icono = "nota", sombra = false, objeto = false, giro = undefined, etiqueta = null } = $props();
  let cargada = $state(false);
  let fallo = $state(false);
  let intentos = $state(0);
  const imagen = $derived(src(url));
  const estilo = $derived(objeto && !redonda ? ui.caratulas : "normal");
  const disco = $derived(estilo === "vinilo" && giro !== undefined);
  const color = $derived(estilo === "cassette" ? colorDe(imagen) : null);
  $effect(() => {
    imagen;
    cargada = false;
    fallo = false;
    intentos = 0;
  });
  // Cuando se piden muchas portadas juntas (Inicio, una rejilla) YouTube rechaza algunas un momento:
  // se reintenta dos veces antes de dejar el icono.
  function alFallar() {
    fallo = true;
    if (intentos < 2) setTimeout(() => { intentos++; fallo = false; }, 1500 * (intentos + 1));
  }
</script>

{#snippet arte()}
  <div class="arte">
    {#if imagen && !fallo}
      {#key intentos}
        <img src={imagen} alt="" loading="lazy" class:cargada onload={() => (cargada = true)} onerror={alFallar} />
      {/key}
    {/if}
    {#if !imagen || fallo || !cargada}
      <div class="sin"><Icono nombre={icono} tam={28} /></div>
    {/if}
  </div>
{/snippet}

<div
  class="portada"
  class:sombra={sombra && estilo === "normal"}
  class:cd={estilo === "cd"}
  class:vinilo={estilo === "vinilo"}
  class:cassette={estilo === "cassette"}
  class:sinarte={!imagen || (fallo && intentos >= 2)}
  class:entero={disco}
  style:width={tam}
  style:border-radius={estilo !== "normal" ? null : redonda ? "50%" : radio}
>
  {#if estilo === "vinilo"}
    <div class="disco">
      <div class="surcos" class:gira={giro}>{#if disco}{@render arte()}{/if}</div>
    </div>
  {/if}
  {#if !disco}{@render arte()}{/if}
  {#if estilo === "cd"}<span class="bisagra"></span><span class="plastico"></span>{/if}
  {#if estilo === "cassette"}
    <!-- Como los cassettes japoneses: arriba las canciones, abajo artista y álbum, a la izquierda la portada y a la derecha el lado -->
    <div class="etiqueta" style:--fondo={color.fondo} style:--tinta={color.tinta}>
      {#if etiqueta?.pistas?.length}
        <ol class="pistas">{#each etiqueta.pistas.slice(0, 8) as pista, i}<li><small>{i + 1}</small><b class="cortar">{pista.titulo}</b>{#if pista.duracion}<span>{tiempo(pista.duracion)}</span>{/if}</li>{/each}</ol>
      {/if}
      <span class="lado"><b>A</b>{#if etiqueta?.anio}<small>{etiqueta.anio}</small>{/if}</span>
      {#if etiqueta}
        <span class="nombres"><b class="cortar">{etiqueta.artista}</b><small class="cortar">{etiqueta.titulo}</small></span>
      {/if}
    </div>
    <span class="ventana"><i class:gira={giro}></i><i class:gira={giro}></i></span>
    <span class="tornillos"></span>
  {/if}
</div>

<style>
  .portada { position: relative; aspect-ratio: 1; flex-shrink: 0; color: var(--tenue); }
  .sombra { box-shadow: 0 18px 50px rgba(0, 0, 0, 0.55); }
  .arte { position: absolute; inset: 0; overflow: hidden; border-radius: inherit; background: var(--tarjeta-2); }
  img {
    position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
    opacity: 0; transition: opacity 0.35s var(--curva); z-index: 1;
  }
  img.cargada { opacity: 1; }
  .sin { position: absolute; inset: 0; display: grid; place-items: center; }

  /* Todo va en cqw (1 % del ancho) para que se vea igual en una tarjeta que en el reproductor.
     El cuadro sigue siendo cuadrado: las rejillas calculan su alto contando con eso. */
  .cd, .vinilo, .cassette { container-type: inline-size; }

  /* Estuche de CD: el real es más ancho que alto, por eso sobra un poco arriba y abajo */
  .cd::before, .bisagra, .plastico { content: ""; position: absolute; left: 0; top: 6%; bottom: 6%; }
  .cd::before {
    right: 0; border-radius: 1.4cqw; background: linear-gradient(90deg, #1b1c21, #0b0c0f);
    box-shadow: 0 3cqw 8cqw rgba(0, 0, 0, 0.55);
  }
  .cd .arte { inset: auto; left: 13.75cqw; top: 7.75cqw; width: 84.5cqw; height: 84.5cqw; border-radius: 0.4cqw; }
  .bisagra {
    width: 12.5cqw; border-radius: 1.4cqw 0 0 1.4cqw;
    background:
      linear-gradient(90deg, rgba(255, 255, 255, 0.2) 0 0.5cqw, rgba(255, 255, 255, 0.03) 1.2cqw 3.8cqw,
        rgba(255, 255, 255, 0.16) 4.1cqw 4.5cqw, rgba(0, 0, 0, 0.25) 5cqw 11.5cqw, rgba(255, 255, 255, 0.14) 12.5cqw);
  }
  .plastico {
    right: 0; z-index: 3; border-radius: 1.4cqw; pointer-events: none;
    box-shadow: inset 0 0 0 max(1px, 0.3cqw) rgba(255, 255, 255, 0.2), inset 0 0 3cqw rgba(0, 0, 0, 0.3);
    background:
      /* Rayones del plástico */
      linear-gradient(68deg, transparent 49.2%, rgba(255, 255, 255, 0.2) 49.8%, transparent 50.4%) 80% 12% / 30% 24% no-repeat,
      linear-gradient(143deg, transparent 49.2%, rgba(255, 255, 255, 0.14) 49.8%, transparent 50.4%) 94% 84% / 26% 30% no-repeat,
      linear-gradient(31deg, transparent 49%, rgba(255, 255, 255, 0.1) 49.8%, transparent 50.6%) 34% 72% / 22% 14% no-repeat,
      /* Reflejos: franjas con un borde duro, como la luz en una superficie plana */
      linear-gradient(112deg, rgba(255, 255, 255, 0.24), rgba(255, 255, 255, 0.07) 19%, transparent 19.4%,
        transparent 36%, rgba(255, 255, 255, 0.09) 36.4%, rgba(255, 255, 255, 0.02) 47%, transparent 47.4%);
  }

  /* Vinilo: la funda con el disco asomando a la derecha */
  .vinilo .arte {
    inset: auto; left: 0; top: 8cqw; z-index: 2; width: 84cqw; height: 84cqw; border-radius: 0.6cqw;
    box-shadow: 1.2cqw 0 3cqw rgba(0, 0, 0, 0.55);
  }
  /* Huella del disco en la funda, luz en el lomo y sombra en la boca */
  .vinilo .arte::after {
    content: ""; position: absolute; inset: 0; z-index: 2; pointer-events: none;
    background:
      radial-gradient(circle, transparent 66%, rgba(255, 255, 255, 0.1) 67.5%, transparent 69.5%),
      linear-gradient(90deg, rgba(255, 255, 255, 0.14), transparent 3%, transparent 95%, rgba(0, 0, 0, 0.4)),
      linear-gradient(125deg, rgba(255, 255, 255, 0.1), transparent 42%);
  }
  .disco {
    position: absolute; right: 1cqw; top: 11cqw; width: 78cqw; height: 78cqw; border-radius: 50%;
    box-shadow: 0 2cqw 6cqw rgba(0, 0, 0, 0.55);
  }
  /* El brillo va fijo sobre el disco: lo que gira son los surcos y la etiqueta, no la luz */
  .disco::after {
    content: ""; position: absolute; inset: 0; z-index: 2; border-radius: 50%; pointer-events: none;
    box-shadow: inset 0 0 0 max(1px, 0.25cqw) rgba(255, 255, 255, 0.12);
    background: conic-gradient(from 25deg, rgba(255, 255, 255, 0.16), transparent 12%, rgba(255, 255, 255, 0.05) 25%, transparent 38%,
      rgba(255, 255, 255, 0.16) 50%, transparent 62%, rgba(255, 255, 255, 0.05) 75%, transparent 88%, rgba(255, 255, 255, 0.16));
  }
  .surcos {
    position: absolute; inset: 0; border-radius: 50%;
    background: repeating-radial-gradient(circle, #101012 0 0.45cqw, #1c1c20 0.45cqw 0.7cqw);
  }

  /* Disco entero (reproductor): la carátula es la etiqueta */
  .entero .disco { inset: 0; width: 100%; height: 100%; }
  .entero .surcos { animation: girar 7s linear infinite paused; }
  .entero .surcos.gira { animation-play-state: running; }
  .entero .arte { inset: 21%; width: auto; height: auto; border-radius: 50%; box-shadow: 0 0 0 0.5cqw #0b0b0d; }
  .entero .arte::after { content: none; }
  @keyframes girar { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .entero .surcos, .ventana i { animation: none; } }

  /* Cassette: el real mide 100 × 64 mm, por eso sobra arriba y abajo. La carátula es la etiqueta y por eso se recorta a lo ancho */
  .cassette::before {
    content: ""; position: absolute; left: 0; right: 0; top: 18cqw; height: 64cqw; border-radius: 2.4cqw;
    background: linear-gradient(170deg, #34363d, #1a1b20 45%, #111216);
    box-shadow: 0 3cqw 8cqw rgba(0, 0, 0, 0.55), inset 0 0 0 max(1px, 0.3cqw) rgba(255, 255, 255, 0.14), inset 0 0.7cqw 0.9cqw rgba(255, 255, 255, 0.1);
  }
  .cassette .arte {
    inset: auto; left: 6.5cqw; top: 22cqw; width: 87cqw; height: 42.5cqw; border-radius: 1.4cqw;
    box-shadow: 0 0.4cqw 1cqw rgba(0, 0, 0, 0.45);
  }
  .etiqueta { display: none; }
  /* Grande (álbum, reproductor): la etiqueta impresa. En una tarjeta chica las letras no se leerían: ahí la portada es la etiqueta */
  @container (min-width: 220px) {
    .etiqueta {
      display: block; position: absolute; z-index: 1; left: 6.5cqw; top: 22cqw; width: 87cqw; height: 42.5cqw; border-radius: 1.4cqw;
      background: var(--fondo); color: var(--tinta); overflow: hidden;
      box-shadow: 0 0.4cqw 1cqw rgba(0, 0, 0, 0.45);
    }
    /* Pegada a la esquina de la etiqueta y debajo de la ventana: el carrete le tapa la esquina de abajo a la derecha */
    .cassette .arte { z-index: 2; left: 6.5cqw; top: 22cqw; width: 25cqw; height: 25cqw; border-radius: 1.4cqw 0 0 0; box-shadow: none; }
    .pistas {
      /* Empieza donde acaba la portada (25) y un respiro */
      position: absolute; left: 27.5cqw; right: 3cqw; top: 1.4cqw; height: 10.4cqw; margin: 0; padding: 0; list-style: none; overflow: hidden;
      columns: 2; column-gap: 2.5cqw; font-size: 2.1cqw; line-height: 2.4cqw; text-align: left;
    }
    .pistas li { break-inside: avoid; display: flex; align-items: baseline; gap: 0.7cqw; }
    /* Sin portada (ni la habrá: no hay url o ya falló los reintentos) no se deja el hueco */
    .sinarte .arte { display: none; }
    .sinarte .pistas { left: 3cqw; }
    .pistas small { flex-shrink: 0; min-width: 1.4cqw; font-size: 1.5cqw; font-weight: 600; opacity: 0.75; }
    .pistas b { flex: 1; min-width: 0; font-weight: 800; }
    .pistas span { flex-shrink: 0; font-size: 1.7cqw; font-weight: 600; font-variant-numeric: tabular-nums; opacity: 0.75; }
    .lado { position: absolute; right: 3.5cqw; top: 12.5cqw; width: 14cqw; height: 15cqw; display: grid; place-content: center; text-align: center; line-height: 1; }
    .lado b { font-size: 8cqw; font-weight: 900; }
    .lado small { margin-top: 0.6cqw; font-size: 2.2cqw; font-weight: 700; letter-spacing: 0.2cqw; opacity: 0.8; }
    .nombres {
      position: absolute; left: 3cqw; right: 3cqw; bottom: 1.4cqw; display: flex; flex-direction: column; align-items: center; gap: 0.2cqw; text-align: center;
      padding-top: 1cqw; border-top: max(1px, 0.25cqw) solid currentColor; line-height: 1.2;
    }
    .nombres b { max-width: 100%; font-size: 3.6cqw; font-weight: 900; letter-spacing: 0.25cqw; text-transform: uppercase; }
    .nombres small { max-width: 100%; font-size: 2.8cqw; font-weight: 600; opacity: 0.85; }
  }
  .ventana {
    position: absolute; z-index: 3; left: 25cqw; top: 35.5cqw; width: 50cqw; height: 15cqw; border-radius: 7.5cqw;
    display: flex; justify-content: space-between; align-items: center; padding: 0 3cqw; box-sizing: border-box;
    box-shadow: 0 0 0 0.9cqw rgba(232, 226, 212, 0.95), inset 0 0.8cqw 1.4cqw rgba(0, 0, 0, 0.75);
    background:
      /* La cinta enrollada en cada carrete, vista por la ventana */
      radial-gradient(circle at 9cqw 50%, #3c2a20 0 10cqw, transparent 10.1cqw),
      radial-gradient(circle at 41cqw 50%, #3c2a20 0 7cqw, transparent 7.1cqw),
      linear-gradient(180deg, #0b0c0f, #17181d);
    overflow: hidden;
  }
  /* El cubo de cada carrete, con sus seis dientes */
  .ventana i {
    position: relative; width: 9cqw; height: 9cqw; border-radius: 50%; animation: girar 3s linear infinite paused;
    background:
      radial-gradient(circle, #0c0d10 0 2.1cqw, transparent 2.2cqw),
      repeating-conic-gradient(#f2eee4 0 22deg, transparent 22deg 60deg),
      radial-gradient(circle, transparent 0 3.1cqw, #f2eee4 3.2cqw);
  }
  .ventana i.gira { animation-play-state: running; }
  /* Abajo: los tornillos de las esquinas y la pieza por donde sale la cinta, con sus agujeros */
  .tornillos { position: absolute; z-index: 3; left: 0; right: 0; top: 18cqw; height: 64cqw; border-radius: 2.4cqw; pointer-events: none;
    background:
      radial-gradient(circle at 3cqw 3cqw, #8d8f96 0 0.9cqw, transparent 1cqw),
      radial-gradient(circle at 97cqw 3cqw, #8d8f96 0 0.9cqw, transparent 1cqw),
      radial-gradient(circle at 3cqw 61cqw, #8d8f96 0 0.9cqw, transparent 1cqw),
      radial-gradient(circle at 97cqw 61cqw, #8d8f96 0 0.9cqw, transparent 1cqw),
      radial-gradient(circle at 34cqw 57.5cqw, #08090b 0 1.5cqw, transparent 1.6cqw),
      radial-gradient(circle at 66cqw 57.5cqw, #08090b 0 1.5cqw, transparent 1.6cqw),
      radial-gradient(circle at 44cqw 57.5cqw, #08090b 0 1cqw, transparent 1.1cqw),
      radial-gradient(circle at 56cqw 57.5cqw, #08090b 0 1cqw, transparent 1.1cqw);
  }
  .tornillos::before {
    content: ""; position: absolute; z-index: -1; left: 18cqw; right: 18cqw; bottom: 0; height: 13cqw;
    clip-path: polygon(6% 0, 94% 0, 100% 100%, 0 100%);
    background: linear-gradient(180deg, #2f3137, #202126);
  }
</style>
