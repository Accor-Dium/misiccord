<script>
  import { flip } from "svelte/animate";
  import { canciones, t } from "../lib/idioma.svelte.js";
  import { alternarAleatorio, moverEnCola, quitarDeCola, rep, reproducirDeCola } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // "A continuación": hasta arriba la que suena y debajo lo que sigue en el orden real (también con aleatorio).
  // Arrastra la agarradera ≡ para cambiar el orden; desliza a la izquierda (o la ✕ con mouse) para quitar una canción.
  const PASO = 100; // una cola puede ser toda la biblioteca: se dibujan de a poco
  let limite = $state(PASO);
  let verAnteriores = $state(false);
  const actual = $derived(rep.cola[rep.indice]);
  const siguientes = $derived(rep.cola.slice(rep.indice + 1, rep.indice + 1 + limite));
  const anteriores = $derived(rep.cola.slice(0, Math.max(rep.indice, 0)));
  const quedan = $derived(Math.max(0, rep.cola.length - rep.indice - 1));

  // ---------- Reordenar ----------
  let arrastre = $state(null); // { desde, sobre, y0, dy, alto } (desde y sobre: posiciones dentro de `siguientes`)

  function agarrar(ev, k) {
    ev.preventDefault();
    ev.stopPropagation();
    ev.currentTarget.setPointerCapture(ev.pointerId);
    arrastre = { desde: k, sobre: k, y0: ev.clientY, dy: 0, alto: ev.currentTarget.closest(".item").offsetHeight };
  }
  function arrastrar(ev) {
    if (!arrastre) return;
    arrastre.dy = ev.clientY - arrastre.y0;
    arrastre.sobre = Math.max(0, Math.min(siguientes.length - 1, arrastre.desde + Math.round(arrastre.dy / arrastre.alto)));
  }
  function soltar() {
    if (!arrastre) return;
    const { desde, sobre } = arrastre;
    arrastre = null;
    if (sobre !== desde) moverEnCola(rep.indice + 1 + desde, rep.indice + 1 + sobre);
  }
  /** La fila que arrastras sigue al dedo y las demás le hacen espacio. */
  function corrimiento(k) {
    const a = arrastre;
    if (!a) return 0;
    if (k === a.desde) return a.dy;
    if (a.desde < a.sobre && k > a.desde && k <= a.sobre) return -a.alto;
    if (a.desde > a.sobre && k < a.desde && k >= a.sobre) return a.alto;
    return 0;
  }

  // ---------- Deslizar para quitar ----------
  const QUITAR = 90; // px hacia la izquierda
  let barrido = $state(null); // { item, x0, y0, dx, activo }
  let recienBarrida = false; // el clic que llega al soltar no debe poner la canción

  function empezarBarrido(ev, item) {
    if (ev.button) return;
    barrido = { item, x0: ev.clientX, y0: ev.clientY, dx: 0, activo: false };
  }
  function moverBarrido(ev) {
    const b = barrido;
    if (!b) return;
    const dx = ev.clientX - b.x0;
    if (!b.activo) {
      if (Math.abs(dx) < 12) return;
      if (Math.abs(ev.clientY - b.y0) > Math.abs(dx)) { barrido = null; return; } // está subiendo o bajando la lista
      b.activo = true;
      ev.currentTarget.setPointerCapture(ev.pointerId);
    }
    b.dx = Math.min(0, dx);
  }
  function soltarBarrido() {
    const b = barrido;
    barrido = null;
    if (!b?.activo) return;
    recienBarrida = true;
    setTimeout(() => (recienBarrida = false), 0);
    if (b.dx <= -QUITAR) quitarDeCola(rep.cola.indexOf(b.item));
  }
  function tocar(item) {
    if (!recienBarrida) reproducirDeCola(rep.cola.indexOf(item));
  }
</script>

<div class="cola">
  <div class="cabeza">
    <span class="tenue">{rep.origen || t("tu música")} · {canciones(quedan)}</span>
    <button class="chico" class:encendido={rep.aleatorio} onclick={alternarAleatorio}>
      <Icono nombre="aleatorio" tam={16} /> {t("Aleatorio")}
    </button>
  </div>

  {#if anteriores.length}
    <button class="anteriores" onclick={() => (verAnteriores = !verAnteriores)}>
      {verAnteriores ? t("Ocultar las anteriores") : t("Ver las anteriores ({n})", { n: anteriores.length })}
    </button>
    {#if verAnteriores}
      {#each anteriores as item (item)}
        <button class="item pasada" onclick={() => tocar(item)}>
          <Portada url={item.portada} tam="42px" radio="6px" />
          <span class="textos"><b class="cortar">{item.titulo}</b><small class="cortar">{item.artista}</small></span>
        </button>
      {/each}
    {/if}
  {/if}

  {#if actual}
    <div class="item sonando">
      <Portada url={actual.portada} tam="42px" radio="6px" />
      <span class="textos"><b class="cortar">{actual.titulo}</b><small class="cortar">{actual.artista}</small></span>
      <span class="ahora">{t("Sonando")}</span>
    </div>
  {/if}

  {#if siguientes.length}
    <h3>{t("Sigue")}</h3>
    {#each siguientes as item, k (item)}
      <div class="carril" animate:flip={{ duration: arrastre ? 0 : 180 }} class:levantada={arrastre?.desde === k}
        style:transform={corrimiento(k) ? `translateY(${corrimiento(k)}px)` : null}
        style:transition={arrastre && arrastre.desde !== k ? "transform 0.15s" : null}>
        {#if barrido?.item === item && barrido.activo}
          <span class="fondo-quitar" class:listo={barrido.dx <= -QUITAR}><Icono nombre="basura" tam={20} /></span>
        {/if}
        <div class="item" role="button" tabindex="0" onclick={() => tocar(item)} onkeydown={(e) => e.key === "Enter" && tocar(item)}
          onpointerdown={(e) => empezarBarrido(e, item)} onpointermove={moverBarrido} onpointerup={soltarBarrido} onpointercancel={() => (barrido = null)}
          style:transform={barrido?.item === item && barrido.activo ? `translateX(${barrido.dx}px)` : null}>
          <Portada url={item.portada} tam="42px" radio="6px" />
          <span class="textos"><b class="cortar">{item.titulo}</b><small class="cortar">{item.artista}</small></span>
          <button class="quitar" aria-label={t("Quitar de la cola")} onclick={(e) => { e.stopPropagation(); quitarDeCola(rep.cola.indexOf(item)); }}>
            <Icono nombre="cerrar" tam={16} />
          </button>
          <span class="agarrar" role="button" tabindex="-1" aria-label={t("Arrastrar para reordenar")}
            onclick={(e) => e.stopPropagation()} onkeydown={() => {}}
            onpointerdown={(e) => agarrar(e, k)} onpointermove={arrastrar} onpointerup={soltar} onpointercancel={() => (arrastre = null)}>
            <Icono nombre="arrastrar" tam={20} />
          </span>
        </div>
      </div>
    {/each}
    {#if quedan > limite}
      <button class="anteriores" onclick={() => (limite += PASO)}>{t("Ver más ({n})", { n: quedan - limite })}</button>
    {/if}
  {:else}
    <p class="tenue vacia">{t("Ya no sigue nada en la cola.")}</p>
  {/if}
</div>

<style>
  .cola { height: 100%; overflow-y: auto; overflow-x: hidden; scrollbar-width: none; touch-action: pan-y; }
  .cola::-webkit-scrollbar { display: none; }
  .cabeza { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; font-size: 13px; }
  .tenue { color: rgba(255, 255, 255, 0.6); }
  .chico { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px; border-radius: 999px; font-size: 13px; font-weight: 700; background: rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.75); flex-shrink: 0; }
  .chico.encendido { background: #fff; color: #04121a; }
  h3 { margin: 14px 0 6px; font-size: 13px; letter-spacing: 1.2px; text-transform: uppercase; color: rgba(255, 255, 255, 0.6); }
  .carril { position: relative; }
  .carril.levantada { z-index: 3; background: rgba(40, 55, 68, 0.97); border-radius: 10px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); }
  .item { position: relative; width: 100%; display: flex; align-items: center; gap: 12px; padding: 6px 4px; text-align: left; border-radius: 8px; background: transparent; cursor: pointer; }
  .item.sonando { background: rgba(255, 255, 255, 0.1); cursor: default; }
  .item.sonando b { color: var(--cian); }
  .item.pasada { opacity: 0.55; }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  small { color: rgba(255, 255, 255, 0.6); }
  .ahora { font-size: 11px; font-weight: 700; letter-spacing: 0.6px; color: var(--cian); flex-shrink: 0; margin-right: 6px; }
  .agarrar { width: 34px; height: 40px; display: grid; place-items: center; color: rgba(255, 255, 255, 0.55); cursor: grab; touch-action: none; flex-shrink: 0; }
  .levantada .agarrar { cursor: grabbing; color: var(--cian); }
  .quitar { display: none; width: 30px; height: 30px; place-items: center; color: rgba(255, 255, 255, 0.55); flex-shrink: 0; }
  @media (hover: hover) { .item:hover .quitar { display: grid; } }
  .fondo-quitar { position: absolute; inset: 0; display: flex; align-items: center; justify-content: flex-end; padding-right: 18px; border-radius: 8px; background: rgba(248, 113, 113, 0.25); color: #fff; }
  .fondo-quitar.listo { background: var(--rojo); }
  .anteriores { display: block; width: 100%; padding: 8px 0; font-size: 13px; font-weight: 600; color: rgba(255, 255, 255, 0.65); }
  .vacia { margin-top: 18px; text-align: center; font-size: 14px; }
</style>
