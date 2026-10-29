// use:jalarParaActualizar={{ alSoltar, estado }}: jalar hacia abajo con el dedo estando hasta arriba de la vista
// recarga (como en las apps del cel). Solo con toque: con mouse no aplica. La vista se desplaza dentro de <main>.
// `estado` es un objeto $state donde se escribe { distancia, listo } para dibujar el indicador.

const UMBRAL = 72;

export function jalarParaActualizar(nodo, opciones) {
  let { alSoltar, estado } = opciones;
  let inicioY = null;
  const principal = () => nodo.closest("main");

  const abajo = (e) => {
    if (e.touches.length !== 1 || estado.cargando || (principal()?.scrollTop ?? 0) > 0) return;
    inicioY = e.touches[0].clientY;
  };
  const mover = (e) => {
    if (inicioY === null) return;
    const dy = e.touches[0].clientY - inicioY;
    if (dy <= 0 || (principal()?.scrollTop ?? 0) > 0) {
      estado.distancia = 0;
      return;
    }
    // Con resistencia: cuesta más mientras más jalas
    estado.distancia = Math.min(130, dy * 0.5);
    estado.listo = estado.distancia >= UMBRAL;
  };
  const soltar = async () => {
    if (inicioY === null) return;
    inicioY = null;
    const listo = estado.listo;
    estado.listo = false;
    if (!listo) {
      estado.distancia = 0;
      return;
    }
    navigator.vibrate?.(15);
    estado.cargando = true;
    estado.distancia = UMBRAL * 0.75;
    try {
      await alSoltar();
    } finally {
      estado.cargando = false;
      estado.distancia = 0;
    }
  };

  nodo.addEventListener("touchstart", abajo, { passive: true });
  nodo.addEventListener("touchmove", mover, { passive: true });
  nodo.addEventListener("touchend", soltar);
  nodo.addEventListener("touchcancel", soltar);
  return {
    update(nuevas) {
      ({ alSoltar, estado } = nuevas);
    },
    destroy() {
      nodo.removeEventListener("touchstart", abajo);
      nodo.removeEventListener("touchmove", mover);
      nodo.removeEventListener("touchend", soltar);
      nodo.removeEventListener("touchcancel", soltar);
    },
  };
}
