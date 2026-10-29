// <main> tiene su propia capa (view-transition-name): lo que deba quedar encima de la barra de navegación
// y del mini reproductor (ventanas, barras flotantes) se mueve directo a <body> con use:aBody.
export function aBody(nodo) {
  document.body.appendChild(nodo);
  return { destroy: () => nodo.remove() };
}
