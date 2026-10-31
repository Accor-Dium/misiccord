// La pestaña Carpetas de Biblioteca: las rutas de las canciones vueltas árbol, sin preguntarle nada al disco.

const corte = (ruta) => Math.max(ruta.lastIndexOf("/"), ruta.lastIndexOf("\\"));
export const nombreCarpeta = (ruta) => ruta.slice(corte(ruta) + 1) || ruta;

/** Map de ruta → { ruta, nombre, subcarpetas (rutas), canciones (las de ahí mismo), total (con subcarpetas) }. */
export function armarArbol(canciones, raices) {
  const limpias = raices.map((r) => r.replace(/[\\/]+$/, ""));
  const nodos = new Map();
  function nodo(ruta) {
    let n = nodos.get(ruta);
    if (!n) nodos.set(ruta, (n = { ruta, nombre: nombreCarpeta(ruta), subcarpetas: new Set(), canciones: [], total: 0 }));
    return n;
  }
  for (const c of canciones) {
    let ruta = c.ruta.slice(0, corte(c.ruta));
    nodo(ruta).canciones.push(c);
    const raiz = limpias.find((r) => ruta === r || ruta.startsWith(`${r}/`) || ruta.startsWith(`${r}\\`));
    for (;;) {
      nodo(ruta).total++;
      if (ruta === raiz || !raiz) break; // sin raíz (una carpeta que ya se quitó) queda suelta, pero se puede abrir
      const padre = ruta.slice(0, corte(ruta));
      nodo(padre).subcarpetas.add(ruta);
      ruta = padre;
    }
  }
  return nodos;
}

/** De la carpeta de música a esta, para ir de regreso. */
export function migasDe(ruta, nodos) {
  const migas = [nodos.get(ruta)];
  for (;;) {
    const padre = nodos.get(migas[0].ruta.slice(0, corte(migas[0].ruta)));
    if (!padre?.subcarpetas.has(migas[0].ruta)) return migas;
    migas.unshift(padre);
  }
}

/** Las canciones de una carpeta y de todo lo que tiene adentro, carpeta por carpeta. */
export function cancionesDe(nodo, nodos) {
  return [...nodo.canciones, ...[...nodo.subcarpetas].flatMap((r) => cancionesDe(nodos.get(r), nodos))];
}
