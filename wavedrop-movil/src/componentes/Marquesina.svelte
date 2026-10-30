<script>
  // Texto de una línea: si no cabe, en vez de cortarse con "…" se desliza de un lado a otro.
  let { children } = $props();
  let caja = $state();
  let texto = $state();
  let sobra = $state(0); // px que no caben

  function medir() {
    sobra = Math.max(0, texto.offsetWidth - caja.clientWidth);
  }
  $effect(() => {
    const vigia = new ResizeObserver(medir);
    vigia.observe(caja);
    vigia.observe(texto);
    return () => vigia.disconnect();
  });
</script>

<div class="marquesina" class:mueve={sobra > 0} bind:this={caja}>
  <div class="texto" bind:this={texto} style:--sobra="-{sobra}px" style:--duracion="{Math.max(6, sobra / 22 + 4)}s">{@render children()}</div>
</div>

<style>
  .marquesina { overflow: hidden; min-width: 0; }
  .texto { display: inline-block; white-space: nowrap; }
  .mueve { mask-image: linear-gradient(to right, #000 calc(100% - 18px), transparent); }
  .mueve .texto { animation: deslizar var(--duracion) ease-in-out infinite alternate; }
  /* Se queda un momento quieto en cada extremo para poder leerlo */
  @keyframes deslizar {
    0%, 18% { transform: translateX(0); }
    82%, 100% { transform: translateX(var(--sobra)); }
  }
  @media (prefers-reduced-motion: reduce) { .mueve .texto { animation: none; } }
</style>
