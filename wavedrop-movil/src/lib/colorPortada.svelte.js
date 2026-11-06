// El color de fondo de una portada (el de sus orillas, que es lo que se ve "detrás" del dibujo) y una tinta que se lea encima.
// Para la etiqueta del cassette. Se calcula una vez por imagen en un lienzo de 24 px: es instantáneo y no usa internet.
// Necesita CORS: el protocolo asset de Tauri y lh3.googleusercontent.com lo mandan (yt3 no: se pide a lh3); si una no, queda papel.
const PAPEL = { fondo: "#ece6d8", tinta: "#1b1a17" };
const LADO = 24;
const colores = $state({}); // url → { fondo, tinta }
const pedidos = new Set();

function medir(url) {
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    try {
      const lienzo = document.createElement("canvas");
      lienzo.width = lienzo.height = LADO;
      const ctx = lienzo.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(img, 0, 0, LADO, LADO);
      const d = ctx.getImageData(0, 0, LADO, LADO).data;
      // El color que más se repite en las orillas (promediarlas todas revuelve blanco con negro y sale un gris que no está)
      const grupos = new Map(); // tono redondeado → [r, g, b, cuántos]
      for (let y = 0; y < LADO; y++) {
        for (let x = 0; x < LADO; x++) {
          if (x > 1 && x < LADO - 2 && y > 1 && y < LADO - 2) continue; // solo las orillas
          const i = (y * LADO + x) * 4;
          const clave = (d[i] >> 5) * 64 + (d[i + 1] >> 5) * 8 + (d[i + 2] >> 5);
          const s = grupos.get(clave) ?? [0, 0, 0, 0];
          s[0] += d[i]; s[1] += d[i + 1]; s[2] += d[i + 2]; s[3]++;
          grupos.set(clave, s);
        }
      }
      const [sr, sg, sb, n] = [...grupos.values()].reduce((a, s) => (s[3] > a[3] ? s : a));
      const r = Math.round(sr / n), g = Math.round(sg / n), b = Math.round(sb / n);
      const luz = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      colores[url] = { fondo: `rgb(${r}, ${g}, ${b})`, tinta: luz > 0.55 ? "#141414" : "#f5f2ea" };
    } catch {
      colores[url] = PAPEL; // la imagen no mandó CORS y el lienzo quedó "manchado"
    }
  };
  img.onerror = () => (colores[url] = PAPEL);
  // yt3 no manda CORS; la misma imagen en lh3 sí
  img.src = url.replace("//yt3.googleusercontent.com/", "//lh3.googleusercontent.com/");
}

/** Mientras se calcula (o sin portada) es papel, como una etiqueta en blanco. */
export function colorDe(url) {
  if (!url) return PAPEL;
  if (!pedidos.has(url)) {
    pedidos.add(url);
    queueMicrotask(() => medir(url)); // fuera del dibujo: escribir estado mientras se dibuja no se puede
  }
  return colores[url] ?? PAPEL;
}
