<script>
  import { src } from "../lib/api.js";
  import { ui } from "../lib/estado.svelte.js";
  import Icono from "./Icono.svelte";

  // Portada con aparición suave y un icono si no hay imagen.
  // objeto: en lo que se ve grande se dibuja como estuche de CD o vinilo si así está en Ajustes (en listas estorbaría).
  // giro (true/false): en vinilo se ve el disco entero, girando mientras sea true, en vez de la funda.
  let { url = null, tam = "100%", radio = "10px", redonda = false, icono = "nota", sombra = false, objeto = false, giro = undefined } = $props();
  let cargada = $state(false);
  let fallo = $state(false);
  let intentos = $state(0);
  const imagen = $derived(src(url));
  const estilo = $derived(objeto && !redonda ? ui.caratulas : "normal");
  const disco = $derived(estilo === "vinilo" && giro !== undefined);
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
  .cd, .vinilo { container-type: inline-size; }

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
  .entero .surcos::after {
    content: ""; position: absolute; left: 50%; top: 50%; z-index: 2; width: 3.4cqw; height: 3.4cqw; margin: -1.7cqw;
    border-radius: 50%; background: #0b0b0d; box-shadow: 0 0 0 0.4cqw rgba(255, 255, 255, 0.28);
  }
  .entero .arte { inset: 21%; width: auto; height: auto; border-radius: 50%; box-shadow: 0 0 0 0.5cqw #0b0b0d; }
  .entero .arte::after { content: none; }
  @keyframes girar { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .entero .surcos { animation: none; } }
</style>
