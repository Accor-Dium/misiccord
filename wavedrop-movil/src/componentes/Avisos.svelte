<script>
  import { fly } from "svelte/transition";
  import { ui } from "../lib/estado.svelte.js";
</script>

<div class="avisos">
  {#each ui.avisos as a (a.id)}
    <div class="aviso {a.tipo}" transition:fly={{ y: -20, duration: 250 }}>{a.texto}</div>
  {/each}
</div>

<style>
  .avisos {
    position: fixed; top: calc(var(--seguro-arriba) + 10px); left: 12px; right: 12px; z-index: 80;
    display: flex; flex-direction: column; gap: 8px; pointer-events: none;
  }
  .aviso {
    background: rgba(28, 42, 53, 0.96); backdrop-filter: blur(16px); border-radius: 14px;
    padding: 12px 16px; font-weight: 600; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    border-left: 3px solid var(--cian);
  }
  @media (min-width: 900px) {
    .avisos { top: auto; bottom: 120px; left: auto; right: 24px; width: 380px; }
  }
  .ok { border-left-color: var(--verde); }
  .error { border-left-color: var(--rojo); }
</style>
