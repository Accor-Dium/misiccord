<script>
  import { src } from "../lib/api.js";
  import { ui } from "../lib/estado.svelte.js";

  // Lomo de un álbum, como si estuvieran apilados: el del CD es de plástico, el del vinilo de cartón y delgado, y el del cassette de papel dentro de su cajita.
  // El color sale de una franja de la carátula: cada álbum se distingue sin tener que calcular nada.
  let { portada, titulo, artista, alTocar } = $props();
  const imagen = $derived(src(portada));
</script>

<button class="costilla" class:vinilo={ui.caratulas === "vinilo"} class:cassette={ui.caratulas === "cassette"} onclick={alTocar}>
  {#if imagen}<img src={imagen} alt="" loading="lazy" />{/if}
  <b class="cortar">{titulo}</b>
  <small class="cortar">{artista}</small>
</button>

<style>
  /* El hueco entre lomos es un borde y no un margen: ListaVirtual mide el alto de cada fila sin márgenes */
  .costilla {
    position: relative; width: 100%; height: 50px; display: flex; align-items: center; gap: 16px; padding: 0 22px 0 30px;
    overflow: hidden; border-bottom: 2px solid transparent; background: var(--tarjeta-2) padding-box; text-align: left; color: #fff;
    transition: transform 0.18s var(--curva);
  }
  img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .costilla::after {
    content: ""; position: absolute; inset: 0;
    background:
      /* Bisagras del estuche en las puntas */
      linear-gradient(90deg, #2a2c33 0 8px, rgba(255, 255, 255, 0.34) 9px, #1b1c22 10px 15px, rgba(255, 255, 255, 0.18) 16px, transparent 17px) left / 17px 100% no-repeat,
      linear-gradient(270deg, #2a2c33 0 6px, rgba(255, 255, 255, 0.28) 7px, transparent 8px) right / 8px 100% no-repeat,
      /* Luz en el canto del plástico */
      linear-gradient(180deg, rgba(255, 255, 255, 0.26), rgba(255, 255, 255, 0.05) 26%, rgba(0, 0, 0, 0.06) 62%, rgba(0, 0, 0, 0.42)),
      /* Para que el texto se lea sobre cualquier carátula */
      linear-gradient(90deg, rgba(0, 0, 0, 0.66), rgba(0, 0, 0, 0.42));
  }
  b, small { position: relative; z-index: 1; min-width: 0; text-shadow: 0 1px 2px rgba(0, 0, 0, 0.8); }
  b { font-size: 14.5px; font-weight: 700; }
  small { margin-left: auto; flex-shrink: 0; max-width: 42%; font-size: 12.5px; opacity: 0.86; }

  /* Vinilo: cartón mate, sin bisagras */
  .vinilo { height: 34px; padding: 0 16px; }
  .vinilo::after {
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.14), transparent 22%, transparent 74%, rgba(0, 0, 0, 0.4)),
      linear-gradient(90deg, rgba(0, 0, 0, 0.62), rgba(0, 0, 0, 0.5));
  }
  .vinilo b { font-size: 13px; }
  .vinilo small { font-size: 11.5px; }

  /* Cassette: el papel de la portada por el canto de la cajita, con plástico arriba y abajo */
  .cassette { height: 42px; padding: 0 18px; }
  .cassette::after {
    background:
      linear-gradient(180deg, #24262c 0 3px, rgba(255, 255, 255, 0.3) 4px, transparent 5px, transparent calc(100% - 5px), rgba(255, 255, 255, 0.16) calc(100% - 4px), #17181d calc(100% - 3px)),
      linear-gradient(90deg, rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.44));
  }
  .cassette b { font-size: 13.5px; }
  .cassette small { font-size: 12px; }

  /* Al pasar el mouse se asoma, como sacándolo de la pila */
  @media (hover: hover) { .costilla:hover { transform: translateX(8px); } }
  .costilla:active { transform: translateX(8px); }
</style>
