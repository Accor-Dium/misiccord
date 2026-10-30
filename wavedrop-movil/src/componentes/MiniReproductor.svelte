<script>
  import { t } from "../lib/idioma.svelte.js";
  import { fly } from "svelte/transition";
  import { abrirReproductor, irPestana, nav, ui } from "../lib/estado.svelte.js";
  import { control, jam, pistaActual, posicionJam, soyAnfitrion, urlJam, votar } from "../lib/jam.svelte.js";
  import Volumen from "./Volumen.svelte";
  import { alternar, rep, siguiente } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Reproductor flotante sobre la barra de navegación; tócalo para verlo en grande.
  // Dentro de un jam muestra lo que suena en el jam (y lleva a la pestaña Jams).
  const enJam = $derived(!!jam.sala);
  const pista = $derived(enJam ? pistaActual() : null);
  const anfitrion = $derived(soyAnfitrion());
  const enVistaJams = $derived(nav.pila.at(-1)?.vista === "jams");

  let posJam = $state(0);
  $effect(() => {
    if (!enJam) return;
    posJam = posicionJam();
    const reloj = setInterval(() => (posJam = posicionJam()), 500);
    return () => clearInterval(reloj);
  });

  const avance = $derived(
    enJam ? (pista?.duracion ? Math.min(100, (posJam / pista.duracion) * 100) : 0)
          : rep.dur ? (rep.pos / rep.dur) * 100 : 0,
  );
</script>

{#if enJam}
  <div class="mini jam" class:solo-escritorio={enVistaJams} transition:fly={{ y: 90, duration: 350 }}>
    <button class="info" onclick={() => irPestana("jams")}>
      <span class="tapa">
        <Portada url={urlJam(pista?.portada)} tam="46px" radio="8px" icono="jam" />
        {#if jam.sala.sonando && pista}<span class="eq"><i></i><i></i><i></i></span>{/if}
      </span>
      <div class="textos">
        <small class="etiqueta"><i class:caido={!jam.conectado}></i> JAM · {jam.sala.nombre}</small>
        <b class="cortar">{pista ? pista.titulo : t("La cola está vacía")}</b>
        <small class="cortar">{pista ? t("{artista} · la puso {quien}", { artista: pista.artista, quien: pista.agregada_por }) : t("Toca para agregar canciones")}</small>
      </div>
    </button>
    {#if anfitrion}
      <button class="redondo play" onclick={() => control(jam.sala.sonando ? "pausa" : "play")} aria-label={jam.sala.sonando ? t("Pausar") : t("Reproducir")}>
        <Icono nombre={jam.sala.sonando ? "pausa" : "play"} relleno tam={22} />
      </button>
      <button class="redondo" onclick={() => control("siguiente")} aria-label={t("Siguiente")}><Icono nombre="siguiente" relleno tam={22} /></button>
    {:else if pista}
      <button class="redondo saltar" onclick={() => votar()} aria-label={t("Votar para saltar")}>
        <Icono nombre="siguiente" relleno tam={20} /><small>{jam.sala.votos}/{jam.sala.votos_necesarios}</small>
      </button>
    {/if}
    {#if ui.amplio && jam.escuchando}<div class="vol"><Volumen ancho="190px" /></div>{/if}
    <div class="avance" style:width="{avance}%"></div>
  </div>
{:else if rep.actual}
  <div class="mini" transition:fly={{ y: 90, duration: 350 }}>
    <button class="info" onclick={abrirReproductor}>
      <Portada url={rep.actual.portada} tam="46px" radio="8px" />
      <div class="textos">
        <b class="cortar">{rep.actual.titulo}</b>
        <small class="cortar">{rep.actual.artista}{#if !rep.actual.ruta} · {t("vista previa")}{/if}</small>
      </div>
    </button>
    <button class="redondo play" onclick={alternar} aria-label={rep.sonando ? t("Pausar") : t("Reproducir")}>
      {#if rep.cargando}<span class="girando"></span>
      {:else}<Icono nombre={rep.sonando ? "pausa" : "play"} relleno tam={22} />{/if}
    </button>
    <button class="redondo" onclick={siguiente} aria-label={t("Siguiente")}><Icono nombre="siguiente" relleno tam={22} /></button>
    {#if ui.amplio}<div class="vol"><Volumen ancho="190px" /></div>{/if}
    <div class="avance" style:width="{avance}%"></div>
  </div>
{/if}

<style>
  .mini {
    position: fixed; z-index: 31; left: 10px; right: 10px;
    bottom: calc(var(--nav) + var(--seguro-abajo) + 6px); height: var(--mini);
    display: flex; align-items: center; gap: 6px; padding: 0 8px 0 10px; border-radius: 18px;
    background: rgba(28, 42, 53, 0.92); backdrop-filter: blur(22px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45); overflow: hidden;
  }
  .mini.jam { background: linear-gradient(100deg, rgba(14, 60, 72, 0.95), rgba(40, 36, 70, 0.95)); border: 1px solid rgba(34, 211, 238, 0.25); }
  .info { flex: 1; min-width: 0; display: flex; align-items: center; gap: 12px; text-align: left; height: 100%; }
  .textos { min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .textos b { font-size: 15px; font-weight: 700; }
  .textos small { color: var(--tenue); font-size: 13px; }
  .etiqueta { display: flex; align-items: center; gap: 6px; color: var(--cian) !important; font-size: 10.5px !important; font-weight: 800; letter-spacing: 1.2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .etiqueta i { width: 7px; height: 7px; border-radius: 50%; background: var(--verde); flex-shrink: 0; animation: latido 1.4s infinite; }
  .etiqueta i.caido { background: var(--tenue); }
  @keyframes latido { 50% { opacity: 0.3; } }
  .tapa { position: relative; flex-shrink: 0; }
  .eq { position: absolute; inset: 0; border-radius: 8px; background: rgba(0, 0, 0, 0.45); display: flex; align-items: flex-end; justify-content: center; gap: 3px; padding-bottom: 11px; }
  .eq i { width: 4px; border-radius: 2px; background: var(--cian); animation: barra 0.9s infinite ease-in-out; }
  .eq i:nth-child(2) { animation-delay: -0.3s; }
  .eq i:nth-child(3) { animation-delay: -0.6s; }
  @keyframes barra { 0%, 100% { height: 6px; } 50% { height: 18px; } }
  .play { background: var(--texto); color: #04121a; width: 46px; height: 46px; }
  .saltar { width: auto; padding: 0 12px; gap: 4px; display: flex; align-items: center; border-radius: 999px; background: rgba(255, 255, 255, 0.1); }
  .saltar small { font-size: 12.5px; font-weight: 700; }
  .avance { position: absolute; left: 0; bottom: 0; height: 2px; background: var(--cian); transition: width 0.5s linear; }
  /* Cel acostado: junto al riel de pestañas, más bajito */
  @media (orientation: landscape) and (max-height: 560px) {
    .mini { left: calc(var(--riel) + 10px); right: calc(10px + env(safe-area-inset-right, 0px)); bottom: calc(var(--seguro-abajo) + 8px); }
    .play { width: 42px; height: 42px; }
  }
  /* En la pestaña Jams del cel la sala ya muestra todo: la barra sobra */
  .solo-escritorio { display: none; }
  @media (min-width: 900px) and (min-height: 561px) {
    .mini { left: calc(var(--lateral) + 16px); right: 16px; bottom: 16px; padding: 0 16px; gap: 12px; }
    .solo-escritorio { display: flex; }
    .info { gap: 16px; }
    .textos b { font-size: 16px; }
    .vol { margin-left: 12px; padding-left: 14px; border-left: 1px solid var(--borde-fuerte); }
  }
  .girando {
    width: 20px; height: 20px; border-radius: 50%; border: 2.5px solid rgba(4, 18, 26, 0.25);
    border-top-color: #04121a; animation: giro 0.8s linear infinite;
  }
  @keyframes giro { to { transform: rotate(360deg); } }
</style>
