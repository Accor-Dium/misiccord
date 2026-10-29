<script>
  // Páginas que se pasan de lado (con imán) y puntitos abajo, como la "marcación rápida" de Inicio.
  let { paginas, pagina } = $props();
  let caja = $state();
  let actual = $state(0);

  function alDesplazar() {
    actual = Math.round(caja.scrollLeft / caja.clientWidth);
  }
  function ir(i) {
    caja.scrollTo({ left: i * caja.clientWidth, behavior: "smooth" });
  }
</script>

<div class="paginas" bind:this={caja} onscroll={alDesplazar}>
  {#each paginas as grupo, p}
    <div class="pagina">{@render pagina(grupo, p)}</div>
  {/each}
</div>
{#if paginas.length > 1}
  <div class="puntos">
    {#each paginas as _, i}
      <button class:activo={i === actual} onclick={() => ir(i)} aria-label="{i + 1}"></button>
    {/each}
  </div>
{/if}

<style>
  .paginas {
    display: flex; overflow-x: auto; scroll-snap-type: x mandatory; overscroll-behavior-x: contain; scrollbar-width: none;
    margin: 0 calc(-1 * var(--margen));
  }
  .paginas::-webkit-scrollbar { display: none; }
  .pagina { flex: 0 0 100%; scroll-snap-align: start; padding: 0 var(--margen); min-width: 0; }
  .puntos { display: flex; justify-content: center; gap: 7px; margin-top: 12px; }
  .puntos button { width: 8px; height: 8px; border-radius: 50%; background: var(--borde-fuerte); transition: background 0.2s, transform 0.2s; }
  .puntos button.activo { background: var(--texto); transform: scale(1.15); }
</style>
