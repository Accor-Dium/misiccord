<script>
  import { onMount } from "svelte";
  import { t } from "../lib/idioma.svelte.js";
  import { analizadorDeAudio } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";

  // Visualizadores como los del Windows Media Player clásico, dibujados con el sonido real (AnalyserNode).
  // Toca el lienzo para cambiar de visualizador. Solo dibuja mientras se ve: es lo único que gasta procesador.
  const MODOS = [["barras", t("Barras")], ["onda", t("Onda")], ["alquimia", t("Alquimia")], ["bateria", t("Batería")], ["estrellas", t("Estrellas")]];
  let modo = $state(leerModo());
  let completo = $state(false);
  let nombreVisible = $state(true);
  let lienzo;

  function leerModo() {
    try { return Math.min(MODOS.length - 1, Number(localStorage.getItem("misiccord_visual") || 0)); } catch { return 0; }
  }
  let reloj;
  function mostrarNombre() {
    nombreVisible = true;
    clearTimeout(reloj);
    reloj = setTimeout(() => (nombreVisible = false), 1800);
  }
  function siguienteModo() {
    modo = (modo + 1) % MODOS.length;
    try { localStorage.setItem("misiccord_visual", String(modo)); } catch {}
    mostrarNombre();
  }

  onMount(() => {
    mostrarNombre();
    const analizador = analizadorDeAudio();
    const frec = new Uint8Array(analizador.frequencyBinCount);
    const onda = new Uint8Array(analizador.fftSize);
    const g = lienzo.getContext("2d");
    let W = 0, H = 0, matiz = 0, cuadro, anterior = -1;
    const picos = new Float32Array(48);
    const estrellas = Array.from({ length: 220 }, nuevaEstrella);

    function medir() {
      const pr = Math.min(devicePixelRatio || 1, 2);
      W = lienzo.width = Math.round(lienzo.clientWidth * pr);
      H = lienzo.height = Math.round(lienzo.clientHeight * pr);
    }
    const vigia = new ResizeObserver(medir);
    vigia.observe(lienzo);
    medir();

    /** Intensidad (0–1) de un tramo del espectro; `x` va de 0 a 1 en escala logarítmica, como oye el oído. */
    function nivel(x) {
      const n = frec.length * 0.75;
      const i = Math.min(frec.length - 1, Math.floor(Math.pow(n, x)));
      return frec[i] / 255;
    }
    const graves = () => (nivel(0.2) + nivel(0.3) + nivel(0.38)) / 3;

    function barras() {
      g.fillStyle = "#000";
      g.fillRect(0, 0, W, H);
      const n = picos.length, ancho = W / n, bloque = Math.max(4, H / 32);
      for (let i = 0; i < n; i++) {
        const v = nivel(i / n) * H;
        picos[i] = Math.max(v, picos[i] - H * 0.008);
        for (let y = 0; y < v; y += bloque) {
          const a = y / H;
          g.fillStyle = a < 0.55 ? "#22e36b" : a < 0.8 ? "#f6e23a" : "#ff4438"; // verde, amarillo, rojo
          g.fillRect(i * ancho + 1, H - y - bloque + 1, ancho - 2, bloque - 2);
        }
        g.fillStyle = "#fff";
        g.fillRect(i * ancho + 1, H - picos[i] - 3, ancho - 2, 3);
      }
    }

    function linea(escala) {
      g.beginPath();
      for (let i = 0; i < onda.length; i += 4) {
        const x = (i / onda.length) * W;
        const y = H / 2 + ((onda[i] - 128) / 128) * H * escala;
        i ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.stroke();
    }
    function ondaVisual() {
      g.fillStyle = "rgba(0, 0, 0, 0.28)";
      g.fillRect(0, 0, W, H);
      g.lineWidth = Math.max(2, W / 260);
      g.strokeStyle = `hsl(${matiz}, 95%, 62%)`;
      g.shadowColor = g.strokeStyle;
      g.shadowBlur = 14;
      linea(0.42);
      g.shadowBlur = 0;
      g.strokeStyle = `hsla(${matiz + 150}, 95%, 70%, 0.45)`;
      linea(-0.28);
    }

    /** Túnel: cada cuadro se vuelve a pintar un poco más grande y girado sobre el anterior. */
    function alquimia() {
      g.save();
      g.globalAlpha = 0.93;
      g.translate(W / 2, H / 2);
      g.rotate(0.006 + graves() * 0.02);
      g.scale(1.022, 1.022);
      g.drawImage(lienzo, -W / 2, -H / 2);
      g.restore();
      g.fillStyle = "rgba(0, 0, 0, 0.05)";
      g.fillRect(0, 0, W, H);
      const r0 = Math.min(W, H) * 0.16, puntas = 64;
      g.beginPath();
      for (let i = 0; i <= puntas; i++) {
        const a = (i / puntas) * Math.PI * 2, r = r0 + nivel(i < puntas / 2 ? i / (puntas / 2) : 2 - i / (puntas / 2)) * r0 * 1.5;
        const x = W / 2 + Math.cos(a) * r, y = H / 2 + Math.sin(a) * r;
        i ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.lineWidth = Math.max(2, W / 200);
      g.strokeStyle = `hsl(${matiz}, 100%, 62%)`;
      g.stroke();
    }

    /** Caleidoscopio: el espectro se repite en gajos en espejo alrededor del centro. */
    function bateria() {
      g.fillStyle = "rgba(0, 0, 0, 0.2)";
      g.fillRect(0, 0, W, H);
      const gajos = 10, r = Math.hypot(W, H) * 0.52;
      g.save();
      g.translate(W / 2, H / 2);
      g.rotate(matiz * 0.004);
      for (let k = 0; k < gajos; k++) {
        g.rotate((Math.PI * 2) / gajos);
        g.save();
        if (k % 2) g.scale(1, -1);
        for (let i = 0; i < 26; i++) {
          const v = nivel(i / 26), x = (i / 26) * r;
          g.fillStyle = `hsla(${matiz + i * 9 + k * 12}, 100%, ${40 + v * 35}%, ${0.15 + v * 0.75})`;
          g.beginPath();
          g.moveTo(x, 0);
          g.lineTo(x + r / 26, v * r * 0.13);
          g.lineTo(x + r / 26, 0);
          g.fill();
        }
        g.restore();
      }
      g.restore();
    }

    function nuevaEstrella() {
      return { a: Math.random() * Math.PI * 2, r: Math.random() * 0.2, v: 0.2 + Math.random() * 0.8 };
    }
    function estrellasVisual() {
      g.fillStyle = "rgba(0, 0, 0, 0.3)";
      g.fillRect(0, 0, W, H);
      const empuje = 0.0015 + graves() * 0.022, m = Math.hypot(W, H) / 2;
      for (let i = 0; i < estrellas.length; i++) {
        const e = estrellas[i];
        const r0 = e.r * m;
        e.r += e.v * empuje * (0.4 + e.r * 4);
        if (e.r > 1) { estrellas[i] = nuevaEstrella(); continue; }
        const r1 = e.r * m;
        g.strokeStyle = `hsla(${matiz + i}, 90%, ${55 + e.r * 40}%, ${Math.min(1, e.r * 3)})`;
        g.lineWidth = 1 + e.r * 3;
        g.beginPath();
        g.moveTo(W / 2 + Math.cos(e.a) * r0, H / 2 + Math.sin(e.a) * r0);
        g.lineTo(W / 2 + Math.cos(e.a) * r1, H / 2 + Math.sin(e.a) * r1);
        g.stroke();
      }
    }

    const dibujos = [barras, ondaVisual, alquimia, bateria, estrellasVisual];
    function ciclo() {
      cuadro = requestAnimationFrame(ciclo);
      if (!W || !H) return;
      analizador.getByteFrequencyData(frec);
      analizador.getByteTimeDomainData(onda);
      matiz = (matiz + 0.5 + graves() * 2) % 360;
      if (modo !== anterior) {
        g.fillStyle = "#000";
        g.fillRect(0, 0, W, H);
        anterior = modo;
      }
      dibujos[modo]();
    }
    ciclo();
    return () => {
      cancelAnimationFrame(cuadro);
      clearTimeout(reloj);
      vigia.disconnect();
    };
  });
</script>

<div class="visual" class:completo>
  <canvas bind:this={lienzo} onclick={siguienteModo} aria-label={t("Cambiar de visualizador")}></canvas>
  <span class="nombre" class:visible={nombreVisible}>{MODOS[modo][1]}</span>
  <button class="grande" onclick={() => (completo = !completo)} aria-label={completo ? t("Salir de pantalla completa") : t("Pantalla completa")}>
    <Icono nombre={completo ? "cerrar" : "expandir"} tam={20} />
  </button>
</div>

<style>
  .visual { position: relative; width: 100%; aspect-ratio: 1; border-radius: 14px; overflow: hidden; background: #000; box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5); }
  .visual.completo { position: fixed; inset: 0; z-index: 80; width: auto; aspect-ratio: auto; border-radius: 0; }
  canvas { display: block; width: 100%; height: 100%; cursor: pointer; }
  .nombre { position: absolute; left: 12px; bottom: 10px; padding: 4px 10px; border-radius: 999px; font-size: 12.5px; font-weight: 700; background: rgba(0, 0, 0, 0.55); color: #fff; opacity: 0; transition: opacity 0.3s; pointer-events: none; }
  .nombre.visible { opacity: 1; }
  .grande { position: absolute; right: 8px; top: 8px; width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; background: rgba(0, 0, 0, 0.45); color: #fff; }
  .completo .grande { top: calc(var(--seguro-arriba) + 10px); right: 12px; }
</style>
