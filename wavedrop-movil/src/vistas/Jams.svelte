<script>
  import { onMount, untrack } from "svelte";
  import { fade, fly, scale, slide } from "svelte/transition";
  import { py, tiempo } from "../lib/api.js";
  import { aviso, ui } from "../lib/estado.svelte.js";
  import {
    agregar, agregarPropia, alternarEscuchar, bibliotecaAnfitrion, buscarCercanos, buscarEnAnfitrion, control, crear,
    jam, pistaActual, posicionJam, qrDelJam, reaccionar, salir, soyAnfitrion, unirse, unirseConDatos, urlJam, votar,
    abrirInternet,
  } from "../lib/jam.svelte.js";
  import { alEvento } from "../lib/api.js";
  import { aBody } from "../lib/aBody.js";
  import { copiar, leerInvitacion } from "../lib/enlaces.svelte.js";
  import Icono from "../componentes/Icono.svelte";
  import Portada from "../componentes/Portada.svelte";
  import Volumen from "../componentes/Volumen.svelte";

  let { e } = $props();

  // ---------- Fuera de un jam ----------
  let nombre = $state(localStorage.getItem("wavedrop_nombre") || "");
  let paso = $state("crear"); // en el cel: pestaña "crear" o "unirme" (en escritorio se ven las dos)
  let modo = $state("sincronizado");
  let ocupado = $state(false);
  let creando = $state(false);
  let cercanos = $state(null);
  let elegido = $state(null); // jam cercano al que te vas a unir (falta el código)
  let codigo = $state("");
  let manual = $state({ ip: "", puerto: "47480", codigo: "" });
  let link = $state("");
  let otrasFormas = $state(false);
  const esCelular = /Android|iPhone|iPad/i.test(navigator.userAgent);

  async function escanear() {
    if (!nombre.trim()) return aviso("Escribe tu nombre primero");
    try {
      // Cámara a pantalla completa con el escáner nativo (solo en el cel)
      const { scan, cancel, checkPermissions, requestPermissions, Format } = await import("@tauri-apps/plugin-barcode-scanner");
      let permiso = await checkPermissions();
      if (permiso !== "granted") permiso = await requestPermissions();
      if (permiso !== "granted") return aviso("Sin permiso de cámara no puedo leer el QR", "error");
      // "Atrás" de Android mientras la cámara está abierta: cancelar el escaneo en vez de salir de la app
      ui.alAtras = () => cancel().catch(() => {});
      history.pushState({ wavedrop: "camara" }, "");
      let r;
      try {
        r = await scan({ windowed: false, formats: [Format.QRCode] });
      } finally {
        if (ui.alAtras) {
          ui.alAtras = () => {}; // quitar la entrada del historial sin navegar
          history.back();
        }
      }
      unirseConLink(r?.content ?? "");
    } catch (err) {
      const texto = err?.message || String(err);
      if (!/cancel/i.test(texto)) aviso(texto, "error");
    }
  }

  function unirseConLink(texto) {
    const datos = leerInvitacion(texto);
    if (!datos) return aviso("Ese QR o link no es de un jam de Misiccord", "error");
    intentar(() => unirseConDatos(datos, nombre.trim()));
  }

  // ---------- Te abrieron con un link de jam ----------
  const invitacion = $derived(jam.sala ? null : jam.invitacion);
  let nombreAutomatico = false;
  async function aceptarInvitacion() {
    const datos = jam.invitacion;
    if (!datos) return;
    await intentar(() => unirseConDatos(datos, nombre.trim()));
    if (jam.sala) jam.invitacion = null;
  }
  // Si ya tienes nombre, entra solo; si no, se te pide primero
  $effect(() => {
    if (invitacion && nombre.trim() && !nombreAutomatico) {
      nombreAutomatico = true;
      untrack(aceptarInvitacion);
    }
  });

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
    if (!nombre.trim()) return aviso("Escribe tu nombre para que los demás sepan quién eres");
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
  const puedeAgregar = $derived(anfitrion || s?.invitados_agregan);
  let pos = $state(0);
  onMount(() => {
    const t = setInterval(() => (pos = posicionJam()), 500);
    return () => clearInterval(t);
  });
  const duracion = $derived(p?.duracion || 0);
  const pendientes = $derived(s ? s.cola.length - s.indice - 1 : 0);

  let pestana = $state("cola"); // cola | agregar | sala
  let fuente = $state("biblioteca");
  let q = $state("");
  let resultados = $state([]);
  let cargando = $state(false);
  let invitar = $state(false);
  let qr = $state(null);

  // ---------- Por internet (anfitrión en la PC) ----------
  let abriendo = $state(false);
  let pctCloudflared = $state(0);
  onMount(() => alEvento("jam_internet", ({ pct }) => (pctCloudflared = pct)));

  async function alternarInternet() {
    abriendo = true;
    pctCloudflared = 0;
    try {
      const url = await abrirInternet(!jam.conexion.internet);
      qr = await qrDelJam(); // el QR ahora lleva (o ya no) la dirección pública
      if (url) aviso("Tu jam ya se puede abrir desde cualquier lugar", "ok");
    } catch (err) {
      aviso(err.message || "No se pudo abrir a internet", "error");
    } finally {
      abriendo = false;
    }
  }

  async function abrirInvitar() {
    invitar = true;
    if (!qr) {
      try {
        qr = await qrDelJam();
      } catch {
        aviso("No se pudo generar el QR", "error");
      }
    }
  }

  let pedido = 0; // solo vale la respuesta de lo último que escribiste
  let espera = null;
  async function cargarResultados() {
    const yo = ++pedido;
    const texto = q.trim();
    // Solo se muestra el esqueleto si no hay nada en pantalla: al escribir, lo anterior se queda hasta que llega lo nuevo
    if (!resultados.length) cargando = true;
    try {
      let lista;
      if (fuente === "mias") lista = (await py("biblioteca", { q: texto })).canciones;
      else if (fuente === "biblioteca") lista = (await bibliotecaAnfitrion(texto)).canciones;
      else lista = texto ? (await buscarEnAnfitrion(texto)).canciones : [];
      if (yo === pedido) resultados = lista;
    } catch (err) {
      if (yo === pedido) aviso(err.message, "error");
    } finally {
      if (yo === pedido) cargando = false;
    }
  }
  /** Resultados mientras escribes: lo local casi al instante, YouTube Music cuando paras de teclear. */
  function alEscribir() {
    clearTimeout(espera);
    espera = setTimeout(cargarResultados, fuente === "buscar" ? 400 : 150);
  }
  $effect(() => {
    if (pestana !== "agregar") return;
    fuente;
    untrack(() => {
      resultados = [];
      cargarResultados();
    });
  });
  $effect(() => { if (pestana === "agregar" && !puedeAgregar) pestana = "cola"; });

  let subiendo = $state(null);

  async function sumar(c) {
    try {
      if (fuente === "mias") {
        subiendo = c.ruta;
        if (!anfitrion) aviso(`Mandando “${c.titulo}” al anfitrión…`);
        await agregarPropia(c);
        aviso(`“${c.titulo}” a la cola`, "ok");
      } else {
        await agregar(c);
        aviso(`“${c.titulo}” a la cola`, "ok");
      }
    } catch (err) {
      aviso(err.message, "error");
    } finally {
      subiendo = null;
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
    <div class="lobby" in:fade={{ duration: 220 }}>
      <header class="hero">
        <span class="sello"><Icono nombre="jam" tam={30} /></span>
        <div>
          <h1 class="titulo-vista">Jams</h1>
          <p class="tenue">Escuchen juntos en la misma red: todos arman la cola y suena sincronizado.</p>
        </div>
      </header>

      {#if invitacion}
        <section class="invitacion" in:scale={{ duration: 220, start: 0.96 }}>
          <span class="sello"><Icono nombre="jam" tam={26} /></span>
          <div class="invitacion-texto">
            <small>TE INVITARON A UN JAM</small>
            <b class="cortar">{invitacion.nombre || "Jam de Misiccord"}</b>
            <span class="tenue">{ocupado ? "Conectando…" : invitacion.url ? "Por internet o en tu red" : "En tu red Wi-Fi"}</span>
          </div>
          <div class="invitacion-acciones">
            <button class="pildora cian" disabled={ocupado || !nombre.trim()} onclick={aceptarInvitacion}>{ocupado ? "…" : "Unirme"}</button>
            <button class="ignorar" onclick={() => (jam.invitacion = null)} aria-label="Ignorar invitación"><Icono nombre="cerrar" tam={18} /></button>
          </div>
          {#if !nombre.trim()}<p class="pide-nombre">Escribe tu nombre abajo y toca <b>Unirme</b>.</p>{/if}
        </section>
      {/if}

      <label class="yo">
        <span class="avatar">{nombre.trim() ? iniciales(nombre.trim()) : "?"}</span>
        <span class="yo-campo">
          <small>Tu nombre en el jam</small>
          <input bind:value={nombre} placeholder="¿Cómo te ven los demás?" maxlength="30" />
        </span>
      </label>

      {#if !ui.amplio}
        <div class="pestanas" role="tablist">
          <button class:activa={paso === "crear"} onclick={() => (paso = "crear")}>Crear</button>
          <button class:activa={paso === "unirme"} onclick={() => (paso = "unirme")}>Unirme</button>
        </div>
      {/if}

      <div class="columnas">
        {#if ui.amplio || paso === "crear"}
          <section class="panel" in:fade={{ duration: 180 }}>
            <h2>Crear un jam</h2>
            <p class="tenue sub">Tú eres el anfitrión: controlas la música y los demás se unen con un código.</p>
            <div class="modos">
              <button class:activo={modo === "sincronizado"} onclick={() => (modo = "sincronizado")}>
                <span class="radio"></span>
                <span><b>Sincronizado</b><small>Suena en todos los dispositivos al mismo tiempo</small></span>
              </button>
              <button class:activo={modo === "anfitrion"} onclick={() => (modo = "anfitrion")}>
                <span class="radio"></span>
                <span><b>Solo aquí</b><small>Suena en este dispositivo, ideal con una bocina</small></span>
              </button>
            </div>
            <button class="pildora cian ancho" disabled={ocupado} onclick={() => { creando = true; intentar(() => crear(nombre.trim(), modo)).finally(() => (creando = false)); }}>
              <Icono nombre="jam" tam={20} /> {creando ? "Abriendo…" : "Crear jam"}
            </button>
          </section>
        {/if}

        {#if ui.amplio || paso === "unirme"}
          <section class="panel" in:fade={{ duration: 180 }}>
            <h2>Unirme a un jam</h2>
            {#if esCelular}
              <button class="escanear" disabled={ocupado} onclick={escanear}>
                <span class="icono-qr"><Icono nombre="camara" tam={26} /></span>
                <span><b>Escanear QR</b><small>Apunta al código que muestra el anfitrión</small></span>
              </button>
            {/if}

            <div class="sub-cab">
              <span>Cerca de ti</span>
              <button class="buscar-otra" onclick={buscar} disabled={cercanos === null}>
                {cercanos === null ? "Buscando…" : "Buscar de nuevo"}
              </button>
            </div>
            {#if cercanos === null}
              <div class="cargando-bloque" style="height:62px"></div>
            {:else if !cercanos.length}
              <p class="tenue nota">No encontré jams en tu red. Pide el QR o el código al anfitrión.</p>
            {:else}
              {#each cercanos as j}
                <div class="cercano" class:elegido={elegido === j}>
                  <button class="cercano-fila" onclick={() => { elegido = elegido === j ? null : j; codigo = ""; }}>
                    <span class="avatar vivo"><Icono nombre="jam" tam={20} /></span>
                    <span class="textos"><b class="cortar">{j.nombre}</b><small>{j.ip}</small></span>
                    <Icono nombre={elegido === j ? "cerrar" : "agregar"} tam={20} />
                  </button>
                  {#if elegido === j}
                    <form class="linea" transition:slide={{ duration: 200 }}
                      onsubmit={(ev) => { ev.preventDefault(); intentar(() => unirse(j.ip, j.puerto, codigo, nombre.trim())); }}>
                      <input class="pin" bind:value={codigo} placeholder="Código" inputmode="numeric" maxlength="4" />
                      <button class="pildora cian" disabled={ocupado || codigo.length !== 4}>Entrar</button>
                    </form>
                  {/if}
                </div>
              {/each}
            {/if}

            <button class="otras" onclick={() => (otrasFormas = !otrasFormas)}>
              Otras formas de unirme <Icono nombre={otrasFormas ? "cerrar" : "agregar"} tam={16} />
            </button>
            {#if otrasFormas}
              <div class="otras-cuerpo" transition:slide={{ duration: 200 }}>
                <form class="linea" onsubmit={(ev) => { ev.preventDefault(); unirseConLink(link); }}>
                  <input bind:value={link} placeholder="Pega el link del jam" />
                  <button class="pildora oscura" disabled={ocupado || !link.trim()}>Entrar</button>
                </form>
                <form class="manual" onsubmit={(ev) => { ev.preventDefault(); intentar(() => unirse(manual.ip.trim(), manual.puerto, manual.codigo, nombre.trim())); }}>
                  <input bind:value={manual.ip} placeholder="IP del anfitrión (ej. 192.168.1.14)" />
                  <input bind:value={manual.puerto} placeholder="Puerto" inputmode="numeric" />
                  <input bind:value={manual.codigo} placeholder="Código" inputmode="numeric" maxlength="4" />
                  <button class="pildora oscura" disabled={ocupado}>Entrar</button>
                </form>
              </div>
            {/if}
          </section>
        {/if}
      </div>
    </div>
  {:else}
    <!-- ---------- La sala ---------- -->
    <div class="sala" in:fade={{ duration: 250 }}>
      <header class="sala-cab">
        <div class="sala-titulo">
          <small class="envivo" class:caido={!jam.conectado}><i></i> {jam.conectado ? "EN VIVO" : "RECONECTANDO…"}</small>
          <h1 class="cortar">{s.nombre}</h1>
          <button class="gente" onclick={() => (pestana = "sala")}>
            <span class="caras">
              {#each s.participantes.slice(0, 4) as persona}<span class="avatar mini">{iniciales(persona.nombre)}</span>{/each}
            </span>
            {s.participantes.length} {s.participantes.length === 1 ? "persona" : "personas"} · {s.modo === "sincronizado" ? "sincronizado" : "suena en el anfitrión"}
          </button>
        </div>
        {#if anfitrion}
          <button class="pildora cian invitar" onclick={abrirInvitar}><Icono nombre="qr" tam={20} /> Invitar</button>
        {/if}
      </header>

      <div class="sala-cuerpo">
        <!-- Lo que suena -->
        <section class="ahora">
          {#if p}
            <div class="ambiente" style:background-image={p.portada ? `url("${urlJam(p.portada)}")` : "none"}></div>
          {/if}
          <div class="ahora-contenido">
            {#if p}
              <div class="tapa">
                <Portada url={urlJam(p.portada)} radio="16px" sombra />
                {#each flotando as r (r.ms)}
                  <span class="flota" style:left="{(r.ms % 70) + 10}%">{r.emoji}</span>
                {/each}
              </div>
              <div class="ahora-info">
                <h2 class="cortar">{p.titulo}</h2>
                <p class="cortar">{p.artista} · la puso <b>{p.agregada_por}</b></p>
              </div>
              <div class="progreso"><div style:width="{duracion ? Math.min(100, (pos / duracion) * 100) : 0}%"></div></div>
              <div class="tiempos"><span>{tiempo(pos)}</span><span>{tiempo(duracion)}</span></div>
            {:else}
              <div class="sin-pista">
                <span class="sello"><Icono nombre="nota" tam={34} /></span>
                <b>La cola está vacía</b>
                {#if puedeAgregar}
                  <button class="pildora cian" onclick={() => (pestana = "agregar")}><Icono nombre="agregar" tam={18} /> Agregar la primera</button>
                {:else}
                  <p>Espera a que el anfitrión ponga algo.</p>
                {/if}
              </div>
            {/if}

            <div class="controles">
              {#if anfitrion}
                <button class="redondo grande" onclick={() => control("anterior")} aria-label="Anterior"><Icono nombre="anterior" relleno tam={30} /></button>
                <button class="play" onclick={() => control(s.sonando ? "pausa" : "play")} aria-label="Reproducir o pausar">
                  <Icono nombre={s.sonando ? "pausa" : "play"} relleno tam={32} />
                </button>
                <button class="redondo grande" onclick={() => control("siguiente")} aria-label="Siguiente"><Icono nombre="siguiente" relleno tam={30} /></button>
              {:else if p}
                <button class="pildora clara" onclick={() => votar().then(() => aviso("Votaste para saltar"))}>
                  <Icono nombre="siguiente" relleno tam={18} /> Saltar · {s.votos}/{s.votos_necesarios}
                </button>
              {/if}
            </div>
            <div class="emojis">
              {#each emojis as em}<button onclick={() => reaccionar(em)} aria-label="Reaccionar {em}">{em}</button>{/each}
            </div>
            {#if jam.escuchando && (s.modo === "sincronizado" || anfitrion)}
              <div class="vol"><Volumen claro /></div>
            {/if}
          </div>
        </section>

        <!-- Cola / Agregar / Sala -->
        <section class="lado">
          <div class="pestanas" role="tablist">
            <button class:activa={pestana === "cola"} onclick={() => (pestana = "cola")}>
              Cola{#if pendientes > 0}<span class="cuenta">{pendientes}</span>{/if}
            </button>
            {#if puedeAgregar}
              <button class:activa={pestana === "agregar"} onclick={() => (pestana = "agregar")}>Agregar</button>
            {/if}
            <button class:activa={pestana === "sala"} onclick={() => (pestana = "sala")}>Sala</button>
          </div>

          {#if pestana === "cola"}
            <div class="lista" in:fade={{ duration: 160 }}>
              {#each s.cola as pista, i (pista.pid)}
                <div class="pista" class:actual={i === s.indice} class:pasada={i < s.indice} transition:slide={{ duration: 200 }}>
                  <div class="pista-tapa">
                    <Portada url={urlJam(pista.portada)} tam="46px" radio="8px" />
                    {#if i === s.indice && s.sonando}<span class="ecualizador"><i></i><i></i><i></i></span>{/if}
                  </div>
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
              {:else}
                <p class="tenue nota centro">Todavía no hay canciones en la cola.</p>
              {/each}
            </div>
          {:else if pestana === "agregar"}
            <div in:fade={{ duration: 160 }}>
              <div class="fuentes">
                {#if !anfitrion}
                  <button class:activo={fuente === "mias"} onclick={() => (fuente = "mias")}>Mis canciones</button>
                {/if}
                <button class:activo={fuente === "biblioteca"} onclick={() => (fuente = "biblioteca")}>{anfitrion ? "Mi biblioteca" : "Del anfitrión"}</button>
                <button class:activo={fuente === "buscar"} onclick={() => (fuente = "buscar")}>YouTube Music</button>
              </div>
              <form class="buscador" onsubmit={(ev) => { ev.preventDefault(); cargarResultados(); }}>
                <Icono nombre="buscar" tam={18} />
                <input bind:value={q} oninput={alEscribir} placeholder={fuente === "buscar" ? "Buscar canción o artista…" : "Filtrar canciones…"} />
              </form>
              {#if cargando}
                {#each Array(4) as _}<div class="cargando-bloque" style="height:52px;margin:8px 0"></div>{/each}
              {:else}
                <div class="lista">
                  {#each resultados.slice(0, 40) as c}
                    <div class="resultado">
                      <Portada url={fuente === "mias" || !c.local ? c.portada : null} tam="44px" radio="8px" />
                      <span class="textos"><b class="cortar">{c.titulo}</b><small class="cortar">{c.artista}</small></span>
                      <button class="sumar" disabled={subiendo === c.ruta} onclick={() => sumar(c)}
                        aria-label={fuente === "mias" && !anfitrion ? "Mandar al jam" : "Agregar a la cola"}>
                        {#if subiendo === c.ruta}<span class="girando"></span>
                        {:else}<Icono nombre={fuente === "mias" && !anfitrion ? "subir" : "agregar"} tam={20} />{/if}
                      </button>
                    </div>
                  {:else}
                    <p class="tenue nota centro">{fuente === "buscar" && !q.trim() ? "Escribe qué quieres escuchar." : "Sin resultados."}</p>
                  {/each}
                </div>
              {/if}
            </div>
          {:else}
            <div in:fade={{ duration: 160 }}>
              <div class="grupo">
                {#if anfitrion}
                  <div class="ajuste">
                    <span>Dónde suena</span>
                    <div class="fuentes compacto">
                      <button class:activo={s.modo === "sincronizado"} onclick={() => control("modo", { modo: "sincronizado" })}>En todos</button>
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
              </div>

              <div class="sub-cab"><span>En el jam</span></div>
              <div class="grupo">
                {#each s.participantes as persona}
                  <div class="persona">
                    <span class="avatar" class:anfi={persona.rol === "anfitrion"}>{iniciales(persona.nombre)}</span>
                    <span class="textos"><b class="cortar">{persona.nombre}</b>{#if persona.rol === "anfitrion"}<small>Anfitrión</small>{/if}</span>
                    {#if anfitrion && persona.rol !== "anfitrion"}
                      <button class="sacar" onclick={() => control("expulsar", { cliente_corto: persona.cliente })}>Sacar</button>
                    {/if}
                  </div>
                {/each}
              </div>

              <button class="salir" onclick={salir}>{anfitrion ? "Terminar jam" : "Salir del jam"}</button>
            </div>
          {/if}
        </section>
      </div>
    </div>
  {/if}
</div>

{#if invitar && s && anfitrion}
  <div class="fondo-modal" use:aBody transition:fade={{ duration: 180 }} onclick={() => (invitar = false)} role="presentation"></div>
  <div class="modal" use:aBody transition:scale={{ duration: 220, start: 0.94 }} role="dialog" aria-label="Invitar al jam">
    <button class="redondo cerrar-modal" onclick={() => (invitar = false)} aria-label="Cerrar"><Icono nombre="cerrar" tam={22} /></button>
    <h2>Invita a tus amigos</h2>
    <p class="tenue">Escanean este QR desde <b>Jams → Unirme</b> en su Misiccord</p>
    <div class="qr-imagen">
      {#if qr}{@html qr.svg}{:else}<div class="cargando-bloque" style="aspect-ratio:1"></div>{/if}
    </div>
    <div class="datos">
      <div><small>CÓDIGO</small><b class="codigo-grande">{jam.conexion.codigo}</b></div>
      <div>
        <small>{jam.conexion.internet ? "INTERNET" : "DIRECCIÓN"}</small>
        <b>{jam.conexion.internet ? jam.conexion.internet.replace("https://", "") : `${jam.conexion.ips?.[0]}:${jam.conexion.puerto}`}</b>
      </div>
    </div>
    {#if jam.conexion.internetDisponible}
      <div class="internet" class:activo={jam.conexion.internet}>
        <div class="internet-texto">
          <b><Icono nombre="jam" tam={18} /> {jam.conexion.internet ? "Abierto a internet" : "Solo en tu red"}</b>
          <small>
            {#if abriendo}{pctCloudflared && pctCloudflared < 100 ? `Preparando la conexión (solo la primera vez)… ${pctCloudflared}%` : "Abriendo la conexión…"}
            {:else if jam.conexion.internet}Pueden unirse desde otra red con el QR o el link. La dirección cambia cada vez.
            {:else}Para amigos que no están en tu Wi-Fi: el QR y el link funcionarán desde cualquier lugar.{/if}
          </small>
        </div>
        <button class="pildora chica {jam.conexion.internet ? 'oscura' : 'cian'}" disabled={abriendo} onclick={alternarInternet}>
          {abriendo ? "…" : jam.conexion.internet ? "Cerrar" : "Abrir"}
        </button>
      </div>
    {/if}
    {#if qr}
      <button class="pildora oscura ancho" onclick={() => copiar(qr.texto).then((ok) => aviso(ok ? "Link copiado: mándalo por WhatsApp o donde quieras" : "No se pudo copiar", ok ? "ok" : "error"))}>Copiar link</button>
    {/if}
  </div>
{/if}

<style>
  .vista { padding: calc(var(--seguro-arriba) + 14px) var(--margen) 0; }
  input:not([type="checkbox"]) {
    height: 48px; border-radius: 12px; border: 1px solid var(--borde-fuerte); background: var(--fondo);
    padding: 0 14px; outline: 0; width: 100%; min-width: 0;
  }
  input:focus { border-color: var(--cian); }
  .ancho { width: 100%; }
  .nota { font-size: 14px; line-height: 1.5; margin: 10px 0; }
  .centro { text-align: center; padding: 24px 0; }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
  .textos small { color: var(--tenue); font-size: 13px; }
  .avatar {
    width: 44px; height: 44px; border-radius: 50%; background: var(--tarjeta-2); display: grid; place-items: center;
    font-weight: 800; flex-shrink: 0; color: var(--texto); font-size: 15px;
  }
  .avatar.vivo { color: var(--verde); background: rgba(74, 222, 128, 0.12); }
  .avatar.anfi { background: var(--cian); color: #04121a; }
  .sello { width: 58px; height: 58px; border-radius: 18px; display: grid; place-items: center; flex-shrink: 0; color: #04121a; background: linear-gradient(135deg, var(--cian), #a78bfa); }

  /* Pestañas tipo segmento (lobby en el cel y lado derecho de la sala) */
  .pestanas { display: flex; gap: 4px; padding: 4px; border-radius: 14px; background: var(--tarjeta); margin-bottom: 14px; }
  .pestanas button { flex: 1; height: 40px; border-radius: 10px; font-weight: 700; font-size: 15px; color: var(--tenue); display: flex; align-items: center; justify-content: center; gap: 6px; transition: background 0.2s, color 0.2s; }
  .pestanas .activa { background: var(--texto); color: #04121a; }
  .cuenta { min-width: 20px; height: 20px; padding: 0 6px; border-radius: 10px; background: var(--cian); color: #04121a; font-size: 12px; display: grid; place-items: center; }

  /* ---------- Lobby ---------- */
  .lobby { max-width: 980px; margin: 0 auto; }
  .hero { display: flex; align-items: center; gap: 16px; }
  .hero p { margin: 4px 0 0; line-height: 1.45; font-size: 14.5px; }
  .invitacion {
    display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 14px; margin-top: 18px;
    padding: 16px; border-radius: 20px; border: 1px solid rgba(34, 211, 238, 0.4);
    background: linear-gradient(135deg, rgba(34, 211, 238, 0.16), rgba(167, 139, 250, 0.14));
  }
  .invitacion .sello { width: 50px; height: 50px; border-radius: 15px; }
  .invitacion-texto { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .invitacion-texto small { font-size: 11px; font-weight: 800; letter-spacing: 1.3px; color: var(--cian); }
  .invitacion-texto b { font-size: 18px; }
  .invitacion-texto span { font-size: 13px; }
  .invitacion-acciones { display: flex; align-items: center; gap: 4px; }
  .invitacion-acciones .pildora { height: 42px; padding: 0 18px; }
  .ignorar { width: 34px; height: 34px; display: grid; place-items: center; color: var(--tenue); }
  .pide-nombre { grid-column: 1 / -1; margin: 0; font-size: 13.5px; color: var(--tenue); }
  .yo { display: flex; align-items: center; gap: 12px; margin: 20px 0 16px; padding: 10px 14px 10px 10px; border-radius: 18px; background: var(--tarjeta); border: 1px solid var(--borde); }
  .yo-campo { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .yo-campo small { font-size: 12px; color: var(--tenue); font-weight: 600; padding-left: 2px; }
  .yo input { height: 32px; border: 0; background: transparent; padding: 0 2px; font-size: 17px; font-weight: 700; }
  .columnas { display: grid; gap: 16px; align-items: start; }
  .panel { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 20px; padding: 18px; min-width: 0; }
  .panel h2 { margin: 0; font-size: 19px; font-weight: 800; }
  .sub { font-size: 14px; line-height: 1.45; margin: 6px 0 14px; }
  .modos { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
  .modos button { display: flex; align-items: center; gap: 14px; text-align: left; padding: 14px; border-radius: 14px; border: 1.5px solid var(--borde-fuerte); transition: border-color 0.2s, background 0.2s; }
  .modos button > span:last-child { display: flex; flex-direction: column; gap: 2px; }
  .modos small { color: var(--tenue); font-size: 13px; line-height: 1.35; }
  .modos .activo { border-color: var(--cian); background: rgba(34, 211, 238, 0.08); }
  .radio { width: 22px; height: 22px; border-radius: 50%; border: 2px solid var(--borde-fuerte); flex-shrink: 0; transition: border 0.2s; }
  .activo .radio { border: 7px solid var(--cian); }
  .escanear { width: 100%; display: flex; align-items: center; gap: 14px; text-align: left; margin-top: 14px; padding: 14px; border-radius: 16px; background: linear-gradient(135deg, rgba(34, 211, 238, 0.18), rgba(167, 139, 250, 0.16)); border: 1px solid rgba(34, 211, 238, 0.35); }
  .escanear > span:last-child { display: flex; flex-direction: column; gap: 2px; }
  .escanear small { color: var(--tenue); font-size: 13px; }
  .icono-qr { width: 50px; height: 50px; border-radius: 14px; background: var(--cian); color: #04121a; display: grid; place-items: center; flex-shrink: 0; }
  .sub-cab { display: flex; justify-content: space-between; align-items: center; margin: 18px 0 8px; font-size: 13px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--tenue); }
  .buscar-otra { color: var(--cian); font-weight: 600; font-size: 13.5px; text-transform: none; letter-spacing: 0; }
  .cercano { border-radius: 14px; transition: background 0.2s; }
  .cercano.elegido { background: var(--tarjeta-2); padding-bottom: 10px; }
  .cercano-fila { width: 100%; display: flex; align-items: center; gap: 12px; padding: 8px; text-align: left; color: var(--tenue); }
  .cercano-fila b { color: var(--texto); }
  .linea { display: flex; gap: 10px; }
  .cercano .linea { padding: 0 10px; }
  .pin { text-align: center; letter-spacing: 8px; font-size: 20px; font-weight: 800; }
  .otras { display: flex; align-items: center; justify-content: space-between; width: 100%; margin-top: 16px; padding: 12px 0 4px; border-top: 1px solid var(--borde); color: var(--tenue); font-weight: 600; font-size: 14.5px; }
  .otras-cuerpo { display: flex; flex-direction: column; gap: 12px; padding-top: 10px; }
  .manual { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; }
  .manual input:first-child { grid-column: 1 / -1; }
  .manual button { grid-column: 1 / -1; }

  /* ---------- Sala ---------- */
  .sala-cab { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; }
  .sala-titulo { min-width: 0; }
  .sala-cab h1 { margin: 2px 0 4px; font-size: 26px; font-weight: 800; letter-spacing: -0.4px; }
  .envivo { display: flex; align-items: center; gap: 6px; color: var(--verde); font-weight: 800; letter-spacing: 1.5px; font-size: 11px; }
  .envivo.caido { color: var(--tenue); }
  .envivo i { width: 8px; height: 8px; border-radius: 50%; background: currentColor; animation: latido 1.4s infinite; }
  @keyframes latido { 50% { opacity: 0.3; } }
  .gente { display: flex; align-items: center; gap: 8px; color: var(--tenue); font-size: 13.5px; text-align: left; }
  .caras { display: flex; }
  .avatar.mini { width: 24px; height: 24px; font-size: 10px; border: 2px solid var(--fondo); margin-left: -6px; }
  .avatar.mini:first-child { margin-left: 0; }
  .invitar { flex-shrink: 0; height: 44px; padding: 0 18px; }

  .sala-cuerpo { display: grid; gap: 18px; }
  .ahora { position: relative; overflow: hidden; border-radius: 24px; background: var(--tarjeta); isolation: isolate; }
  .ambiente {
    position: absolute; inset: -30%; z-index: -1; background-size: cover; background-position: center;
    filter: blur(60px) saturate(1.4) brightness(0.45);
  }
  .ahora-contenido { padding: 20px 18px 18px; text-align: center; }
  .tapa { position: relative; width: min(58vw, 260px); margin: 0 auto 16px; }
  .flota { position: absolute; bottom: 10%; font-size: 34px; animation: subir 4s ease-out forwards; pointer-events: none; }
  @keyframes subir { from { transform: translateY(0) scale(0.6); opacity: 0; } 15% { opacity: 1; transform: translateY(-20px) scale(1.1); } to { transform: translateY(-220px) scale(1); opacity: 0; } }
  .ahora h2 { margin: 0; font-size: 21px; font-weight: 800; }
  .ahora-info p { margin: 4px 0 14px; color: rgba(255, 255, 255, 0.72); font-size: 14.5px; }
  .progreso { height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 0.2); overflow: hidden; }
  .progreso div { height: 100%; background: #fff; transition: width 0.5s linear; }
  .tiempos { display: flex; justify-content: space-between; font-size: 12.5px; color: rgba(255, 255, 255, 0.7); margin-top: 6px; font-variant-numeric: tabular-nums; }
  .controles { display: flex; justify-content: center; align-items: center; gap: 22px; margin: 12px 0 12px; min-height: 8px; }
  .grande { width: 54px; height: 54px; }
  .play { width: 66px; height: 66px; border-radius: 50%; background: #fff; color: #04121a; display: grid; place-items: center; transition: transform 0.15s var(--curva); }
  .play:active { transform: scale(0.92); }
  .emojis { display: flex; justify-content: center; gap: 6px; flex-wrap: wrap; }
  .emojis button { font-size: 22px; width: 44px; height: 44px; border-radius: 50%; background: rgba(255, 255, 255, 0.09); transition: transform 0.15s var(--curva); }
  .emojis button:active { transform: scale(1.3); }
  .vol { max-width: 340px; margin: 14px auto 0; }
  .sin-pista { padding: 18px 0 4px; color: var(--tenue); display: grid; justify-items: center; gap: 12px; }
  .sin-pista b { color: var(--texto); font-size: 17px; }
  .sin-pista p { margin: 0; }

  .lado { min-width: 0; }
  .lista { display: flex; flex-direction: column; }
  .resultado, .pista { display: flex; align-items: center; gap: 12px; padding: 7px 8px; border-radius: 12px; }
  .pista.actual { background: var(--tarjeta); }
  .pista.actual b { color: var(--cian); }
  .pista.pasada { opacity: 0.45; }
  .pista-tapa { position: relative; flex-shrink: 0; }
  .ecualizador { position: absolute; inset: 0; border-radius: 8px; background: rgba(0, 0, 0, 0.55); display: flex; align-items: flex-end; justify-content: center; gap: 3px; padding-bottom: 12px; }
  .ecualizador i { width: 4px; border-radius: 2px; background: var(--cian); animation: barra 0.9s infinite ease-in-out; }
  .ecualizador i:nth-child(2) { animation-delay: -0.3s; }
  .ecualizador i:nth-child(3) { animation-delay: -0.6s; }
  @keyframes barra { 0%, 100% { height: 6px; } 50% { height: 20px; } }
  .fuentes { display: flex; gap: 6px; flex-wrap: wrap; }
  .fuentes button { padding: 8px 14px; border-radius: 999px; background: var(--tarjeta-2); font-weight: 600; font-size: 14px; }
  .fuentes .activo { background: var(--texto); color: #04121a; }
  .fuentes.compacto button { padding: 6px 12px; font-size: 13px; }
  .buscador { display: flex; align-items: center; gap: 8px; margin: 12px 0 6px; padding-left: 14px; border-radius: 12px; background: var(--tarjeta); color: var(--tenue); }
  .buscador input { border: 0; background: transparent; }
  .sumar { width: 40px; height: 40px; border-radius: 50%; background: var(--tarjeta-2); color: var(--cian); display: grid; place-items: center; flex-shrink: 0; }
  .sumar:active { transform: scale(0.9); }
  .girando { width: 20px; height: 20px; border-radius: 50%; border: 2.5px solid var(--borde-fuerte); border-top-color: var(--cian); animation: giro 0.8s linear infinite; }
  @keyframes giro { to { transform: rotate(360deg); } }
  .grupo { background: var(--tarjeta); border-radius: 16px; padding: 4px 14px; }
  .ajuste { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--borde); }
  .ajuste:last-child { border-bottom: 0; }
  .interruptor { -webkit-appearance: none; appearance: none; width: 50px; height: 30px; border-radius: 15px; background: var(--borde-fuerte); position: relative; flex-shrink: 0; transition: background 0.25s; }
  .interruptor::after { content: ""; position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; border-radius: 50%; background: #fff; transition: transform 0.25s var(--curva); }
  .interruptor:checked { background: var(--cian); }
  .interruptor:checked::after { transform: translateX(20px); }
  .persona { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--borde); }
  .persona:last-child { border-bottom: 0; }
  .persona .avatar { width: 38px; height: 38px; font-size: 13px; }
  .sacar { color: var(--rojo); font-weight: 600; font-size: 14px; }
  .salir { display: block; width: 100%; margin: 20px 0 8px; height: 48px; border-radius: 14px; border: 1px solid rgba(248, 113, 113, 0.35); color: var(--rojo); font-weight: 700; }

  /* ---------- Invitar ---------- */
  .fondo-modal { position: fixed; inset: 0; z-index: 300; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); }
  .modal {
    position: fixed; z-index: 301; left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: min(380px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto;
    background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 24px; padding: 22px 20px 20px; text-align: center;
  }
  .modal h2 { margin: 0; font-size: 21px; font-weight: 800; }
  .modal p { margin: 6px 0 16px; font-size: 14px; line-height: 1.45; }
  .cerrar-modal { position: absolute; top: 10px; right: 10px; }
  .qr-imagen { width: min(230px, 62vw); margin: 0 auto; background: #fff; border-radius: 16px; padding: 10px; }
  .qr-imagen :global(svg) { width: 100%; height: auto; display: block; }
  .datos { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; margin: 16px 0; text-align: left; }
  .datos > div { background: var(--fondo); border-radius: 14px; padding: 10px 14px; display: flex; flex-direction: column; min-width: 0; }
  .datos small { font-size: 11px; letter-spacing: 1.5px; color: var(--tenue); }
  .datos b { overflow-wrap: anywhere; }
  .internet { display: flex; align-items: center; gap: 12px; text-align: left; margin: 0 0 14px; padding: 12px 14px; border-radius: 14px; background: var(--fondo); border: 1px solid var(--borde); }
  .internet.activo { border-color: rgba(74, 222, 128, 0.45); background: rgba(74, 222, 128, 0.07); }
  .internet-texto { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .internet-texto b { display: flex; align-items: center; gap: 6px; font-size: 14.5px; }
  .internet.activo b { color: var(--verde); }
  .internet-texto small { color: var(--tenue); font-size: 12.5px; line-height: 1.4; }
  .chica { height: 38px; padding: 0 16px; font-size: 14px; flex-shrink: 0; }
  .codigo-grande { font-size: 24px; letter-spacing: 5px; color: var(--cian); }

  /* ---------- Escritorio ---------- */
  @media (min-width: 900px) {
    .columnas { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; }
    .panel { padding: 24px; }
    .yo { max-width: 460px; }
    .sala-cuerpo { grid-template-columns: minmax(320px, 400px) minmax(0, 1fr); gap: 28px; align-items: start; }
    .ahora { position: sticky; top: 20px; }
    .tapa { width: 100%; max-width: 300px; }
  }
</style>
