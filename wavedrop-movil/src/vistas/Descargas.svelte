<script>
  import { t } from "../lib/idioma.svelte.js";
  import { onMount } from "svelte";
  import { fade, slide } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { aviso, descargarLink, descargas } from "../lib/estado.svelte.js";
  import { reproducir } from "../lib/reproductor.svelte.js";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";

  let link = $state("");
  let leyendo = $state(false);
  const lista = $derived(Object.values(descargas.trabajos).sort((a, b) => b.creado - a.creado));
  const textos = {
    cola: t("En cola"), buscando: t("Buscando…"), descargando: t("Descargando"), etiquetando: t("Completando datos"),
    listo: t("Listo"), existe: t("Ya la tienes"), error: t("Error"), cancelado: t("Cancelada"),
  };

  onMount(async () => {
    const r = await py("descargas");
    for (const x of r.trabajos) descargas.trabajos[x.id] = x;
  });

  async function bajarLink() {
    if (!link.trim()) return;
    leyendo = true;
    try {
      await descargarLink(link.trim());
      link = "";
    } catch {
      aviso(t("No pude leer ese link"), "error");
    } finally {
      leyendo = false;
    }
  }

  async function limpiar() {
    await py("limpiar_descargas");
    for (const [id, t] of Object.entries(descargas.trabajos)) {
      if (["listo", "existe", "error", "cancelado"].includes(t.estado)) delete descargas.trabajos[id];
    }
  }
</script>

<div class="vista">
  <header>
    <h1 class="titulo-vista">{t("Descargas")}</h1>
    {#if lista.some((x) => ["listo", "existe", "error", "cancelado"].includes(x.estado))}
      <button class="limpiar" onclick={limpiar}>{t("Limpiar")}</button>
    {/if}
  </header>

  <form class="caja" onsubmit={(ev) => { ev.preventDefault(); bajarLink(); }}>
    <Icono nombre="link" tam={20} />
    <input bind:value={link} placeholder={t("Pega un link de playlist o álbum")} />
    <button class="pildora cian chica" disabled={leyendo || !link.trim()}>{leyendo ? t("Leyendo…") : t("Descargar")}</button>
  </form>
  <p class="nota">{t("YouTube, YT Music, Spotify, Tidal o SoundCloud. Las que ya tienes no se vuelven a bajar.")}</p>

  {#each lista as tr (tr.id)}
    <div class="trabajo" transition:slide={{ duration: 250 }}>
      <Portada url={tr.portada} tam="50px" radio="8px" />
      <div class="textos">
        <b class="cortar">{tr.titulo}</b>
        <small class="cortar {tr.estado}">{textos[tr.estado] ?? tr.estado}{#if tr.estado === "descargando"} · {tr.pct}%{/if}{#if tr.error} · {tr.error}{/if}</small>
        {#if ["descargando", "buscando", "etiquetando", "cola"].includes(tr.estado)}
          <div class="barra"><div style:width="{tr.estado === 'etiquetando' ? 100 : tr.pct}%"></div></div>
        {/if}
      </div>
      {#if tr.estado === "listo" && tr.cancion}
        <button class="redondo" onclick={() => reproducir([tr.cancion], 0, t("Descargas"))} aria-label={t("Escuchar")}><Icono nombre="play" relleno tam={20} /></button>
      {:else if ["cola", "buscando", "descargando"].includes(tr.estado)}
        <button class="redondo" onclick={() => py("cancelar_descarga", { id: tr.id })} aria-label={t("Cancelar")}><Icono nombre="cerrar" tam={20} /></button>
      {/if}
    </div>
  {:else}
    <p class="vacio" in:fade>{t("No hay descargas. Busca música o pega un link de playlist.")}</p>
  {/each}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
  header { display: flex; align-items: center; justify-content: space-between; }
  .limpiar { color: var(--cian); font-weight: 700; }
  .caja {
    margin-top: 16px; display: flex; align-items: center; gap: 10px; height: 54px; padding: 0 6px 0 14px;
    border-radius: 14px; background: var(--tarjeta); border: 1px solid var(--borde); color: var(--tenue);
  }
  .caja input { flex: 1; min-width: 0; height: 100%; border: 0; outline: 0; background: transparent; color: var(--texto); }
  .chica { height: 42px; padding: 0 16px; font-size: 14px; }
  .chica:disabled { opacity: 0.5; }
  .nota { color: var(--tenue); font-size: 13px; margin: 8px 2px 14px; }
  .trabajo { display: flex; align-items: center; gap: 12px; padding: 8px 0; }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  small { color: var(--tenue); font-size: 13px; }
  small.listo, small.existe { color: var(--verde); }
  small.error { color: var(--rojo); }
  small.descargando, small.etiquetando, small.buscando { color: var(--cian); }
  .barra { height: 3px; border-radius: 2px; background: var(--borde-fuerte); overflow: hidden; }
  .barra div { height: 100%; background: var(--cian); transition: width 0.4s var(--curva); }
</style>
