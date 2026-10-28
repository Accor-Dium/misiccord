"""Descarga una playlist (YouTube, YT Music, Spotify, SoundCloud...) desde la consola.

Uso:
    python descargar_playlist.py "URL"
    python descargar_playlist.py "URL" --carpeta Musica --formato 0
    python descargar_playlist.py "URL" --por-playlist   # sin separar por artista
"""
import argparse
import sys

from nucleo import FORMATOS, FUENTES, Descargador, ffmpeg_disponible, obtener_coleccion

AYUDA = __doc__ + "\nFormatos (--formato):\n" + "\n".join(f"    {i}: {f.etiqueta}" for i, f in enumerate(FORMATOS))


def main() -> None:
    parser = argparse.ArgumentParser(description=AYUDA, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="Link de la playlist, álbum o canción")
    parser.add_argument("--carpeta", default="descargas", help="Carpeta de destino")
    parser.add_argument("--formato", type=int, default=2, help="Número de formato (ver lista arriba)")
    parser.add_argument("--por-playlist", action="store_true",
                        help="Guardar en una carpeta con el nombre de la playlist en vez de separar por artista")
    args = parser.parse_args()

    if not ffmpeg_disponible():
        sys.exit("No se encontro ffmpeg. Corre instalar.bat y luego cierra y vuelve a abrir la terminal.")

    col = obtener_coleccion(args.url)
    print(f"{col.titulo} ({FUENTES[col.fuente]}): {len(col.entradas)} canciones")
    descargador = Descargador(args.carpeta, FORMATOS[args.formato], args.por_playlist, col.titulo)
    fallidas = 0

    try:
        for e in col.entradas:
            prefijo = f"[{e.indice}/{len(col.entradas)}] {e.artista} - {e.titulo}"
            if descargador.ya_descargada(e):
                print(f"{prefijo}: ya descargada")
                continue
            try:
                descargador.descargar(
                    e, lambda est, pct, *_: print(f"\r{prefijo}: {est} {pct}%   ", end=""), lambda: False
                )
                print(f"\r{prefijo}: listo" + " " * 20)
            except RuntimeError as err:
                print(f"\r{prefijo}: FALLÓ - {err}")
                fallidas += 1
    except KeyboardInterrupt:
        sys.exit("\nCancelado.")

    print(f"Listo. {fallidas} fallaron." if fallidas else "Listo.")


if __name__ == "__main__":
    main()
