<script>
  import { fly } from "svelte/transition";
  import { flip } from "svelte/animate";
  import { quitarAviso, ui } from "../lib/estado.svelte.js";
  import { jam } from "../lib/jam.svelte.js";
  import { rep } from "../lib/reproductor.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import Icono from "./Icono.svelte";

  // Avisos flotantes abajo, encima del mini reproductor (ahí el pulgar los alcanza y no tapan los títulos).
  // Tocarlos los cierra; si traen acción ("Abrir", "Deshacer"…) tienen su botón.
  const iconos = { ok: "check", error: "alerta", info: "info" };
</script>

<div class="avisos" class:con-mini={rep.actual || jam.sala} role="status" aria-live="polite">
  {#each ui.avisos as a (a.id)}
    <div class="aviso {a.tipo}" in:fly={{ y: 24, duration: 260 }} out:fly={{ y: 12, duration: 180 }} animate:flip={{ duration: 200 }}>
      <button class="cuerpo" onclick={() => quitarAviso(a.id)} aria-label={t("Cerrar aviso")}>
        <span class="icono"><Icono nombre={iconos[a.tipo] ?? "info"} tam={16} /></span>
        <span class="texto">{a.texto}</span>
      </button>
      {#if a.accion}
        <button class="accion" onclick={() => { quitarAviso(a.id); a.accion.f(); }}>{a.accion.texto}</button>
      {/if}
      {#if a.avance !== null}<span class="avance" style:width="{Math.round(a.avance * 100)}%"></span>{/if}
    </div>
  {/each}
</div>

<style>
  .avisos {
    position: fixed; z-index: 80; left: 12px; right: 12px;
    bottom: calc(var(--nav) + var(--seguro-abajo) + 10px);
    display: flex; flex-direction: column-reverse; align-items: center; gap: 8px; pointer-events: none;
  }
  .avisos.con-mini { bottom: calc(var(--nav) + var(--mini) + var(--seguro-abajo) + 14px); }
  .aviso {
    position: relative; overflow: hidden; pointer-events: auto;
    display: flex; align-items: center; gap: 4px; width: fit-content; max-width: min(520px, 100%);
    background: rgba(240, 246, 250, 0.97); color: #0a141c; border-radius: 16px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45), 0 1px 0 rgba(255, 255, 255, 0.4) inset;
  }
  .cuerpo { display: flex; align-items: center; gap: 10px; padding: 11px 14px 11px 11px; text-align: left; min-width: 0; color: inherit; }
  .icono { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; flex-shrink: 0; background: #0a141c; color: var(--cian); }
  .ok .icono { color: var(--verde); }
  .error .icono { background: #b91c1c; color: #fff; }
  .texto { font-size: 14.5px; font-weight: 600; line-height: 1.3; overflow-wrap: anywhere; }
  .accion { padding: 0 14px 0 6px; height: 40px; font-weight: 800; font-size: 14px; color: #0e7490; flex-shrink: 0; }
  .avance { position: absolute; left: 0; bottom: 0; height: 3px; background: var(--cian); transition: width 0.3s; }
  @media (min-width: 900px) {
    .avisos, .avisos.con-mini { left: calc(var(--lateral) + 24px); right: 24px; bottom: calc(var(--mini) + 28px); }
  }
</style>
