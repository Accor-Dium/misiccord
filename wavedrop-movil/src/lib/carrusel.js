// Carruseles con mouse (escritorio): la rueda solo mueve la página hacia abajo y la barra de scroll está oculta,
// así que no había forma de ver lo que sigue a la derecha. Aquí, para todos los .carrusel de la app:
//   - se pueden arrastrar con el mouse (sin abrir la tarjeta al soltar),
//   - al pasar el mouse aparecen flechas a los lados, como en YouTube Music.
// En el cel no cambia nada: el dedo ya los mueve.

const conMouse = window.matchMedia("(hover: hover) and (pointer: fine)");
let actual = null; // carrusel bajo el mouse

const flechas = [-1, 1].map((direccion) => {
  const b = document.createElement("button");
  b.className = "flecha-carrusel";
  b.setAttribute("aria-label", direccion < 0 ? "Anteriores" : "Siguientes");
  b.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${direccion < 0 ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"}"/></svg>`;
  b.addEventListener("click", () => {
    actual?.scrollBy({ left: direccion * actual.clientWidth * 0.8, behavior: "smooth" });
  });
  document.body.append(b);
  return b;
});

function colocar() {
  const c = actual;
  const visible = !!c && conMouse.matches && c.isConnected && c.scrollWidth > c.clientWidth + 4;
  if (!visible) {
    for (const b of flechas) b.classList.remove("visible");
    return;
  }
  const r = c.getBoundingClientRect();
  // A la altura de las portadas (el texto de las tarjetas queda abajo)
  const y = r.top + Math.min(r.height * 0.4, 90) - 20;
  const [izq, der] = flechas;
  izq.style.top = der.style.top = `${y}px`;
  izq.style.left = `${r.left + 14}px`;
  der.style.left = `${r.right - 54}px`;
  izq.classList.toggle("visible", c.scrollLeft > 4);
  der.classList.toggle("visible", c.scrollLeft + c.clientWidth < c.scrollWidth - 4);
}

document.addEventListener("pointerover", (e) => {
  if (e.pointerType !== "mouse") return;
  if (e.target.closest?.(".flecha-carrusel")) return; // pasar a la flecha no cuenta como salir
  actual = e.target.closest?.(".carrusel") ?? null;
  colocar();
});
document.addEventListener("scroll", colocar, true); // el carrusel y la página
window.addEventListener("resize", colocar);

// ---------- Arrastrar con el mouse ----------
let arrastre = null;

document.addEventListener("pointerdown", (e) => {
  if (e.pointerType !== "mouse" || e.button !== 0) return;
  const c = e.target.closest?.(".carrusel");
  if (!c || c.scrollWidth <= c.clientWidth) return;
  arrastre = { c, x: e.clientX, inicio: c.scrollLeft, movido: false };
});

document.addEventListener("pointermove", (e) => {
  if (!arrastre) return;
  const dx = e.clientX - arrastre.x;
  if (!arrastre.movido) {
    if (Math.abs(dx) < 6) return; // un clic con temblor sigue siendo clic
    arrastre.movido = true;
    arrastre.c.style.scrollSnapType = "none"; // si no, el imán pelea contra el arrastre
    arrastre.c.style.cursor = "grabbing";
    document.body.style.userSelect = "none";
  }
  arrastre.c.scrollLeft = arrastre.inicio - dx;
});

function soltar() {
  if (!arrastre) return;
  const { c, movido } = arrastre;
  arrastre = null;
  c.style.cursor = "";
  document.body.style.userSelect = "";
  if (!movido) return;
  c.style.scrollSnapType = "";
  // El clic que llega al soltar no debe abrir la tarjeta donde terminó el arrastre
  const tapar = (ev) => { ev.preventDefault(); ev.stopPropagation(); };
  window.addEventListener("click", tapar, true);
  setTimeout(() => window.removeEventListener("click", tapar, true), 0);
}
document.addEventListener("pointerup", soltar);
document.addEventListener("pointercancel", soltar);
// Las portadas son <img>: el navegador intentaría "arrastrar la imagen" en vez del carrusel
document.addEventListener("dragstart", (e) => {
  if (e.target.closest?.(".carrusel")) e.preventDefault();
});
