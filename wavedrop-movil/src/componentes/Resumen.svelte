<script>
  import { fade } from "svelte/transition";
  import { py } from "../lib/api.js";
  import { aBody } from "../lib/aBody.js";
  import { aviso, ui } from "../lib/estado.svelte.js";
  import { local, t } from "../lib/idioma.svelte.js";
  import { reproducir } from "../lib/reproductor.svelte.js";
  import Icono from "./Icono.svelte";
  import Portada from "./Portada.svelte";

  // Presentación del resumen (como las de YouTube Music y Apple Music): pantallas que avanzan solas.
  // Toca a la derecha para adelantar, a la izquierda para regresar; deja presionado para detenerla.
  const DURACION = 7000;
  let datos = $state(null);
  let n = $state(0);
  let avance = $state(0); // 0 a 1 en la pantalla actual
  let detenida = $state(false);

  const numero = (x) => new Intl.NumberFormat(local()).format(x);
  const veces = (x) => (x === 1 ? t("1 vez") : t("{n} veces", { n: x }));

  $effect(() => {
    const r = ui.resumen;
    datos = null;
    n = 0;
    avance = 0;
    if (!r) return;
    py("estadisticas", { dias: r.dias })
      .then((d) => { if (ui.resumen === r) datos = d; })
      .catch(() => { aviso(t("No pude calcular tus estadísticas"), "error"); cerrar(); });
  });

  const horaPico = $derived(datos ? datos.por_hora.indexOf(Math.max(...datos.por_hora)) : 0);
  const momento = $derived(horaPico < 6 ? t("de madrugada") : horaPico < 12 ? t("por la mañana") : horaPico < 19 ? t("por la tarde") : t("de noche"));
  const cambio = $derived.by(() => {
    if (!datos?.anterior.minutos) return null;
    return Math.round(((datos.actual.minutos - datos.anterior.minutos) / datos.anterior.minutos) * 100);
  });
  const portadaDe = (nombre) => datos?.canciones.find((c) => (c.artista || "").startsWith(nombre))?.portada;
  const pantallas = $derived.by(() => {
    if (!datos) return [];
    const p = ["inicio", "minutos"];
    if (datos.artistas.length) p.push("artistas");
    if (datos.canciones.length) p.push("canciones");
    if (datos.generos.length) p.push("generos");
    p.push("hora", "final");
    return p;
  });

  function cerrar() {
    ui.resumen = null;
  }
  function ir(paso) {
    const j = n + paso;
    if (j < 0) return;
    if (j >= pantallas.length) return cerrar();
    n = j;
    avance = 0;
  }

  // Avanza solo (se detiene al dejar presionado o en la última)
  $effect(() => {
    if (!datos) return;
    let antes = performance.now();
    let cuadro;
    const paso = (ahora) => {
      if (!detenida && n < pantallas.length - 1) {
        avance += (ahora - antes) / DURACION;
        if (avance >= 1) ir(1);
      }
      antes = ahora;
      cuadro = requestAnimationFrame(paso);
    };
    cuadro = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(cuadro);
  });

  let presionado = 0;
  function bajar() {
    presionado = performance.now();
    detenida = true;
  }
  function subir(ev) {
    detenida = false;
    if (performance.now() - presionado > 250) return; // era para detenerla, no un toque
    if (ev.target.closest?.("button")) return;
    ir(ev.clientX < innerWidth * 0.3 ? -1 : 1);
  }
  function escucharTop() {
    const lista = datos.canciones.filter((c) => c.local || c.id);
    const nombre = ui.resumen.nombre;
    cerrar();
    if (lista.length) reproducir(lista, 0, nombre);
  }
</script>

{#if ui.resumen}
  <div class="resumen fondo-{n % 5}" use:aBody transition:fade={{ duration: 220 }} role="dialog" aria-label={t("Tu resumen")}
    onpointerdown={bajar} onpointerup={subir} onpointercancel={() => (detenida = false)}>
    <div class="barras" aria-hidden="true">
      {#each pantallas as _, i}
        <span><i style:width="{i < n ? 100 : i === n ? avance * 100 : 0}%"></i></span>
      {/each}
    </div>
    <button class="redondo cerrar" onclick={cerrar} aria-label={t("Cerrar")}><Icono nombre="cerrar" tam={24} /></button>

    {#if !datos}
      <div class="pantalla"><p class="sub">{t("Preparando tu resumen…")}</p></div>
    {:else}
      {#key n}
        <div class="pantalla" in:fade={{ duration: 300 }}>
          {#if pantallas[n] === "inicio"}
            <p class="sub">{t("Tu resumen de música")}</p>
            <h1 class="gigante primera">{ui.resumen.nombre}</h1>
            <p class="sub">{t("Esto fue lo que más sonó")}</p>
          {:else if pantallas[n] === "minutos"}
            <p class="sub">{t("Escuchaste")}</p>
            <h1 class="gigante">{numero(datos.actual.minutos)}</h1>
            <p class="sub">{t("minutos de música")}</p>
            <p class="dato">{t("{r} reproducciones · {c} canciones · {a} artistas", { r: numero(datos.actual.reproducciones), c: numero(datos.actual.canciones), a: numero(datos.actual.artistas) })}</p>
            {#if cambio !== null}<p class="dato">{cambio >= 0 ? t("{n} % más que el periodo anterior", { n: cambio }) : t("{n} % menos que el periodo anterior", { n: -cambio })}</p>{/if}
          {:else if pantallas[n] === "artistas"}
            <p class="sub">{t("Tu artista número uno")}</p>
            <div class="tapa"><Portada url={portadaDe(datos.artistas[0].nombre)} radio="50%" icono="persona" /></div>
            <h2>{datos.artistas[0].nombre}</h2>
            <p class="dato">{datos.artistas[0].pct} % · {veces(datos.artistas[0].veces)}</p>
            <ol>{#each datos.artistas.slice(1, 5) as a, i}<li><span>{i + 2}</span><b class="cortar">{a.nombre}</b><small>{a.pct} %</small></li>{/each}</ol>
          {:else if pantallas[n] === "canciones"}
            <p class="sub">{t("Tu canción número uno")}</p>
            <div class="tapa"><Portada url={datos.canciones[0].portada} radio="14px" icono="nota" /></div>
            <h2>{datos.canciones[0].titulo}</h2>
            <p class="dato">{datos.canciones[0].artista} · {veces(datos.canciones[0].veces)}</p>
            <ol>{#each datos.canciones.slice(1, 5) as c, i}<li><span>{i + 2}</span><b class="cortar">{c.titulo}</b><small>{veces(c.veces)}</small></li>{/each}</ol>
          {:else if pantallas[n] === "generos"}
            <p class="sub">{t("Tu género")}</p>
            <h1 class="gigante mediano">{datos.generos[0].nombre}</h1>
            <p class="dato">{datos.generos[0].pct} %</p>
            <ol>{#each datos.generos.slice(1, 5) as g, i}<li><span>{i + 2}</span><b class="cortar">{g.nombre}</b><small>{g.pct} %</small></li>{/each}</ol>
          {:else if pantallas[n] === "hora"}
            <p class="sub">{t("Tu momento para escuchar")}</p>
            <h1 class="gigante mediano">{momento}</h1>
            <p class="dato">{t("Sobre todo de {a}:00 a {b}:00", { a: horaPico, b: (horaPico + 1) % 24 })}</p>
          {:else}
            <p class="sub">{ui.resumen.nombre}</p>
            <h2>{t("Eso fue todo")}</h2>
            <div class="cuadros">
              <div><b>{numero(datos.actual.minutos)}</b><small>{t("Minutos")}</small></div>
              <div><b>{numero(datos.actual.reproducciones)}</b><small>{t("Reproducciones")}</small></div>
              <div><b>{numero(datos.actual.canciones)}</b><small>{t("Canciones distintas")}</small></div>
              <div><b>{numero(datos.actual.artistas)}</b><small>{t("Artistas")}</small></div>
            </div>
            <button class="pildora clara" onclick={escucharTop}><Icono nombre="play" relleno tam={20} /> {t("Escuchar mi top")}</button>
          {/if}
        </div>
      {/key}
    {/if}
  </div>
{/if}

<style>
  .resumen {
    position: fixed; inset: 0; z-index: 400; display: flex; flex-direction: column; color: #fff; user-select: none; -webkit-user-select: none;
    padding: calc(var(--seguro-arriba) + 12px) 22px calc(var(--seguro-abajo) + 24px); transition: background 0.6s;
  }
  .fondo-0 { background: linear-gradient(160deg, #7c3aed, #db2777 60%, #f97316); }
  .fondo-1 { background: linear-gradient(160deg, #0891b2, #2563eb 60%, #4f46e5); }
  .fondo-2 { background: linear-gradient(160deg, #be123c, #7c3aed); }
  .fondo-3 { background: linear-gradient(160deg, #059669, #0891b2); }
  .fondo-4 { background: linear-gradient(160deg, #f59e0b, #dc2626); }
  .barras { display: flex; gap: 4px; }
  .barras span { flex: 1; height: 3px; border-radius: 2px; background: rgba(255, 255, 255, 0.3); overflow: hidden; }
  .barras i { display: block; height: 100%; background: #fff; }
  .cerrar { align-self: flex-end; margin-top: 6px; }
  .pantalla { flex: 1; min-height: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; gap: 10px; max-width: 560px; width: 100%; margin: 0 auto; }
  .sub { margin: 0; font-size: 19px; font-weight: 600; opacity: 0.9; }
  .gigante { margin: 0; font-size: clamp(54px, 16vw, 104px); font-weight: 900; letter-spacing: -2px; line-height: 1.02; }
  .gigante.primera { font-size: clamp(42px, 12vw, 80px); text-transform: capitalize; }
  .gigante.mediano { font-size: clamp(40px, 11vw, 76px); }
  h2 { margin: 6px 0 0; font-size: 28px; font-weight: 800; }
  .dato { margin: 0; font-size: 16px; opacity: 0.88; }
  .tapa { width: min(52vw, 34vh); margin: 8px 0; }
  ol { list-style: none; margin: 12px 0 0; padding: 0; width: 100%; max-width: 380px; display: flex; flex-direction: column; gap: 8px; text-align: left; }
  li { display: flex; align-items: center; gap: 12px; }
  li span { width: 18px; font-weight: 800; opacity: 0.75; }
  li b { flex: 1; min-width: 0; font-weight: 700; }
  li small { opacity: 0.85; flex-shrink: 0; }
  .cuadros { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; width: 100%; max-width: 380px; margin: 14px 0 18px; }
  .cuadros div { display: flex; flex-direction: column; padding: 14px; border-radius: 16px; background: rgba(0, 0, 0, 0.22); }
  .cuadros b { font-size: 26px; font-weight: 800; }
  .cuadros small { opacity: 0.85; }
</style>
