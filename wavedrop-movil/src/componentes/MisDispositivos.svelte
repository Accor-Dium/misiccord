<script>
  import { onMount } from "svelte";
  import { slide } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { aviso, mostrarHoja } from "../lib/estado.svelte.js";
  import { t } from "../lib/idioma.svelte.js";
  import { leerQR } from "../lib/qr.js";
  import { cargarSinc, leerVinculo, sinc } from "../lib/sincronizacion.svelte.js";
  import Icono from "./Icono.svelte";

  // Ajustes → Mis dispositivos: vincular el cel con la PC (sin cuentas) y ver cómo van.
  // Para vincular, en los dos se toca "Vincular": cada uno muestra su código y ve al otro en "Cerca de ti";
  // en uno se elige al otro y se escribe el código que muestra (o se escanea su QR desde el cel).
  let { android = false } = $props();
  let abierto = $state(false);
  let qr = $state(null); // { qr (svg), texto } del código de este dispositivo
  let elegido = $state(null); // dispositivo cercano al que te vas a vincular
  let codigo = $state("");
  let ocupado = $state(false);
  let ahora = $state(Date.now() / 1000);
  let vinculadosAlAbrir = 0;
  const est = $derived(sinc.estado);
  const codigoMio = $derived(est?.vinculando?.codigo ?? qr?.vinculando?.codigo);

  onMount(() => {
    cargarSinc().catch(() => {});
    const reloj = setInterval(() => (ahora = Date.now() / 1000), 15000);
    return () => {
      clearInterval(reloj);
      if (abierto) py("sinc_vincular_cerrar").catch(() => {});
    };
  });

  // Un QR escaneado con la cámara normal (abre la app con misiccord://vincular)
  $effect(() => {
    if (!sinc.vinculo) return;
    const v = sinc.vinculo;
    sinc.vinculo = null;
    vincularCon(v);
  });

  // El otro escribió el código de este: Python cierra la vinculación solo y aparece uno más en la lista
  $effect(() => {
    if (abierto && est && !est.vinculando && est.dispositivos.length > vinculadosAlAbrir) {
      const nuevo = est.dispositivos.at(-1);
      aviso(t("Vinculado con {nombre}: se sincronizan solos cuando estén en la misma red", { nombre: nuevo.nombre }), "ok");
      abierto = false;
      qr = null;
    }
  });

  async function abrirVinculacion() {
    abierto = true;
    elegido = null;
    codigo = "";
    vinculadosAlAbrir = est?.dispositivos.length ?? 0;
    try {
      qr = await py("sinc_vincular");
      sinc.estado = await py("sinc_buscar");
    } catch (e) {
      aviso(e.message, "error");
      abierto = false;
    }
  }

  async function cerrarVinculacion() {
    abierto = false;
    qr = null;
    elegido = null;
    sinc.estado = await py("sinc_vincular_cerrar").catch(() => sinc.estado);
  }

  async function vincularCon(datos) {
    ocupado = true;
    try {
      const r = await py("sinc_vincular_con", datos);
      vinculadosAlAbrir = r.dispositivos.length; // este aviso ya se da aquí
      sinc.estado = r;
      aviso(t("Vinculado con {nombre}: se sincronizan solos cuando estén en la misma red", { nombre: r.vinculado.nombre }), "ok");
      if (abierto) await cerrarVinculacion();
    } catch (e) {
      aviso(e.message, "error");
    } finally {
      ocupado = false;
    }
  }

  async function escanear() {
    const texto = await leerQR();
    if (texto === null) return;
    const v = leerVinculo(texto);
    if (!v) return aviso(t("Ese QR no es de Mis dispositivos de Misiccord"), "error");
    vincularCon(v);
  }

  function enviarCodigo(evento) {
    evento.preventDefault();
    if (codigo.replace(/\D/g, "").length !== 6) return aviso(t("El código tiene 6 números"));
    vincularCon({ ip: elegido.ip, puerto: elegido.puerto, codigo });
  }

  async function sincronizarAhora(d) {
    try {
      sinc.estado = await py("sinc_ahora", { id: d.id });
    } catch (e) {
      aviso(e.message, "error");
    }
  }

  function menu(d) {
    mostrarHoja({
      titulo: d.nombre,
      subtitulo: estadoDe(d),
      opciones: [
        {
          texto: d.copiar ? t("No recibir sus canciones") : t("Recibir sus canciones"),
          icono: "descargas",
          accion: async () => (sinc.estado = await py("sinc_ajustar", { id: d.id, copiar: !d.copiar })),
        },
        {
          texto: t("Desvincular"), icono: "cerrar", peligro: true,
          accion: async () => {
            sinc.estado = await py("sinc_desvincular", { id: d.id });
            aviso(t("{nombre} ya no se sincroniza con este dispositivo", { nombre: d.nombre }));
          },
        },
      ],
    });
  }

  function haceCuanto(s) {
    const min = Math.round((ahora - s) / 60);
    if (min < 1) return t("hace un momento");
    if (min < 60) return t("hace {n} min", { n: min });
    if (min < 60 * 24) return t("hace {n} h", { n: Math.round(min / 60) });
    return t("hace {n} días", { n: Math.round(min / 1440) });
  }

  function estadoDe(d) {
    if (d.sincronizando) {
      const p = est?.progreso;
      return p?.id === d.id && p.total ? `${p.texto} (${p.hechas}/${p.total})` : t("Sincronizando…");
    }
    const ultima = d.ultima ? t("Última vez {cuando}", { cuando: haceCuanto(d.ultima) }) : t("Todavía no se sincroniza");
    if (d.error) return `${ultima} · ${d.error}`;
    return d.en_linea ? `${t("En esta red")} · ${ultima}` : ultima;
  }
</script>

<section>
  <h2>{t("Mis dispositivos")}</h2>
  <p class="tenue explica">
    {t("Vincula tu cel con tu PC (o con otro cel) para tener lo mismo en los dos: Me gusta, playlists, categorías, historial y las canciones que le falten a cada uno. Se sincronizan solos cuando están en la misma red Wi-Fi. Sin cuentas.")}
  </p>

  {#if est}
    {#each est.dispositivos as d (d.id)}
      <div class="dispositivo" transition:slide={{ duration: 200 }}>
        <span class="icono" class:vivo={d.en_linea}><Icono nombre="dispositivos" tam={22} /></span>
        <div class="texto">
          <b class="cortar">{d.nombre}</b>
          <small class:error={d.error && !d.sincronizando}>{estadoDe(d)}</small>
          {#if d.sincronizando && est.progreso?.id === d.id && est.progreso.total}
            <div class="progreso"><div style:width="{(est.progreso.hechas / est.progreso.total) * 100}%"></div></div>
          {/if}
        </div>
        <button class="redondo" disabled={!d.en_linea || d.sincronizando} onclick={() => sincronizarAhora(d)} aria-label={t("Sincronizar ahora")}
          title={d.en_linea ? t("Sincronizar ahora") : t("No está en esta red")}>
          <span class:gira={d.sincronizando}><Icono nombre="actualizar" tam={20} /></span>
        </button>
        <button class="redondo" onclick={() => menu(d)} aria-label={t("Más opciones")}><Icono nombre="mas" tam={20} /></button>
      </div>
    {/each}

    {#if !abierto}
      <button class="pildora cian vincular" onclick={abrirVinculacion}><Icono nombre="agregar" tam={20} /> {t("Vincular un dispositivo")}</button>
      <p class="tenue este">{t("Este dispositivo se llama “{nombre}”", { nombre: est.nombre })}</p>
    {:else}
      <div class="panel" transition:slide={{ duration: 220 }}>
        <p class="tenue">{t("Toca Vincular también en el otro dispositivo. Después, en uno de los dos, elige al otro y escribe el código que muestra.")}</p>
        <div class="columnas">
          <div class="mio">
            <small class="tenue">{t("Código de este dispositivo")}</small>
            <b class="codigo">{codigoMio ? `${codigoMio.slice(0, 3)} ${codigoMio.slice(3)}` : "··· ···"}</b>
            <div class="qr">{#if qr}{@html qr.qr}{:else}<div class="cargando-bloque" style="aspect-ratio:1"></div>{/if}</div>
            <small class="tenue">{t("Desde un cel también puedes escanear este QR")}</small>
          </div>
          <div class="otros">
            <small class="tenue">{t("Cerca de ti")}</small>
            {#each est.cercanos as c (c.id)}
              <button class="cercano" class:activo={elegido?.id === c.id} onclick={() => { elegido = c; codigo = ""; }}>
                <Icono nombre="dispositivos" tam={20} /><span class="cortar">{c.nombre}</span>
              </button>
              {#if elegido?.id === c.id}
                <form class="escribir" onsubmit={enviarCodigo} transition:slide={{ duration: 160 }}>
                  <!-- svelte-ignore a11y_autofocus -->
                  <input inputmode="numeric" autocomplete="one-time-code" maxlength="7" placeholder="000 000" autofocus
                    bind:value={codigo} aria-label={t("Código que muestra {nombre}", { nombre: c.nombre })} />
                  <button class="pildora cian" disabled={ocupado}>{ocupado ? t("Vinculando…") : t("Vincular")}</button>
                </form>
              {/if}
            {:else}
              <p class="tenue buscando">{t("Buscando… Abre Ajustes → Mis dispositivos → Vincular en el otro, conectado a la misma red Wi-Fi.")}</p>
            {/each}
            {#if android}
              <button class="pildora oscura escanear" disabled={ocupado} onclick={escanear}><Icono nombre="camara" tam={20} /> {t("Escanear su QR")}</button>
            {/if}
          </div>
        </div>
        <button class="restaurar" onclick={cerrarVinculacion}>{t("Cancelar")}</button>
      </div>
    {/if}
  {/if}
</section>

<style>
  section { margin-top: 26px; }
  h2 { font-size: 13px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--cian); margin: 0 0 8px; }
  .explica { line-height: 1.5; font-size: 14px; margin: 0 0 6px; }
  .dispositivo { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--borde); }
  .icono { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; flex-shrink: 0; background: var(--tarjeta-2); color: var(--tenue); }
  .icono.vivo { color: var(--cian); background: rgba(34, 211, 238, 0.12); }
  .texto { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .texto b { font-weight: 600; }
  .texto small { color: var(--tenue); line-height: 1.35; }
  .texto small.error { color: #fca5a5; }
  .redondo { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; flex-shrink: 0; color: var(--texto); }
  .redondo:disabled { opacity: 0.35; }
  .gira { display: grid; animation: girar 1s linear infinite; }
  @keyframes girar { to { transform: rotate(360deg); } }
  .progreso { height: 3px; border-radius: 2px; background: var(--borde-fuerte); overflow: hidden; margin-top: 4px; }
  .progreso div { height: 100%; background: var(--cian); transition: width 0.4s var(--curva); }
  .vincular { margin-top: 14px; height: 44px; padding: 0 18px; display: inline-flex; align-items: center; gap: 8px; }
  .este { font-size: 13px; margin: 10px 0 0; }
  .panel { margin-top: 14px; padding: 16px; border-radius: 16px; background: var(--tarjeta); border: 1px solid var(--borde); }
  .panel > p { margin: 0 0 14px; font-size: 14px; line-height: 1.45; }
  .columnas { display: flex; flex-direction: column; gap: 18px; }
  .mio { display: flex; flex-direction: column; align-items: center; gap: 8px; text-align: center; }
  .codigo { font-size: 34px; font-weight: 900; letter-spacing: 4px; font-variant-numeric: tabular-nums; }
  .qr { width: 170px; border-radius: 12px; overflow: hidden; background: #fff; }
  .qr :global(svg) { display: block; width: 100%; height: auto; }
  .otros { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .cercano { display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 12px; background: var(--tarjeta-2); text-align: left; min-width: 0; }
  .cercano.activo { outline: 2px solid var(--cian); }
  .buscando { font-size: 13.5px; line-height: 1.45; margin: 0; }
  .escribir { display: flex; gap: 8px; }
  .escribir input {
    flex: 1; min-width: 0; height: 46px; border-radius: 12px; border: 1px solid var(--borde-fuerte); background: var(--tarjeta-2);
    color: inherit; font: inherit; font-size: 20px; letter-spacing: 3px; text-align: center; font-variant-numeric: tabular-nums;
  }
  .escribir .pildora { height: 46px; padding: 0 18px; }
  .escanear { height: 44px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
  .restaurar { color: var(--cian); font-weight: 600; padding: 14px 0 0; }
  @media (min-width: 900px) and (min-height: 561px) {
    .columnas { flex-direction: row; align-items: flex-start; }
    .mio { width: 220px; flex-shrink: 0; }
    .otros { flex: 1; }
  }
</style>
