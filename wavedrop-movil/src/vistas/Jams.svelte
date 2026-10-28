<script>
  import { onMount } from "svelte";
  import { fade, fly, slide } from "svelte/transition";
  import { tiempo } from "../lib/api.js";
  import { aviso } from "../lib/estado.svelte.js";
  import {
    agregar, alternarEscuchar, bibliotecaAnfitrion, buscarCercanos, buscarEnAnfitrion, control, crear, jam,
    pistaActual, posicionJam, reaccionar, salir, soyAnfitrion, unirse, urlJam, votar,
  } from "../lib/jam.svelte.js";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";

  let { e } = $props();

  // ---------- Fuera de un jam ----------
  let nombre = $state(localStorage.getItem("wavedrop_nombre") || "");
  let modo = $state("sincronizado");
  let ocupado = $state(false);
  let cercanos = $state(null);
  let elegido = $state(null); // jam cercano al que te vas a unir (falta el código)
  let codigo = $state("");
  let manual = $state({ ip: "", puerto: "47480", codigo: "" });

  $effect(() => localStorage.setItem("wavedrop_nombre", nombre));

  async function buscar() {
    cercanos = null;
    try {
      cercanos = await buscarCercanos();
    } catch {
      cercanos = [];
    }
  }
  onMount(() => { if (!jam.sala) buscar(); });

  async function intentar(f) {
    if (!nombre.trim()) {
      aviso("Escribe tu nombre para que los demás sepan quién eres");
      return;
    }
    ocupado = true;
    try {
      await f();
    } catch (err) {
      aviso(err.message || "No se pudo conectar", "error");
    } finally {
      ocupado = false;
    }
  }

  // ---------- Dentro de un jam ----------
  const s = $derived(jam.sala);
  const p = $derived(pistaActual());
  const anfitrion = $derived(soyAnfitrion());
  let pos = $state(0);
  onMount(() => {
    const t = setInterval(() => (pos = posicionJam()), 500);
    return () => clearInterval(t);
  });
  const duracion = $derived(p?.duracion || 0);

  let panelAgregar = $state(false);
  let fuente = $state("biblioteca");
  let q = $state("");
  let resultados = $state([]);
  let cargando = $state(false);
  let ajustes = $state(false);

  async function cargarResultados() {
    cargando = true;
    try {
      resultados = fuente === "biblioteca"
        ? (await bibliotecaAnfitrion(q.trim())).canciones
        : q.trim() ? (await buscarEnAnfitrion(q.trim())).canciones : [];
    } catch (err) {
      aviso(err.message, "error");
    } finally {
      cargando = false;
    }
  }
  $effect(() => { if (panelAgregar) { fuente; cargarResultados(); } });

  async function sumar(c) {
    try {
      await agregar(c);
      aviso(c.local || c.ruta ? `“${c.titulo}” a la cola` : `Descargando “${c.titulo}” para el jam`, "ok");
    } catch (err) {
      aviso(err.message, "error");
    }
  }

  const emojis = ["🔥", "❤️", "😂", "👏", "🎉", "😮"];
  // Reacciones recientes (últimos 4 s según el reloj del anfitrión) flotando sobre la portada
  const flotando = $derived((s?.reacciones ?? []).filter((r) => Date.now() + jam.desfase - r.ms < 4000));
  const iniciales = (n) => n.split(" ").map((x) => x[0]).join("").slice(0, 2).toUpperCase();
</script>

<div class="vista">
  {#if !s}
    <!-- ---------- Crear o unirse ---------- -->
    <div in:fade={{ duration: 220 }}>
      <h1 class="titulo-vista">Jams</h1>
      <p class="tenue intro">Escuchen juntos en la misma red: todos arman la cola y la música suena sincronizada.</p>

      <label class="campo">
        <span>Tu nombre</span>
        <input bind:value={nombre} placeholder="¿Cómo te ven los demás?" maxlength="30" />
      </label>

      <section class="tarjeta">
        <h2><Icono nombre="jam" tam={22} /> Crear un jam</h2>
        <div class="modos">
          <button class:activo={modo === "sincronizado"} onclick={() => (modo = "sincronizado")}>
            <b>Sincronizado</b><small>Suena en todos los dispositivos al mismo tiempo</small>
          </button>
          <button class:activo={modo === "anfitrion"} onclick={() => (modo = "anfitrion")}>
            <b>Solo aquí</b><small>Suena en este dispositivo (ideal con una bocina)</small>
          </button>
        </div>
        <button class="pildora cian ancho" disabled={ocupado} onclick={() => intentar(() => crear(nombre.trim(), modo))}>
          {ocupado ? "Abriendo…" : "Crear jam"}
        </button>
      </section>

      <div class="titulo-seccion">Jams cercanos <button onclick={buscar}><small>Buscar de nuevo</small></button></div>
      {#if cercanos === null}
        <div class="cargando-bloque" style="height:64px"></div>
      {:else if !cercanos.length}
        <p class="tenue nota">No encontré jams en tu red. Pídele al anfitrión su dirección y código, o vuelve a buscar.</p>
      {:else}
        {#each cercanos as j}
          <button class="cercano" class:elegido={elegido === j} onclick={() => { elegido = j; codigo = ""; }}>
            <span class="avatar vivo"><Icono nombre="jam" tam={22} /></span>
            <span class="textos"><b class="cortar">{j.nombre}</b><small>{j.ip}:{j.puerto}</small></span>
          </button>
          {#if elegido === j}
            <form class="codigo" transition:slide={{ duration: 200 }}
              onsubmit={(ev) => { ev.preventDefault(); intentar(() => unirse(j.ip, j.puerto, codigo, nombre.trim())); }}>
              <input bind:value={codigo} placeholder="Código de 4 dígitos" inputmode="numeric" maxlength="4" />
              <button class="pildora cian" disabled={ocupado || codigo.length !== 4}>Unirme</button>
            </form>
          {/if}
        {/each}
      {/if}

      <details class="manual">
        <summary>Unirse con dirección</summary>
        <form onsubmit={(ev) => { ev.preventDefault(); intentar(() => unirse(manual.ip.trim(), manual.puerto, manual.codigo, nombre.trim())); }}>
          <input bind:value={manual.ip} placeholder="IP del anfitrión (ej. 192.168.1.14)" />
          <div class="fila2">
            <input bind:value={manual.puerto} placeholder="Puerto" inputmode="numeric" />
            <input bind:value={manual.codigo} placeholder="Código" inputmode="numeric" maxlength="4" />
          </div>
          <button class="pildora oscura ancho" disabled={ocupado}>Unirme</button>
        </form>
      </details>
    </div>
  {:else}
    <!-- ---------- La sala ---------- -->
    <div in:fade={{ duration: 250 }}>
      <div class="sala-cab">
        <div>
          <small class="envivo"><i></i> {jam.conectado ? "EN VIVO" : "RECONECTANDO…"}</small>
          <h1>{s.nombre}</h1>
          <p class="tenue">{s.modo === "sincronizado" ? "Sincronizado en todos" : "Suena en el anfitrión"} · {s.participantes.length} conectados</p>
        </div>
        <button class="redondo relleno" onclick={() => (ajustes = !ajustes)} aria-label="Ajustes del jam"><Icono nombre="ajustes" tam={22} /></button>
      </div>

      {#if anfitrion}
        <div class="acceso">
          <div><small>CÓDIGO</small><b class="codigo-grande">{jam.conexion.codigo}</b></div>
          <div><small>DIRECCIÓN</small><b>{jam.conexion.ips?.[0]}:{jam.conexion.puerto}</b></div>
        </div>
      {/if}

      {#if ajustes}
        <section class="tarjeta" transition:slide={{ duration: 220 }}>
          {#if anfitrion}
            <div class="ajuste">
              <span>Modo</span>
              <div class="segmentos">
                <button class:activo={s.modo === "sincronizado"} onclick={() => control("modo", { modo: "sincronizado" })}>Sincronizado</button>
                <button class:activo={s.modo === "anfitrion"} onclick={() => control("modo", { modo: "anfitrion" })}>Solo aquí</button>
              </div>
            </div>
            <label class="ajuste">
              <span>Invitados pueden agregar canciones</span>
              <input type="checkbox" class="interruptor" checked={s.invitados_agregan}
                onchange={(ev) => control("permisos", { invitados_agregan: ev.target.checked })} />
            </label>
          {/if}
          {#if s.modo === "sincronizado" || anfitrion}
            <label class="ajuste">
              <span>Escuchar en este dispositivo</span>
              <input type="checkbox" class="interruptor" checked={jam.escuchando} onchange={alternarEscuchar} />
            </label>
          {/if}
          <div class="personas">
            {#each s.participantes as persona}
              <div class="persona">
                <span class="avatar">{iniciales(persona.nombre)}</span>
                <span class="cortar">{persona.nombre}{#if persona.rol === "anfitrion"} · anfitrión{/if}</span>
                {#if anfitrion && persona.rol !== "anfitrion"}
                  <button class="sacar" onclick={() => control("expulsar", { cliente_corto: persona.cliente })}>Sacar</button>
                {/if}
              </div>
            {/each}
          </div>
        </section>
      {/if}

      <!-- Lo que suena -->
      <section class="ahora">
        {#if p}
          <div class="ambiente" style:background-image={p.portada ? `url("${urlJam(p.portada)}")` : "none"}></div>
          <div class="tapa">
            <Portada url={urlJam(p.portada)} radio="14px" sombra />
            {#each flotando as r (r.ms)}
              <span class="flota" in:fly={{ y: 0, duration: 1 }} style:left="{(r.ms % 70) + 10}%">{r.emoji}</span>
            {/each}
          </div>
          <h2 class="cortar">{p.titulo}</h2>
          <p class="cortar tenue">{p.artista} · la puso {p.agregada_por}</p>
          <div class="progreso"><div style:width="{duracion ? Math.min(100, (pos / duracion) * 100) : 0}%"></div></div>
          <div class="tiempos"><span>{tiempo(pos)}</span><span>{tiempo(duracion)}</span></div>
        {:else}
          <div class="sin-pista">
            <Icono nombre="nota" tam={40} />
            <p>La cola está vacía. ¡Agrega la primera canción!</p>
          </div>
        {/if}

        <div class="controles">
          {#if anfitrion}
            <button class="redondo grande" onclick={() => control("anterior")} aria-label="Anterior"><Icono nombre="anterior" relleno tam={30} /></button>
            <button class="play" onclick={() => control(s.sonando ? "pausa" : "play")} aria-label="Reproducir o pausar">
              <Icono nombre={s.sonando ? "pausa" : "play"} relleno tam={32} />
            </button>
            <button class="redondo grande" onclick={() => control("siguiente")} aria-label="Siguiente"><Icono nombre="siguiente" relleno tam={30} /></button>
          {:else}
            <button class="pildora oscura" onclick={() => votar().then(() => aviso("Votaste para saltar"))} disabled={!p}>
              <Icono nombre="siguiente" relleno tam={18} /> Saltar ({s.votos}/{s.votos_necesarios})
            </button>
          {/if}
        </div>
        <div class="emojis">
          {#each emojis as em}<button onclick={() => reaccionar(em)}>{em}</button>{/each}
        </div>
      </section>

      <!-- Cola -->
      <div class="titulo-seccion">
        Cola
        {#if anfitrion || s.invitados_agregan}
          <button class="pildora cian chica" onclick={() => (panelAgregar = !panelAgregar)}>
            <Icono nombre={panelAgregar ? "cerrar" : "agregar"} tam={18} /> {panelAgregar ? "Cerrar" : "Agregar"}
          </button>
        {/if}
      </div>

      {#if panelAgregar}
        <section class="tarjeta" transition:slide={{ duration: 220 }}>
          <div class="segmentos">
            <button class:activo={fuente === "biblioteca"} onclick={() => (fuente = "biblioteca")}>Biblioteca del anfitrión</button>
            <button class:activo={fuente === "buscar"} onclick={() => (fuente = "buscar")}>YouTube Music</button>
          </div>
          <form class="buscador" onsubmit={(ev) => { ev.preventDefault(); cargarResultados(); }}>
            <Icono nombre="buscar" tam={18} />
            <input bind:value={q} placeholder={fuente === "biblioteca" ? "Filtrar canciones…" : "Buscar canción o artista…"} />
          </form>
          {#if cargando}
            <div class="cargando-bloque" style="height:48px;margin:8px 0"></div>
          {:else}
            {#each resultados.slice(0, 40) as c}
              <div class="resultado">
                <Portada url={c.local ? null : c.portada} tam="42px" radio="6px" />
                <span class="textos"><b class="cortar">{c.titulo}</b><small class="cortar">{c.artista}</small></span>
                <button class="redondo" onclick={() => sumar(c)} aria-label="Agregar a la cola"><Icono nombre="agregar" tam={22} /></button>
              </div>
            {:else}
              <p class="tenue nota">{fuente === "buscar" && !q.trim() ? "Escribe qué quieres escuchar." : "Sin resultados."}</p>
            {/each}
          {/if}
        </section>
      {/if}

      {#each s.cola as pista, i (pista.pid)}
        <div class="pista" class:actual={i === s.indice} class:pasada={i < s.indice} transition:slide={{ duration: 200 }}>
          <Portada url={urlJam(pista.portada)} tam="46px" radio="6px" />
          <span class="textos">
            <b class="cortar">{pista.titulo}</b>
            <small class="cortar">
              {#if pista.estado === "descargando"}Descargando…{:else if pista.estado === "error"}No se pudo descargar{:else}{pista.artista}{/if}
              · {pista.agregada_por}
            </small>
          </span>
          {#if anfitrion}
            {#if i !== s.indice && pista.estado === "lista"}
              <button class="redondo" onclick={() => control("saltar_a", { indice: i })} aria-label="Poner ya"><Icono nombre="play" relleno tam={18} /></button>
            {/if}
            <button class="redondo" onclick={() => control("quitar", { pid: pista.pid })} aria-label="Quitar"><Icono nombre="cerrar" tam={18} /></button>
          {/if}
        </div>
      {/each}

      <button class="salir" onclick={salir}>{anfitrion ? "Terminar jam" : "Salir del jam"}</button>
    </div>
  {/if}
</div>

<style>
  .vista { padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
  .intro { margin: 8px 0 18px; line-height: 1.5; }
  .campo { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
  .campo span { font-size: 13px; color: var(--tenue); font-weight: 600; }
  input:not([type="checkbox"]) {
    height: 48px; border-radius: 12px; border: 1px solid var(--borde-fuerte); background: var(--tarjeta);
    padding: 0 14px; outline: 0; width: 100%; min-width: 0;
  }
  input:focus { border-color: var(--cian); }
  .tarjeta { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 18px; padding: 16px; margin: 8px 0 14px; }
  .tarjeta h2 { display: flex; align-items: center; gap: 10px; margin: 0 0 14px; font-size: 18px; }
  .modos { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
  .modos button { text-align: left; padding: 12px; border-radius: 14px; border: 1px solid var(--borde-fuerte); display: flex; flex-direction: column; gap: 4px; }
  .modos small { color: var(--tenue); font-size: 12.5px; line-height: 1.35; }
  .modos .activo { border-color: var(--cian); background: rgba(34, 211, 238, 0.08); }
  .ancho { width: 100%; }
  .nota { font-size: 14px; line-height: 1.5; }
  .cercano { width: 100%; display: flex; align-items: center; gap: 12px; padding: 10px; border-radius: 14px; text-align: left; }
  .cercano.elegido, .cercano:active { background: var(--tarjeta); }
  .avatar { width: 46px; height: 46px; border-radius: 50%; background: var(--tarjeta-2); display: grid; place-items: center; font-weight: 800; flex-shrink: 0; color: var(--texto); }
  .avatar.vivo { color: var(--verde); }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .textos small { color: var(--tenue); }
  .codigo { display: flex; gap: 10px; margin: 0 0 10px; }
  .manual { margin-top: 18px; color: var(--tenue); }
  .manual summary { cursor: pointer; font-weight: 600; padding: 8px 0; }
  .manual form { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; }
  .fila2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

  .sala-cab { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .sala-cab h1 { margin: 4px 0 2px; font-size: 26px; font-weight: 800; }
  .sala-cab p { margin: 0; font-size: 14px; }
  .envivo { display: flex; align-items: center; gap: 6px; color: var(--verde); font-weight: 800; letter-spacing: 1.5px; font-size: 11px; }
  .envivo i { width: 8px; height: 8px; border-radius: 50%; background: var(--verde); animation: latido 1.4s infinite; }
  @keyframes latido { 50% { opacity: 0.3; } }
  .acceso { display: flex; gap: 12px; margin: 14px 0 4px; }
  .acceso > div { flex: 1; background: var(--tarjeta); border-radius: 14px; padding: 10px 14px; display: flex; flex-direction: column; }
  .acceso small { font-size: 11px; letter-spacing: 1.5px; color: var(--tenue); }
  .codigo-grande { font-size: 26px; letter-spacing: 6px; color: var(--cian); }
  .ajuste { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--borde); }
  .segmentos { display: flex; gap: 6px; flex-wrap: wrap; }
  .segmentos button { padding: 8px 14px; border-radius: 999px; background: var(--tarjeta-2); font-weight: 600; font-size: 14px; }
  .segmentos .activo { background: var(--texto); color: #04121a; }
  .interruptor { -webkit-appearance: none; appearance: none; width: 50px; height: 30px; border-radius: 15px; background: var(--borde-fuerte); position: relative; flex-shrink: 0; transition: background 0.25s; }
  .interruptor::after { content: ""; position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; border-radius: 50%; background: #fff; transition: transform 0.25s var(--curva); }
  .interruptor:checked { background: var(--cian); }
  .interruptor:checked::after { transform: translateX(20px); }
  .personas { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
  .persona { display: flex; align-items: center; gap: 10px; }
  .persona .avatar { width: 36px; height: 36px; font-size: 13px; }
  .persona span.cortar { flex: 1; }
  .sacar { color: var(--rojo); font-weight: 600; font-size: 14px; }

  .ahora { position: relative; text-align: center; margin: 20px calc(-1 * var(--margen)) 0; padding: 22px var(--margen) 18px; overflow: hidden; }
  .ambiente {
    position: absolute; inset: -20%; z-index: -1; background-size: cover; background-position: center;
    filter: blur(60px) saturate(1.4) brightness(0.5);
  }
  .tapa { position: relative; width: min(62%, 300px); margin: 0 auto 16px; }
  .flota { position: absolute; bottom: 10%; font-size: 34px; animation: subir 4s ease-out forwards; pointer-events: none; }
  @keyframes subir { from { transform: translateY(0) scale(0.6); opacity: 0; } 15% { opacity: 1; transform: translateY(-20px) scale(1.1); } to { transform: translateY(-220px) scale(1); opacity: 0; } }
  .ahora h2 { margin: 0; font-size: 22px; font-weight: 800; }
  .ahora p { margin: 4px 0 14px; }
  .progreso { height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 0.2); overflow: hidden; }
  .progreso div { height: 100%; background: #fff; transition: width 0.5s linear; }
  .tiempos { display: flex; justify-content: space-between; font-size: 12.5px; color: rgba(255, 255, 255, 0.7); margin-top: 6px; font-variant-numeric: tabular-nums; }
  .controles { display: flex; justify-content: center; align-items: center; gap: 22px; margin: 14px 0 10px; }
  .grande { width: 54px; height: 54px; }
  .play { width: 68px; height: 68px; border-radius: 50%; background: #fff; color: #04121a; display: grid; place-items: center; }
  .emojis { display: flex; justify-content: center; gap: 6px; }
  .emojis button { font-size: 24px; width: 46px; height: 46px; border-radius: 50%; background: rgba(255, 255, 255, 0.08); transition: transform 0.15s var(--curva); }
  .emojis button:active { transform: scale(1.3); }
  .sin-pista { padding: 30px 0; color: var(--tenue); display: grid; justify-items: center; gap: 10px; }

  .chica { height: 36px; padding: 0 14px; font-size: 14px; }
  .buscador { display: flex; align-items: center; gap: 8px; margin: 12px 0 6px; padding: 0 0 0 12px; border-radius: 12px; background: var(--fondo); color: var(--tenue); }
  .buscador input { border: 0; background: transparent; }
  .resultado, .pista { display: flex; align-items: center; gap: 12px; padding: 6px 0; }
  .pista.actual b { color: var(--cian); }
  .pista.pasada { opacity: 0.5; }
  .salir { display: block; margin: 26px auto 8px; color: var(--rojo); font-weight: 700; }

  @media (min-width: 900px) {
    .tapa { width: 280px; }
  }
</style>
