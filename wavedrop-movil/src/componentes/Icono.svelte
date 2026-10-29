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
    arrastrar: "M5 9h14M5 15h14",
    ordenar: "M4 7h9M4 12h6M4 17h3M17 5v14M14 16l3 3 3-3",
    corazon: "M12 20.3s-7.6-4.6-9.4-9.3C1.3 7.6 3.5 4.3 7 4.3c2 0 3.6 1.1 5 3 1.4-1.9 3-3 5-3 3.5 0 5.7 3.3 4.4 6.7-1.8 4.7-9.4 9.3-9.4 9.3z",
    estadisticas: "M5 20V11M12 20V4M19 20v-6",
    info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v6M12 7.5h.01",
    video: "M3 7h11a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H3zM16 11l5-3v8l-5-3",
    carpeta: "M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    fundido: "M3 18c4 0 5-12 9-12s5 12 9 12M3 6c4 0 5 12 9 12s5-12 9-12",
    alerta: "M12 8v5M12 16.5h.01M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
    copiar: "M9 9h11v11H9zM5 15H4V4h11v1",
    usb: "M12 2v14M12 16a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM12 12 7 9V6M12 10l5-3V5M6 4h2v2H6zM16 3h2v2h-2z",
    abrir: "M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5",
    radio: "M12 13a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM8.5 15a5 5 0 0 1 0-7M15.5 8a5 5 0 0 1 0 7M5.6 18a9 9 0 0 1 0-13M18.4 5a9 9 0 0 1 0 13",
    actualizar: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
    tendencia: "M3 17l6-6 4 4 8-8M15 7h6v6",
    nuevo: "M12 3l2.4 5.4L20 9.3l-4.2 3.9 1.1 5.8L12 16.1 7.1 19l1.1-5.8L4 9.3l5.6-.9z",
    animo: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8.5 14a4.5 4.5 0 0 0 7 0M9 9.5h.01M15 9.5h.01",
    idioma: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3.5 9h17M3.5 15h17M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z",
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
