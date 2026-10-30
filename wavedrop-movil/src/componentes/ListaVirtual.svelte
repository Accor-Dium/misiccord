<script module>
  // Por tipo de fila y compartidas: una lista que aún no se ve (hay una por letra) debe ocupar ya su lugar real,
  // o la página brincaría al llegar a ella y los saltos del índice caerían donde no es
  const medidas = $state({}); // tipo → { alto, columnas, ancho }
</script>

<script>
  import { onMount, untrack } from "svelte";

  // Solo existen en el DOM las filas cerca de la pantalla: armar miles de golpe tardaba segundos en el cel.
  // Las filas de un `tipo` deben medir lo mismo. Con `clase` la caja puede ser una rejilla CSS (global: es otro componente).
  let { items, clave, tipo, clase = "", fila } = $props();

  const RESERVA = 1000; // px dibujados de más arriba y abajo: al deslizar rápido no se alcanza a ver vacío

  let caja = $state();
  // Renglones dibujados: de `primera` a `ultima` sin incluirla
  let primera = $state(0);
  let ultima = $state(0);
  const medida = $derived(medidas[tipo] ?? { alto: 64, columnas: 1 });
  const renglones = $derived(Math.ceil(items.length / medida.columnas));
  const visibles = $derived(items.slice(primera * medida.columnas, ultima * medida.columnas));

  function ubicar() {
    const arriba = caja.getBoundingClientRect().top;
    primera = Math.min(Math.max(Math.floor((-arriba - RESERVA) / medida.alto), 0), renglones);
    ultima = Math.min(Math.max(Math.ceil((innerHeight - arriba + RESERVA) / medida.alto), primera), renglones);
  }

  // Se mide una vez por ancho, no con cada fila que entra: los textos en otros alfabetos usan otra fuente y cambian el alto
  // 1 o 2 px, y dos listas midiendo distinto se corregirían entre sí sin fin
  function ajustar() {
    const ancho = caja.clientWidth;
    if (caja.firstElementChild && medidas[tipo]?.ancho !== ancho) {
      const estilo = getComputedStyle(caja);
      medidas[tipo] = {
        ancho,
        columnas: estilo.display === "grid" ? estilo.gridTemplateColumns.split(" ").length : 1,
        // La más alta: una tarjeta sin subtítulo no debe definir el alto de toda la lista
        alto: Math.max(...[...caja.children].map((x) => x.offsetHeight)) + (parseFloat(estilo.rowGap) || 0),
      };
    }
    ubicar();
  }

  $effect(() => {
    items;
    tipo;
    visibles;
    untrack(ajustar);
  });

  // Escucha el desplazamiento solo mientras está cerca de la pantalla: ordenadas por álbum son cientos de listas
  onMount(() => {
    const principal = caja.closest("main");
    let escuchando = false;
    function escuchar(si) {
      if (si === escuchando) return;
      escuchando = si;
      const accion = si ? "addEventListener" : "removeEventListener";
      principal[accion]("scroll", ubicar, { passive: true });
      window[accion]("resize", ajustar);
    }
    const vigia = new IntersectionObserver((vistas) => {
      escuchar(vistas.at(-1).isIntersecting);
      ubicar();
    }, { root: principal, rootMargin: `${RESERVA}px 0px` });
    vigia.observe(caja);
    return () => {
      vigia.disconnect();
      escuchar(false);
    };
  });
</script>

<div bind:this={caja} class="caja {clase}" style:height="{renglones * medida.alto}px" style:padding-top="{primera * medida.alto}px">
  {#each visibles as item (clave(item))}
    {@render fila(item)}
  {/each}
</div>

<style>
  /* Las filas entran y salen arriba de lo que ves: que el navegador no intente "corregir" el desplazamiento */
  .caja { overflow-anchor: none; align-content: start; }
</style>
