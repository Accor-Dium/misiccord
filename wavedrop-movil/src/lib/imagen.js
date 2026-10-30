/** Cualquier imagen del teléfono o la PC se pasa a JPG de hasta 1200 px (así WebP o fotos enormes también sirven). */
export async function aJpeg(archivo) {
  const imagen = await createImageBitmap(archivo);
  const escala = Math.min(1, 1200 / Math.max(imagen.width, imagen.height));
  const lienzo = document.createElement("canvas");
  lienzo.width = Math.round(imagen.width * escala);
  lienzo.height = Math.round(imagen.height * escala);
  lienzo.getContext("2d").drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
  return lienzo.toDataURL("image/jpeg", 0.9);
}
