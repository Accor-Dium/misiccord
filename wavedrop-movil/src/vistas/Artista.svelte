<script>
  import { canciones, t } from "../lib/idioma.svelte.js";
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { py, src } from "../lib/api.js";
  import { abrir, atras, aviso } from "../lib/estado.svelte.js";
  import { reproducir, reproducirAleatorio } from "../lib/reproductor.svelte.js";
  import FilaCancion from "../componentes/FilaCancion.svelte";
  import Icono from "../componentes/Icono.svelte";
  import Tarjeta from "../componentes/Tarjeta.svelte";

  // Artista: primero lo que tienes (al instante y sin internet) y, si hay conexión, lo de YouTube Music debajo.
  // Se abre con e.nombre y/o e.id (browse_id).
  let { e } = $props();
  const a = $derived(e.datos);
  let tuyo = $state(e.tuyo ?? null); // { canciones, albumes }
  let sinConexion = $state(false);
  let verMas = $state(false);
  let verTodas = $state(false);
  const tuyas = $derived(tuyo?.canciones ?? []);
  const nombre = $derived(a?.nombre ?? e.nombre ?? "");
  const lista = $derived(tuyas.length ? tuyas : a?.canciones ?? []);
  const portada = $derived(a?.portada ?? tuyo?.albumes?.find((x) => x.portada)?.portada ?? tuyas.find((c) => c.portada)?.portada);

  // Las primeras canciones se dejan listas para que suenen en cuanto las toques
  $effect(() => {
    const ids = (a?.canciones ?? []).filter((c) => !c.ruta && c.id).slice(0, 5).map((c) => c.id);
    if (ids.length) py("precargar", { ids }).catch(() => {});
  });

  onMount(async () => {
    if (e.nombre && !tuyo) {
      try {
        tuyo = e.tuyo = await py("artista_local", { nombre: e.nombre });
      } catch {}
    }
    if (e.datos) return;
    try {
      let id = e.id;
      if (!id) {
        const r = await py("buscar", { q: e.nombre, tipo: "artistas" });
        id = r.artistas?.[0]?.browse_id;
        if (!id) throw new Error("sin artista");
      }
      e.datos = (await py("artista", { browse_id: id })).artista;
    } catch (err) {
      // Sin internet no es un error si tienes canciones suyas: lo tuyo ya está en pantalla
      sinConexion = true;
      if (!tuyo?.canciones.length) aviso(t("No encontré a {nombre}", { nombre: e.nombre ?? t("este artista") }), "error");
    }
  });
</script>

<div class="vista">
  <button class="redondo relleno volver" onclick={atras} aria-label={t("Atrás")}><Icono nombre="atras" tam={24} /></button>
  <div class="hero" style:background-image={portada ? `url("${src(portada)}")` : "none"}>
    <div class="degradado"></div>
    <div class="nombre">
      <h1>{nombre}</h1>
      {#if a?.oyentes}<p>{a.oyentes} oyentes mensuales</p>{/if}
    </div>
  </div>

  {#if tuyas.length}
    <div class="cuerpo">
      <div class="acciones">
        <button class="pildora clara" onclick={() => reproducir(lista, 0, nombre)}><Icono nombre="play" relleno tam={20} /> {t("Reproducir")}</button>
        <button class="pildora oscura" onclick={() => reproducirAleatorio(lista, nombre)}><Icono nombre="aleatorio" tam={20} /> {t("Aleatorio")}</button>
      </div>
      <div class="titulo-seccion">{t("En tu biblioteca")} <small>{canciones(tuyas.length)}</small></div>
      {#each verTodas ? tuyas : tuyas.slice(0, 6) as c, i (c.db_id)}
        <FilaCancion cancion={c} alTocar={() => reproducir(tuyas, i, nombre)} />
      {/each}
      {#if tuyas.length > 6}
        <button class="ver" onclick={() => (verTodas = !verTodas)}>{verTodas ? t("Ver menos") : t("Ver todas ({n})", { n: tuyas.length })}</button>
      {/if}
      {#if tuyo.albumes.length}
        <div class="titulo-seccion">{t("Tus álbumes")}</div>
        <div class="carrusel">
          {#each tuyo.albumes as al}
            <Tarjeta portada={al.portada} titulo={al.nombre} subtitulo={[al.anio, canciones(al.canciones)].filter(Boolean).join(" · ")}
              alTocar={() => abrir("album", { local: al })} />
          {/each}
        </div>
      {/if}
      {#if sinConexion}<p class="tenue sin-red">{t("Sin conexión: esto es lo que tienes guardado.")}</p>{/if}
    </div>
  {/if}

  {#if a}
    <div class="cuerpo" in:fade={{ duration: 300 }}>
      {#if a.descripcion}
        <p class="desc" class:abierta={verMas}>{a.descripcion}</p>
        <button class="ver" onclick={() => (verMas = !verMas)}>{verMas ? "Ver menos" : "Ver más"}</button>
      {/if}
      {#if !tuyas.length}
        <div class="acciones">
          <button class="pildora clara" onclick={() => reproducir(a.canciones, 0, a.nombre)}><Icono nombre="play" relleno tam={20} /> {t("Reproducir")}</button>
          <button class="pildora oscura" onclick={() => reproducirAleatorio(a.canciones, a.nombre)}><Icono nombre="aleatorio" tam={20} /> {t("Aleatorio")}</button>
        </div>
      {/if}

      {#if a.canciones.length}
        <div class="titulo-seccion">{t("Populares")}</div>
        {#each a.canciones as c, i}
          <FilaCancion cancion={c} alTocar={() => reproducir(a.canciones, i, a.nombre)} />
        {/each}
      {/if}

      {#if a.albumes.length}
        <div class="titulo-seccion">{t("Álbumes y sencillos")}</div>
        <div class="carrusel">
          {#each a.albumes as al}
            <Tarjeta portada={al.miniatura} titulo={al.titulo} subtitulo={[al.tipo, al.anio].filter(Boolean).join(" · ")}
              alTocar={() => abrir("album", { id: al.browse_id })} />
          {/each}
        </div>
      {/if}

      {#if a.parecidos.length}
        <div class="titulo-seccion">{t("Artistas parecidos")}</div>
        <div class="carrusel">
          {#each a.parecidos as p}
            <Tarjeta portada={p.miniatura} titulo={p.nombre} redonda icono="persona" ancho="var(--artista)"
              alTocar={() => abrir("artista", { id: p.browse_id, nombre: p.nombre })} />
          {/each}
        </div>
      {/if}
    </div>
  {:else if !tuyas.length && !sinConexion}
    <div class="cuerpo">{#each Array(5) as _}<div class="cargando-bloque" style="height:56px;margin:10px 0"></div>{/each}</div>
  {/if}
</div>

<style>
  .vista { position: relative; }
  .volver { position: absolute; top: calc(var(--seguro-arriba) + 10px); left: 12px; z-index: 3; background: rgba(0, 0, 0, 0.35); backdrop-filter: blur(10px); }
  .hero {
    position: relative; height: 56vh; min-height: 320px; background: var(--tarjeta) center 20% / cover no-repeat;
    display: flex; align-items: flex-end;
  }
  .degradado { position: absolute; inset: 0; background: linear-gradient(to bottom, rgba(10, 15, 20, 0.05) 30%, var(--fondo)); }
  .nombre { position: relative; padding: 0 var(--margen) 4px; }
  h1 { margin: 0; font-size: 44px; font-weight: 900; letter-spacing: -1px; line-height: 1; }
  .nombre p { margin: 10px 0 0; font-weight: 600; color: rgba(255, 255, 255, 0.8); }
  .cuerpo { padding: 0 var(--margen); }
  .desc {
    margin: 14px 0 0; font-weight: 500; line-height: 1.45; color: rgba(255, 255, 255, 0.88);
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }
  .desc.abierta { -webkit-line-clamp: unset; }
  .ver { margin-top: 4px; font-weight: 700; color: var(--tenue); }
  .acciones { display: flex; gap: 12px; margin: 20px 0 4px; }
  .acciones .pildora { flex: 1; }
  .sin-red { margin-top: 16px; font-size: 13.5px; }
</style>
