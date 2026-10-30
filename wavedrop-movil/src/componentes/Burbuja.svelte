<script>
  import { onMount } from "svelte";
  import { emitTo, listen } from "@tauri-apps/api/event";
  import { invoke } from "@tauri-apps/api/core";
  import { currentMonitor, getCurrentWindow } from "@tauri-apps/api/window";
  import { t } from "../lib/idioma.svelte.js";
  import Icono from "./Icono.svelte";

  // La burbuja flotante del escritorio: es su propia ventana (ver `burbuja` en src-tauri/src/lib.rs).
  // Cerrada es un círculo con la portada y el avance alrededor; al pasar el mouse crece a una píldora con controles.
  // No reproduce nada: la ventana principal le manda lo que suena ("burbuja-estado") y ella le manda órdenes ("burbuja-control").
  //
  // Para que abrir se sienta inmediato y suave, la ventana crece de golpe (lo de más es transparente) y la píldora se
  // estira con una transición de CSS; al cerrar es al revés: primero se encoge la píldora y luego la ventana.
  const TAM = 64;
  const ANCHO = 336;
  const ANIMACION = 220; // ms, igual que la transición del CSS
  const CLAVE = "misiccord_burbuja_posicion"; // dónde la dejaste (en px lógicos, el círculo cerrado)

  const ventana = getCurrentWindow();
  let estado = $state({ hay: false, titulo: "", artista: "", portada: null, sonando: false, pos: 0, dur: 0 });
  let abierta = $state(false);
  let haciaIzquierda = $state(false); // crece hacia la izquierda si a la derecha no cabe
  let grande = false; // la ventana ya tiene el tamaño de la píldora
  let origen = { x: 0, y: 0 }; // posición del círculo cerrado
  let monitor = null; // se lee al arrancar y al soltarla: preguntarlo al pasar el mouse metía retraso
  let moviendo = false; // los cambios de tamaño propios también disparan onMoved
  let colocada = false; // al crearse, Windows avisa que se movió a donde nació: eso no es una posición tuya
  let espera;

  const avance = $derived(estado.dur ? Math.min(1, estado.pos / estado.dur) : 0);
  const R = 30; // radio del anillo de avance
  const vuelta = 2 * Math.PI * R;

  function mandar(accion) {
    emitTo("main", "burbuja-control", { accion }).catch(() => {});
  }

  async function leerMonitor() {
    const m = await currentMonitor();
    if (!m) return;
    const area = m.workArea ?? m; // sin la barra de tareas, si el sistema la da
    const f = m.scaleFactor;
    monitor = { x: area.position.x / f, y: area.position.y / f, ancho: area.size.width / f, alto: area.size.height / f };
  }

  function marco(x, ancho) {
    moviendo = true;
    clearTimeout(marco.t);
    marco.t = setTimeout(() => (moviendo = false), 250);
    return invoke("burbuja", { accion: "marco", x, y: origen.y, ancho });
  }

  async function abrir() {
    clearTimeout(espera);
    if (abierta) return;
    if (!grande) {
      haciaIzquierda = !!monitor && origen.x + ANCHO > monitor.x + monitor.ancho;
      grande = true;
      await marco(haciaIzquierda ? origen.x + TAM - ANCHO : origen.x, ANCHO);
    }
    abierta = true;
  }

  async function cerrar() {
    // Solo si de verdad saliste: WebView2 a veces avisa "salió" con el cursor encima (al darle el primer clic, por ejemplo)
    // Si sigue encima se vuelve a revisar: al salir después ya no llegaría otro aviso
    if (await invoke("burbuja", { accion: "dentro" }).catch(() => false)) {
      clearTimeout(espera);
      espera = setTimeout(cerrar, 500);
      return;
    }
    abierta = false;
    clearTimeout(espera);
    espera = setTimeout(() => {
      if (abierta || !grande) return;
      grande = false;
      marco(origen.x, TAM);
    }, ANIMACION + 20);
  }

  // Pasar el mouse la abre al momento; salir la cierra con un respiro (para poder ir de un botón a otro)
  function entrar() {
    clearTimeout(espera);
    abrir();
  }
  function salir() {
    clearTimeout(espera);
    espera = setTimeout(cerrar, 350);
  }

  // Arrastrar desde la portada o el fondo mueve la ventana; un clic sin moverse abre la app
  let inicio = null;
  function bajar(e) {
    if (e.button !== 0 || e.target.closest("button")) return;
    inicio = { x: e.screenX, y: e.screenY };
  }
  function mover(e) {
    if (!inicio) return;
    if (Math.hypot(e.screenX - inicio.x, e.screenY - inicio.y) > 4) {
      inicio = null;
      ventana.startDragging().catch(() => {});
    }
  }
  function subir(e) {
    if (!inicio) return;
    inicio = null;
    if (e.target.closest(".portada")) invoke("burbuja", { accion: "abrir" });
  }

  async function guardarPosicion() {
    if (moviendo || !colocada) return;
    const f = await ventana.scaleFactor();
    const p = (await ventana.outerPosition()).toLogical(f);
    origen = { x: grande && haciaIzquierda ? p.x + ANCHO - TAM : p.x, y: p.y };
    try { localStorage.setItem(CLAVE, JSON.stringify(origen)); } catch {}
    leerMonitor(); // pudo pasar a otra pantalla
  }

  onMount(() => {
    let guardado = null;
    try { guardado = JSON.parse(localStorage.getItem(CLAVE) || "null"); } catch {}
    (async () => {
      await leerMonitor();
      const p = monitor;
      const dentro = guardado && p && guardado.x >= p.x - TAM && guardado.x <= p.x + p.ancho && guardado.y >= p.y - TAM && guardado.y <= p.y + p.alto;
      // La primera vez: abajo a la derecha, arriba de la barra de tareas
      origen = dentro ? guardado : p ? { x: p.x + p.ancho - TAM - 24, y: p.y + p.alto - TAM - 24 } : { x: 40, y: 40 };
      await marco(origen.x, TAM);
      setTimeout(() => (colocada = true), 400);
    })();
    let movida;
    ventana.onMoved(() => {
      clearTimeout(movida);
      movida = setTimeout(guardarPosicion, 300);
    });
    const quitar = listen("burbuja-estado", ({ payload }) => (estado = payload));
    // Al esconderse (volviste a la app) se cierra en círculo de una vez
    listen("burbuja-oculta", () => {
      clearTimeout(espera);
      abierta = false;
      if (grande) {
        grande = false;
        marco(origen.x, TAM);
      }
    });
    mandar("listo"); // que la principal mande lo que suena ahora
    return () => quitar.then((f) => f());
  });
</script>

<!-- La píldora va pegada al lado del círculo: crece hacia la derecha o, si no cabe, hacia la izquierda -->
<div class="lienzo" class:izquierda={haciaIzquierda}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="burbuja" class:abierta onmouseenter={entrar} onmouseleave={salir} onmousedown={bajar} onmousemove={mover} onmouseup={subir}>
    <div class="portada" title={t("Abrir Misiccord")}>
      {#if estado.portada}
        <img src={estado.portada} alt="" draggable="false" />
      {:else}
        <span class="logo"><Icono nombre="nota" tam={26} /></span>
      {/if}
      <svg class="anillo" viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r={R} class="fondo-anillo" />
        <circle cx="32" cy="32" r={R} class="lleno" stroke-dasharray={vuelta} stroke-dashoffset={vuelta * (1 - avance)} />
      </svg>
      <span class="pausada" class:visible={estado.hay && !estado.sonando && !abierta}><Icono nombre="pausa" relleno tam={18} /></span>
    </div>
    <div class="resto" aria-hidden={!abierta}>
      <div class="textos">
        {#if estado.hay}
          <b class="cortar">{estado.titulo}</b>
          <small class="cortar">{estado.artista}</small>
        {:else}
          <b class="cortar">Misiccord</b>
          <small class="cortar">{t("No hay nada sonando")}</small>
        {/if}
      </div>
      <div class="controles">
        <button onclick={() => mandar("anterior")} disabled={!estado.hay} aria-label={t("Anterior")}><Icono nombre="anterior" relleno tam={18} /></button>
        <button class="play" onclick={() => mandar("alternar")} disabled={!estado.hay} aria-label={estado.sonando ? t("Pausar") : t("Reproducir")}>
          <Icono nombre={estado.sonando ? "pausa" : "play"} relleno tam={20} />
        </button>
        <button onclick={() => mandar("siguiente")} disabled={!estado.hay} aria-label={t("Siguiente")}><Icono nombre="siguiente" relleno tam={18} /></button>
        <button onclick={() => invoke("burbuja", { accion: "abrir" })} aria-label={t("Abrir Misiccord")} title={t("Abrir Misiccord")}>
          <Icono nombre="abrir" tam={17} />
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  :global(html), :global(body) { background: transparent !important; overflow: hidden; margin: 0; }
  .lienzo { position: fixed; inset: 0; }
  .burbuja {
    position: absolute; top: 0; left: 0; width: 64px; height: 64px; border-radius: 32px; display: flex; align-items: center;
    background: #111a22; color: #fff; user-select: none; -webkit-user-select: none; cursor: grab; overflow: hidden;
    box-sizing: border-box; border: 1px solid rgba(255, 255, 255, 0.1);
    transition: width 220ms cubic-bezier(0.22, 1, 0.36, 1);
  }
  /* Hacia la izquierda: pegada a la derecha de la ventana, con el círculo a la derecha */
  .izquierda .burbuja { left: auto; right: 0; flex-direction: row-reverse; }
  .burbuja.abierta { width: 336px; }
  .portada { position: relative; width: 62px; height: 62px; flex-shrink: 0; border-radius: 50%; cursor: pointer; }
  .portada img, .logo { position: absolute; inset: 5px; width: 52px; height: 52px; border-radius: 50%; object-fit: cover; }
  .logo { display: grid; place-items: center; background: linear-gradient(135deg, #22d3ee, #7c3aed); }
  .anillo { position: absolute; inset: 0; width: 62px; height: 62px; transform: rotate(-90deg); pointer-events: none; }
  .anillo circle { fill: none; stroke-width: 3; }
  .fondo-anillo { stroke: rgba(255, 255, 255, 0.12); }
  .lleno { stroke: #22d3ee; stroke-linecap: round; transition: stroke-dashoffset 1s linear; }
  .pausada {
    position: absolute; inset: 5px; border-radius: 50%; display: grid; place-items: center; background: rgba(0, 0, 0, 0.45);
    opacity: 0; transition: opacity 150ms;
  }
  .pausada.visible { opacity: 1; }
  /* Lo de la píldora siempre está (con su ancho fijo) y solo se desvanece: así no se reacomoda mientras crece */
  .resto {
    flex: 0 0 auto; width: 262px; display: flex; align-items: center; gap: 4px; padding: 0 8px 0 10px; box-sizing: border-box;
    opacity: 0; transition: opacity 120ms;
  }
  .izquierda .resto { padding: 0 6px 0 12px; }
  .abierta .resto { opacity: 1; transition: opacity 180ms 60ms; }
  .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; line-height: 1.25; }
  .textos b { font-size: 13.5px; }
  .textos small { font-size: 12px; color: rgba(255, 255, 255, 0.6); }
  .controles { display: flex; align-items: center; gap: 1px; flex-shrink: 0; }
  .controles button {
    width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; color: #fff; cursor: pointer;
    background: transparent; border: 0; padding: 0;
  }
  .controles button:hover:not(:disabled) { background: rgba(255, 255, 255, 0.1); }
  .controles button:disabled { opacity: 0.35; cursor: default; }
  .controles .play { width: 36px; height: 36px; background: #fff; color: #04121a; }
  .controles .play:hover:not(:disabled) { background: #e6edf3; }
  .cortar { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
