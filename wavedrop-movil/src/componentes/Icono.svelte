<script>
  // Iconos en línea (trazos de 24x24) para no depender de fuentes ni librerías.
  let { nombre, tam = 24, relleno = false, clase = "" } = $props();

  const trazos = {
    inicio: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
    buscar: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4.35-4.35",
    biblioteca: "M5 4v16M9.5 4v16M14 4.5l5 15",
    descargas: "M12 4v11m0 0-4.5-4.5M12 15l4.5-4.5M5 20h14",
    ajustes: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm7.4-3a7.4 7.4 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7.6 7.6 0 0 0-2-1.2L14.5 3h-4l-.4 2.6a7.6 7.6 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1a7.6 7.6 0 0 0 2 1.2l.4 2.6h4l.4-2.6a7.6 7.6 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z",
    play: "M7 4.5v15a1 1 0 0 0 1.5.86l12-7.5a1 1 0 0 0 0-1.72l-12-7.5A1 1 0 0 0 7 4.5z",
    pausa: "M7 4h3.5v16H7zM13.5 4H17v16h-3.5z",
    siguiente: "M5 5.5v13l9.5-6.5zM17 5h2.5v14H17z",
    anterior: "M19 5.5v13L9.5 12zM4.5 5H7v14H4.5z",
    aleatorio: "M16 4h4v4M20 4l-6.5 6.5M4 20l6-6M16 20h4v-4M20 20 4 4",
    repetir: "M17 2l3 3-3 3M4 11V9a4 4 0 0 1 4-4h12M7 22l-3-3 3-3M20 13v2a4 4 0 0 1-4 4H4",
    abajo: "M6 9l6 6 6-6",
    atras: "M15 5l-7 7 7 7",
    mas: "M5 12h.01M12 12h.01M19 12h.01",
    agregar: "M12 5v14M5 12h14",
    check: "M5 12.5l4.5 4.5L19 7.5",
    cerrar: "M6 6l12 12M18 6 6 18",
    letra: "M4 6h16M4 12h10M4 18h7M18 15v6M15 18h6",
    cola: "M4 6h12M4 12h12M4 18h8M18 14v7l4-3.5z",
    compartir: "M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM8.6 13.5l6.8 4M15.4 6.5l-6.8 4",
    disco: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm0-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    persona: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-8 9a8 8 0 0 1 16 0",
    lista: "M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01",
    nota: "M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zm12-2a3 3 0 1 1-6 0 3 3 0 0 1 6 0z",
    link: "M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1",
    basura: "M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3",
    seleccionar: "M4 5h4v4H4zM4 15h4v4H4zM11 7h9M11 17h9M5 7l1 1 2-2",
    jam: "M12 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM7.8 14.2a6 6 0 0 1 0-8.4M16.2 5.8a6 6 0 0 1 0 8.4M5 17a10 10 0 0 1 0-14M19 3a10 10 0 0 1 0 14M12 12v9",
    volumen: "M4 9v6h4l5 4V5L8 9zM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12",
    silencio: "M4 9v6h4l5 4V5L8 9zM17 9l5 6M22 9l-5 6",
    qr: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2v2h-2zM18 14h2v2h-2zM14 18h2v2h-2zM18 18h2v2h-2z",
    camara: "M4 8h3l2-3h6l2 3h3v11H4zM12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z",
    subir: "M12 20V9m0 0-4.5 4.5M12 9l4.5 4.5M5 4h14",
    video: "M3 7h11a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H3zM16 11l5-3v8l-5-3",
    carpeta: "M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    fundido: "M3 18c4 0 5-12 9-12s5 12 9 12M3 6c4 0 5 12 9 12s5-12 9-12",
  };
</script>

<svg
  class={clase}
  width={tam}
  height={tam}
  viewBox="0 0 24 24"
  fill={relleno ? "currentColor" : "none"}
  stroke={relleno ? "none" : "currentColor"}
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  <path d={trazos[nombre] ?? ""} />
</svg>
