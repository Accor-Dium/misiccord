// use:mantener={fn}: dejar presionado ~0.5 s (dedo o mouse) llama fn. El toque normal sigue siendo un toque,
// y deslizar la lista lo cancela. Los botones de adentro (⋯, descargar) no cuentan.

export function mantener(nodo, fn) {
  let espera = null;
  let disparado = false;
  let x = 0;
  let y = 0;

  const cancelar = () => {
    clearTimeout(espera);
    espera = null;
  };
  const abajo = (e) => {
    if (!fn || e.button !== 0) return;
    const boton = e.target.closest?.("button, a, input");
    if (boton && boton !== nodo) return;
    disparado = false;
    x = e.clientX;
    y = e.clientY;
    cancelar();
    espera = setTimeout(() => {
      espera = null;
      disparado = true;
      navigator.vibrate?.(25);
      fn?.();
    }, 500);
  };
  const mover = (e) => {
    if (espera && Math.hypot(e.clientX - x, e.clientY - y) > 10) cancelar();
  };
  // Lo que llega al soltar después de mantener no es un toque: no debe reproducir ni abrir nada
  const clic = (e) => {
    if (!disparado) return;
    disparado = false;
    e.preventDefault();
    e.stopPropagation();
  };
  // Android abre el menú del sistema (copiar, compartir…) con el dedo largo
  const menu = (e) => {
    if (espera || disparado) e.preventDefault();
  };

  nodo.addEventListener("pointerdown", abajo);
  nodo.addEventListener("pointermove", mover);
  nodo.addEventListener("pointerup", cancelar);
  nodo.addEventListener("pointercancel", cancelar);
  nodo.addEventListener("pointerleave", cancelar);
  nodo.addEventListener("click", clic, true);
  nodo.addEventListener("contextmenu", menu);
  return {
    update(nueva) {
      fn = nueva;
    },
    destroy() {
      cancelar();
      nodo.removeEventListener("pointerdown", abajo);
      nodo.removeEventListener("pointermove", mover);
      nodo.removeEventListener("pointerup", cancelar);
      nodo.removeEventListener("pointercancel", cancelar);
      nodo.removeEventListener("pointerleave", cancelar);
      nodo.removeEventListener("click", clic, true);
      nodo.removeEventListener("contextmenu", menu);
    },
  };
}
