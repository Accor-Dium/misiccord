# Misiccord (carpeta `wavedrop-movil/`)

Reproductor y descargador de música (YouTube Music, Spotify, SoundCloud) con biblioteca local, letras
sincronizadas, recomendaciones y **jams** (escuchar juntos en red local o por internet).
Una sola base de código para **Windows** (instalador NSIS) y **Android** (APK).

> El nombre interno histórico es **WaveDrop** y así se queda en identificadores y rutas (ver "No cambiar").
> El nombre visible es **Misiccord**.

Lee este archivo completo antes de cambiar algo. Casi todo lo que "parece raro" aquí tiene una razón
documentada abajo; si algo no está documentado, pregunta antes de "arreglarlo".

---

## Estado del proyecto (al 9 de noviembre de 2026 · versión publicada: **4.2.1**)

Resumen para que no tengas que leer todo el código. Actualiza esta sección cuando publiques una versión.

### Qué hace la app hoy
- **Biblioteca local**: escanea la carpeta de descargas (y las que se agreguen), agrupa por canción/álbum/artista, playlists propias,
  historial de reproducción, vista de lista o cuadrícula (cada pestaña recuerda la suya), índice A–Z con burbuja de la letra. Eliminar canciones: una, varias (modo selección en Biblioteca), un álbum o un artista completo.
- **Cel en horizontal**: pestañas en un riel a la izquierda, reproductor grande en dos columnas (carátula, letra, cola o ecualizador a la izquierda y controles a la derecha), marcación rápida 6×2 y cuadrículas más anchas.
- **Reproductor**: fundido entre canciones (0–12 s, en Ajustes), aleatorio/repetir, volumen de 0 a 200 % con curva perceptual, reproductor grande con letra sincronizada (LRCLIB)
  y cola, mini reproductor. **Al abrir la app sigue lo que sonaba**: cola, canción y posición, en pausa. En el cel: notificación de música, **widget de la pantalla de inicio** (canción y controles; con la app cerrada recuerda la última y su Play abre la app y sigue sonando), pantalla bloqueada, relojes (Wear OS/Galaxy Watch) y audífonos Bluetooth.
  **Android Auto** como app de música (igual que Spotify o YT Music): pestañas Recientes, Me gusta, Playlists y Biblioteca (álbumes y artistas), búsqueda (también por voz), cola y controles; funciona aunque la app esté cerrada. Si se desconectan el coche o los audífonos, la música se pausa (no sigue por la bocina).
- **En línea (YouTube Music)**: buscador en vivo en **Inicio** (resultados mientras escribes), álbumes y artistas, recomendaciones "Para ti"
  (radio a partir de lo que más escuchas/descargas, caché de 6 h). Lo que no tienes suena **al instante por streaming progresivo** y se guarda en caché si se escucha completo.
- **Inicio estilo YouTube Music** (sin cuenta): chips de estados de ánimo (sus playlists), "marcación rápida" 3×3 con tus recomendaciones,
  las secciones generales del inicio de YouTube Music (playlists, selecciones rápidas) y "Explorar" (nuevos lanzamientos, tendencias, estados de ánimo
  y géneros). En el cel se actualiza **jalando hacia abajo**.
- **Menú de canción** (dejarla presionada o "⋯", igual en filas, tarjetas y reproductor): Me gusta arriba, botones grandes (Reproducir después,
  Playlist/Descargar, Compartir) e Iniciar radio, cola, jam, álbum, artista, información, eliminar.
- **Compartir y exportar**: en Biblioteca (botón compartir) se eligen canciones, álbumes, artistas y playlists. Android: menú Compartir del sistema
  (WhatsApp, Telegram, Bluetooth…). PC: copiar los archivos al portapapeles (se pegan en WhatsApp/Telegram de escritorio), copiar a una USB conectada
  o a cualquier carpeta (`Misiccord/<álbum o playlist>/`, con `.m3u8` en las playlists). Lo no descargado se comparte como link de YouTube Music.
- **Idioma**: español e inglés; por defecto el del dispositivo, se cambia en Ajustes → Idioma (la app se recarga).
- **Descargas**: canciones sueltas o links de playlists/álbumes de YouTube, YouTube Music, **Spotify** (se lee la lista de la página *embed* de Spotify, que trae unas 100 canciones como máximo, y cada una se busca en YouTube Music), **Tidal** (igual, desde su página *embed*: hasta 50 canciones) y SoundCloud.
  Metadatos de YouTube Music (MusicBrainz si no está ahí; de MusicBrainz solo el género), carpetas por artista, 1–4 descargas a la vez, carpeta configurable (en Android: carpeta de la app o la pública
  `Music/Misiccord`, que pide "Acceso a todos los archivos").
  **Importar playlists** (Descargas, al pegar un link en el buscador o el botón de lista en una playlist de YouTube Music): además de bajarlas, queda como playlist de la app en el mismo orden; importar el mismo link otra vez la actualiza.
- **Jams** (escuchar juntos):
  - Modos *Sincronizado* (suena en todos) o *Solo aquí* (suena en el anfitrión, ideal con bocina). Cola compartida, votos para saltar, reacciones,
    invitados mandan canciones de su teléfono (en la red local suenan desde su teléfono, sin copiarse) o de YouTube Music (suenan al momento, sin esperar descarga), agregar desde cualquier lista.
  - Unirse: QR (escáner de la app o cámara normal), **link** que abre la app y entra solo, jams cercanos (UDP en la red) o IP + código.
  - **Por internet**: el anfitrión (PC o cel) toca "Abrir" en Invitar; túnel de Cloudflare, sin cuenta ni configurar el módem.
- **Mis dispositivos** (Ajustes, sin cuentas): se vincula el cel con la PC una vez (código de 6 números o QR) y cada vez que están en la misma red Wi-Fi
  se sincronizan solos: Me gusta, playlists, categorías, historial y las canciones que le falten a cada uno. Borrar una canción en uno no la borra en el otro. Por internet todavía no (fase 2).
- **Videos musicales** (apagado por defecto, en Ajustes): ver el clip en el reproductor (sigue al audio, sin sonido propio) y descargarlo junto a la canción.
- **Biblioteca por carpetas**: agregar o quitar carpetas de música y navegarlas en la pestaña Carpetas.
- **Categorías de Biblioteca** (pestaña propia y filtros): décadas y categorías (Jazz, Pop, Rock, Soundtrack, Videojuegos, Anime) más las que crees. Se renombran, se les suman géneros y se les mueven canciones o álbumes. Fotos de artistas y playlists con nombre, carátula y orden editables.
- **Escritorio**: burbuja flotante al minimizar (opcional, Ajustes → Ventana): círculo con la portada y el avance, siempre encima; al pasar el mouse
  se abre con la canción, los controles y el volumen (bocina: pasar el mouse muestra la barra, un clic silencia), se arrastra a donde quieras y un clic regresa a la app. En Windows la vista previa del ícono de la barra
  de tareas trae anterior / reproducir-pausar / siguiente y el título de la ventana dice qué suena.
- **Actualizaciones automáticas** desde GitHub Releases (Windows instala solo; Android baja el APK y abre el instalador).

### Historial de versiones
**Cómo se numera (desde 2.0.1)**: `MAYOR.MENOR.PARCHE`. Cambios grandes (funciones nuevas importantes) suben el **mayor**; arreglos de bugs
medianos, el **menor**; detalles pequeños, el **parche**. Hasta 1.0.10 todo subía solo el último número (por eso se brincó a 2.x).

| Versión | Qué trajo |
|---|---|
| 1.0.0 | Migración de WaveDrop (PySide6) a Tauri 2: Windows + Android con el mismo núcleo de Python; jams en red local. |
| 1.0.1 | Carpeta pública Música en Android (permiso de archivos), primeras actualizaciones automáticas. |
| 1.0.2 | **Lector QR ya no cierra la app** (reglas R8), rediseño de Jams, respaldo ante "not a bot" de YouTube, arreglos de Inicio. |
| 1.0.3 | Jams por internet desde la PC, barra flotante del jam, agregar al jam desde cualquier lista, límite de intentos del código. |
| 1.0.4 | Eliminar canciones, primer streaming, controles de medios/relojes, jam por internet desde el cel (`cloudflared` para Android). |
| 1.0.5 | Streaming progresivo real (cliente `android_music` sin JS: de ~11 s a ~2 s en el cel) y precarga, YouTube en jams al instante, buscador en Inicio. |
| 1.0.6 | Links de jam (`https://accor-dium.github.io/misiccord/jam/#…` → `misiccord://`), el QR usa ese link, avisos si un jam no responde. |
| 1.0.7 | Videos musicales (ver y descargar, opcional) y biblioteca por carpetas (de Omar). |
| 1.0.8 | Info y edición de etiquetas/carátula, letras con traducción y romanización, estadísticas, Me gusta, ordenar biblioteca, ecualizador, pregunta al reproducir en un jam, mantener para agregar a la cola, descargas en segundo plano en Android (de Omar). |
| 1.0.9 | Inicio estilo YouTube Music (estados de ánimo, marcación rápida, Explorar), jalar para actualizar, menú de canción al mantener presionada (compartir, radio), compartir/exportar (Android: menú del sistema; PC: portapapeles, USB o carpeta), avisos nuevos, idioma español/inglés. |
| 1.0.10 | Volumen de 0 a 200 % con curva en decibeles (perceptual); arriba de 100 % refuerzo por Web Audio con limitador y recorte suave. |
| 2.0.1 | La música sigue al quitar la app de recientes (Android), widget de la pantalla de inicio, Biblioteca en lista o cuadrícula, burbuja del índice A–Z (y salta hacia arriba), barra de avance sin parpadeo, deslizar barra/volumen no cierra el reproductor, ícono de micrófono en la letra. Empieza la numeración mayor.menor.parche. |
| 2.0.2 | Los géneros de YouTube Music (Inicio y Explorar) ya abren sus playlists y álbumes. |
| 2.1.0 | Links de Tidal (playlist, álbum o canción; hasta 50 canciones por playlist) y nuevo ícono de la letra (burbuja con comillas). |
| 3.0.0 | Biblioteca instantánea (lista virtual, portadas en la base), pestaña Géneros y columnas de la cuadrícula, cola real con aleatorio, ecualizador de 3 a 31 bandas y mono, visualizadores, resumen del periodo, completar datos y editar álbum con MusicBrainz, kanji con `pykakasi`, álbum/artista primero lo local (de Omar). |
| 3.1.0 | Escritorio: burbuja flotante al minimizar (opcional, en Ajustes) y, en Windows, controles en la vista previa de la barra de tareas y la canción en el título de la ventana. |
| 3.2.0 | Cel en horizontal: riel de pestañas a la izquierda, reproductor en dos columnas, marcación rápida 6×2, cuadrículas más anchas (con sus propias columnas). |
| 3.3.0 | (Omar) Carátulas como estuche de CD o vinilo (Ajustes → Apariencia), con el disco girando en el reproductor y lomos en la lista de álbumes; volumen en la burbuja flotante. |
| 3.4.0 | (Omar) Retomar lo que sonaba al abrir la app y desde el Play del widget; regresar a donde estabas; álbumes: qué te falta (con caché de 7 días) y avance de la discografía; Biblioteca con fotos de artistas, filtros por categoría, pestaña Carpetas y playlists editables (nombre, carátula, orden). |
| 3.5.0 | (Omar) Categorías editables (crear, renombrar, ocultar, mover canciones), todas las canciones de un artista, Ver todos en el artista, bandas del ecualizador en una línea y tocar otra vez la pestaña regresa al principio. |
| 4.0.0 | **Mis dispositivos**: vincular el cel con la PC sin cuentas (código o QR) y sincronizarse solos en la misma red Wi-Fi: Me gusta, playlists, categorías, historial y copiar las canciones que le falten a cada uno. |
| 4.0.1 | Mis dispositivos en Android 17: pide el permiso Dispositivos cercanos (sin él no se veía la PC), el QR trae todas las IPs, tarjeta "Vinculando…", lector de QR con cuadro y Cancelar, y el servidor (sincronizar y jam) ya no tarda ~12 s en arrancar en PCs con VPN. |
| 4.1.0 | Cambios de Omar: historial de lo escuchado y de búsquedas, radio al tocar una canción en Inicio y la búsqueda, carátulas de cassette con etiqueta japonesa, todas las canciones del artista estilo Musicolet (cada disco completo), datos de YouTube Music primero al descargar y "ya la tienes" por álbum, romanización de árabe, hebreo y tailandés. |
| 4.2.0 | Jams: la canción de un invitado suena desde su teléfono en la red local (sin copiarla al anfitrión, entra a la cola al instante; por internet se sigue subiendo) y crear o unirse a un jam pide el permiso Dispositivos cercanos (Android 17). |
| 4.2.1 | Video musical sincronizado con la canción: la canción espera a su video al empezar, al adelantar y si el video se traba; las diferencias chicas se corrigen sin saltos, y se elige el clip de duración más parecida. |
| *(sin publicar)* | **Android Auto completo** (Misiccord sale como app de música: navegar tu música, buscar, cola; con la app cerrada toca `ReproductorAuto`), pausa al desconectarse el coche o los audífonos, e **importar playlists** de Spotify, YouTube, YT Music, Tidal y SoundCloud como playlists de la app. |

### Qué está probado y dónde
- **En dispositivos reales** (lo probó quien administra el proyecto): app de Windows, Android en varios teléfonos (Samsung S25 Ultra, Pixel 7 Pro…),
  jams en red local, escáner QR, jam por internet abierto desde el cel.
- **Solo en el emulador o con scripts**: Mis dispositivos (dos procesos en la misma PC y la interfaz en el navegador: vincular, código equivocado, playlists, Me gusta, categorías, historial, copiar canciones en los dos sentidos, borrar), controles de reloj (con `cmd media_session dispatch`), links en Android, eliminar canciones,
  tiempos de streaming, streaming progresivo (en Chromium con la red frenada), retomar la sesión y el Play del widget con la app cerrada.
- **Sin probar todavía (cambios sin publicar, 10 nov 2026)**: **todo lo de Android Auto**: el Kotlin nuevo (`AndroidAuto.kt`, `ServicioMedios` como MediaBrowserService) se escribió sin poder compilarlo; falta `npx tauri android build` y probarlo con el Desktop Head Unit (DHU) o un coche, con la app abierta y cerrada. De importar playlists se probó el núcleo con `scripts/probar_importar_auto.py` (orden, actualizar, árbol de Android Auto) y la interfaz compila (`vite build`, `svelte-check`), pero no se ha importado un link real.
- **Sin probar todavía**: links y "una sola ventana" en Windows, panel de medios de Windows, un reloj real, un jam con YouTube Music entre teléfonos reales, videos musicales y carpetas de la biblioteca en el cel, lo de 1.0.8 (segundo plano, ecualizador, editar etiquetas) en teléfonos reales, y de 1.0.9: exportar a una USB real y todo en la app de Windows (se probó en navegador con el núcleo de Python y en el emulador: menú, compartir de Android, jalar para actualizar, idioma); de 1.0.10, el volumen arriba de 100 % con música real; de 2.0.1, el widget y quitar de recientes en teléfonos reales (en el emulador sí: sigue sonando, controles, reabrir, atrás, reiniciar para el QR) (la curva y el limitador se midieron en Chromium con señales de prueba); de 3.1.0, la burbuja con dos monitores o con escalado distinto de 100 % (se probó en un monitor de 3440×1440); de 3.2.0, el horizontal en teléfonos reales con muesca o bordes curvos (se probó en el navegador y en el emulador); de 3.3.0, la carátula de vinilo y CD en el cel y el volumen de la burbuja con música real (se vio en el navegador); de 3.4.0, retomar la sesión y el Play del widget con la app cerrada en teléfonos reales (se revisó el núcleo y la biblioteca en el navegador); Mis dispositivos entre un cel real y la PC (que Android reciba el anuncio UDP con la pantalla encendida, el aviso del firewall de Windows, copiar muchas canciones y quedarse sin espacio).

### Dónde guarda las cosas
| | Windows | Android |
|---|---|---|
| Datos (`biblioteca.db`, `ajustes.json`, `recomendaciones.json`, `sesion.json`, `sesion_posicion.json`) | `%LOCALAPPDATA%\WaveDrop` | `files/wavedrop` de la app |
| Música descargada (por defecto) | `~/Music/Misiccord` | `Android/data/com.wavedrop.movil/files/Music` (o `Music/Misiccord` si se elige) |
| Caché (previas, portadas, yt-dlp, APK de actualización) | `%LOCALAPPDATA%\WaveDrop\cache` | caché de la app |
| `cloudflared` | se baja a `%LOCALAPPDATA%\WaveDrop\bin` la primera vez | dentro del APK (`libcloudflared.so`) |

### Problemas conocidos y siguientes pasos
- El `misiccord-servicio.exe` de Windows (~11 MB) se cuela en el APK por `bundle.resources`; debería ir solo en la config de Windows.
- El APK de teléfonos también trae las librerías `x86_64` del emulador (`libqjs.so`, `libcloudflared.so`): unos 12 MB de más.
- YouTube a veces pide "confirm you're not a bot" en ciertas redes/IPs: hay respaldo de clientes, pero puede volver a pasar si YouTube cambia algo.
- Android puede dormir la app en segundo plano si no hay nada sonando (con música activa la mantiene viva el servicio de medios).
- Lo que Python manda como error (`RuntimeError("…")`) y los textos de las notificaciones de Kotlin siguen solo en español.
- `README.md` todavía es el de la plantilla de Tauri.
- No hay iOS ni macOS (no se ha intentado).

---

## Arquitectura en una imagen

```
Interfaz (Svelte 5, src/)            ──invoke("py")──►  Rust (src-tauri/src/lib.rs)
   ▲  evento Tauri "python"                                 │
   │                                                        ├─ Windows: proceso hijo misiccord-servicio.exe
   └──────── avisos (descargas, jam, medios…) ◄─────────────┤   (python/servicio.py empaquetado con PyInstaller),
                                                            │   JSON por líneas en stdin/stdout
                                                            └─ Android: plugin Kotlin PythonPlugin.kt → Chaquopy
                                                                (Python 3.14 dentro del APK)

Todo el trabajo real vive en Python: python/wavedrop/  (el mismo código en las dos plataformas)
```

- La interfaz **nunca** habla con internet para la lógica de la app: llama `py("funcion", datos)` (`src/lib/api.js`)
  y Python responde. Excepciones a propósito: el cliente del jam habla HTTP directo con el servidor del anfitrión,
  y el buscador de actualizaciones de Android lee la API de GitHub.
- Python avisa cosas asíncronas con `emitir(tipo, datos)` (`api.py`); la interfaz las escucha con
  `alEvento(tipo, f)` (`src/lib/api.js`). En Android también el servicio de medios (Kotlin) mete eventos
  `"medios"` en esa misma cola.

### Agregar una función nueva de punta a punta (receta)
1. Python: función `def mi_cosa(d: dict) -> dict` en `python/wavedrop/api.py` y regístrala en el dict `FUNCIONES`
   (al final del archivo). Siempre recibe y devuelve dicts serializables a JSON.
2. Interfaz: `const r = await py("mi_cosa", { ... })`. Si Python lanza excepción, `py()` lanza `Error` con el mensaje.
3. Si tarda o avanza: `emitir("mi_evento", {...})` en Python y `alEvento("mi_evento", f)` en la interfaz.
4. **No** hace falta tocar Rust ni Kotlin para esto. Solo se tocan para cosas nativas (permisos, servicios, intents).

---

## Mapa de carpetas (qué hace cada cosa)

### `python/wavedrop/` — el núcleo (compartido Windows/Android)
| Archivo | Responsabilidad |
|---|---|
| `api.py` | Punto de entrada único: `despachar()` + `FUNCIONES`. Ajustes, biblioteca, playlists, descargas (`_Gestor`, pool de hilos), jams, eliminar, actualización del APK. |
| `plataforma.py` | Rutas por plataforma (`carpeta_datos/musica/cache`), `es_android()`, herramientas (`ffmpeg`, `deno`), `lib_nativa()` (ejecutables del APK), `archivo_nuevo()` (avisa a MediaStore). |
| `descargas.py` | yt-dlp: leer playlists/links (incluye Spotify y Tidal por scraping de su página embed), `Descargador`, `extraer()` con **respaldo de clientes** si YouTube pide "confirm you're not a bot", reintento si `descargados.txt` bloquea una canción borrada. Sin ffmpeg (Android) etiqueta con mutagen. |
| `explorar.py` | ytmusicapi: búsqueda, álbum, artista, radio, recomendaciones (caché 6 h), `previa()` (descarga completa a caché: **solo respaldo**). |
| `flujo.py` | **Streaming progresivo** de canciones que no tienes: servidor local `127.0.0.1:<puerto>/flujo/<id>?t=<token>` que pasa el audio de YouTube por pedazos (soporta Range) y lo guarda en caché si se escucha completo. Camino rápido con cliente `android_music` sin JS; precarga en segundo plano. `servir()` lo reutiliza el jam. |
| `biblioteca.py` | SQLite: canciones, carpetas, playlists, historial (`eventos`). Álbumes por álbum+artista del álbum. `buscar_existente()` para no descargar dos veces. |
| `jam.py` | Servidor HTTP del jam (solo librería estándar): sala, cola, votos, reacciones, sincronía por reloj, SSE `/eventos` (red local) y sondeo largo `/esperar` (internet), subir canciones de invitados, descubrimiento UDP. |
| `sincronizar.py` | **Mis dispositivos**: vincular (Diffie-Hellman con el código), anunciarse/escuchar por UDP 47475, servidor HTTP 47500–47509 con peticiones y respuestas firmadas (HMAC), qué cambió (`refrescar`), fusionar (gana lo más reciente) y copiar canciones. |
| `tunel.py` | Jam por internet: túnel rápido de Cloudflare (`cloudflared`). Windows lo baja la primera vez; Android lo trae en el APK. Job Object en Windows para que muera con el servicio. |
| `letras.py` | LRCLIB (letra sincronizada) con `.lrc` junto al archivo. **Nunca** imprimas ni registres letras en logs/salidas. |
| `musicbrainz.py` | Completa álbum/año/pista/portada al descargar. |
| `etiquetas.py` | Ver y editar etiquetas y carátula de una canción descargada (mutagen: mp3, m4a, flac, ogg/opus). La interfaz manda la imagen ya pasada a JPG. |
| `romanizar.py` | Idioma de una letra (por escritura y palabras comunes) y romanización **sin internet**: coreano, japonés (kanji con `pykakasi`), cirílico, griego. Chino no (necesita diccionario). |
| `idioma.py` | Idioma de lo que Python le manda a la interfaz (títulos de recomendaciones, avisos de segundo plano): `t("texto")` con su traducción en `_EN`. |
| `exportar.py` | PC: memorias USB conectadas (`GetDriveTypeW`), copiar canciones a una carpeta (con `.m3u8`), archivos al portapapeles (`CF_HDROP`), mostrar en el Explorador. |
| `traduccion.py` | Traducción de letras con **MyMemory** (gratis, sin clave, ~5000 caracteres/día por IP): caché en `cache/traducciones`, líneas repetidas una sola vez. |

`python/servicio.py`: el proceso de escritorio (stdin/stdout en UTF-8 forzado; `print` va a stderr).

### `src/` — interfaz (Svelte 5 con runes: `$state`, `$derived`, `$effect`, `$props`)
- `App.svelte`: arranque, mapa de vistas, mini reproductor, hoja, avisos. Importa `lib/medios.svelte.js` y llama `escucharEnlaces()`.
- `lib/api.js` (`py`, `alEvento`, `src`, `tiempo`) · `lib/estado.svelte.js` (navegación con pila + historial de Android, `ui`, avisos, hojas, descargas) ·
  `lib/reproductor.svelte.js` (dos `<audio>` con fundido seno/coseno, cola, precarga de la siguiente, respaldo si el flujo falla) ·
  `lib/jam.svelte.js` (cliente del jam: SSE o sondeo largo, sincronía, agregar desde cualquier lista) ·
  `lib/medios.svelte.js` (notificación/pantalla bloqueada/relojes en Android; Media Session de WebView2 en Windows) ·
  `lib/enlaces.svelte.js` (links de jam: deep link `misiccord://` y la página `https`) ·
  `lib/eliminar.js` (borrar canciones con confirmación) · `lib/actualizaciones.svelte.js` · `lib/aBody.js` ·
  `lib/idioma.svelte.js` (`t()`, idioma del dispositivo o el elegido) + `lib/textos/en.js` (traducción al inglés) ·
  `lib/menuCancion.js` (el menú de una canción) · `lib/compartir.js` (compartir/exportar) · `lib/jalar.js` (jalar para actualizar) ·
  `lib/escritorio.svelte.js` (lo que suena para la burbuja y la barra de tareas, y sus órdenes) ·
  `lib/sincronizacion.svelte.js` (estado de Mis dispositivos y el link `misiccord://vincular`) · `lib/qr.js` (leer un QR con la cámara: Jams y Mis dispositivos; lo que se ve lo dibuja `componentes/Escaner.svelte`).
- `vistas/`: `Inicio` (con el buscador en vivo `componentes/Buscador.svelte`), `Explorar`, `Biblioteca` (selección para compartir o borrar), `Album`
  (también playlists de YouTube Music), `Artista`, `Playlist`, `MeGusta`, `Estadisticas`, `Jams`, `Descargas`, `Ajustes`.
- `componentes/`: `FilaCancion` (menú ⋯, agregar al jam, eliminar), `Hoja` (menú inferior / ventana en escritorio), `MiniReproductor` (también muestra el jam),
  `Reproductor`, `Cola`, `Ecualizador`, `Visualizador`, `Marquesina` (texto que se desliza si no cabe), `Resumen`, `CompletarDatos`, `Letra`, `Tarjeta`, `Portada` (reintenta si una portada falla), `Icono` (íconos SVG por nombre), `Volumen`, `Navegacion`, `ListaVirtual` (solo dibuja las filas cerca de la pantalla),
  `Burbuja` (la ventana flotante: `main.js` la monta sola con `index.html?burbuja`), `Avisos` (abajo, con acción y barra de avance: `aviso(texto, tipo, { id, duracion, accion, avance })`), `BotonDescarga`, `Paginas`, `InfoCancion`.
- `app.css`: tokens de color, `--margen`, carruseles (`scroll-padding` evita que se "corran"), tamaño de artistas `--artista`.

### `src-tauri/` — Rust y Android
- `src-tauri/src/lib.rs`: comandos `py`, `permiso_archivos`, `instalar_apk`, `medios`, `burbuja`, `barra_tareas`; plugins; arranque/cierre del servicio en Windows;
  puente de eventos en Android; módulo `burbuja` (la ventana flotante). `src-tauri/src/barra.rs`: botones de la vista previa de la barra de tareas (solo Windows).
- `tauri.conf.json`: versión (la pone `publicar.ps1`), updater, deep-link `misiccord`, NSIS por usuario. `capabilities/{default,desktop,mobile}.json` (sin BOM).
- `gen/android/` **está editado a mano y versionado** (no es desechable):
  - `app/src/main/java/com/wavedrop/movil/PythonPlugin.kt` (llamar Python, eventos, permisos, instalar APK, medios) y `ServicioMedios.kt` (servicio en primer plano + MediaSession, y MediaBrowserService de Android Auto).
  - `AndroidAuto.kt`: `Nucleo` (Python desde Kotlin, también sin interfaz; PythonPlugin lo usa) y `ReproductorAuto` (MediaPlayer para cuando Android Auto toca con la app cerrada). `res/xml/automotive_app_desc.xml` + `meta-data` del manifiesto: Misiccord es app de música para Android Auto.
  - `WidgetMisiccord.kt` + `res/layout/widget_misiccord.xml` + `res/xml/widget_misiccord.xml`: widget 4×1. `ServicioMedios` lo actualiza solo cuando cambia algo que se ve
    (no con cada avance); sus botones van al servicio igual que los de la notificación, menos Play, que va a `ReanudarWidget.kt` (Activity invisible). Recuerda la última canción (preferencias `widget` y `widget_portada.jpg`);
    con la app cerrada anterior y siguiente solo la abren (Python vive dentro de ella). Textos en `res/values/strings.xml` y `res/values-en/`.
  - `app/src/main/AndroidManifest.xml` (permisos de archivos, cámara, servicio de medios, FileProvider, intent-filter `misiccord`).
  - `app/build.gradle.kts` (Chaquopy, Python 3.14, paquetes pip, ABIs, firma, `androidx.media`).
  - `app/misiccord.pro` (reglas R8: **sin ellas el lector QR truena**, ver abajo).
  - `buildSrc/.../RustPlugin.kt` (solo `arm64-v8a` y `x86_64`).
  - `app/src/main/jniLibs/<abi>/libqjs.so` y `libcloudflared.so`: **no están en git** (los `.so` se ignoran); genéralos con
    `compilar_qjs.ps1` y `compilar_cloudflared.ps1` antes de tu primer build de Android (ver Comandos).

### Otros
- `scripts/`: `publicar.ps1` (publica una versión), `construir_servicio.py` (PyInstaller del servicio de Windows), `compilar_qjs.ps1`, `compilar_cloudflared.ps1`, `crear_icono.py`, `probar_importar_auto.py` (prueba sin red de importar playlists y del árbol de Android Auto; necesita ffmpeg).
- `web/`: código de la página de los links de jam. **Se publica en la rama `gh-pages`** (GitHub Pages → `https://accor-dium.github.io/misiccord/jam/`), no desde `main`.
- `firma/` (**privada, en .gitignore**): llave del APK (`misiccord.jks`, `keystore.properties`) y del updater (`actualizaciones.key(.pub)`, `actualizaciones.properties`). Nunca la subas, la imprimas ni la copies.
- `publicar/vX.Y.Z/`: lo que se subió a cada Release. `servicio-dist/`: salida de PyInstaller (generada).

---

## No cambiar (aunque parezca mejora)

- **Identificadores**: `identifier` = `com.wavedrop.movil` (cambiarlo = otra app; se pierden datos y actualizaciones), carpeta de datos `%LOCALAPPDATA%\WaveDrop`,
  claves de `localStorage` (`wavedrop_nombre`, `wavedrop_volumen`, `misiccord_ultima_revision`, `misiccord_idioma`, `misiccord_orden`, `misiccord_volumen_escala`, `misiccord_vista_biblioteca`, `misiccord_burbuja_posicion`), esquema `misiccord://`, URL de la página
  `https://accor-dium.github.io/misiccord/jam/` (está en `lib/enlaces.svelte.js` y en `api.jam_qr`: cambia las dos o ninguna), repo `Accor-Dium/misiccord`.
- **Llaves de firma**: si cambia la del APK, Android no deja actualizar encima; si cambia la del updater, las PCs instaladas no aceptan versiones nuevas.
- **Python 3.14 + Chaquopy 17.2** y **solo ABIs arm64/x86_64** (Chaquopy no compila 3.14 para armeabi-v7a).
- **`yt-dlp>=2026.10.26` + `yt-dlp-ejs`**, nunca `yt-dlp[default]` (pip resolvía una versión de 2021).
- **QuickJS en Android, deno en Windows** como motor de JS de yt-dlp (`plataforma.js_runtimes`). En Android no hay ffmpeg: se baja m4a/opus tal cual.
- **Cliente `android_music` sin JS** como primer intento en `flujo.py`: en el cel el JS por QuickJS tarda ~10 s por canción. Saltarse la página
  (`player_skip=webpage`) **provoca** "confirm you're not a bot": no lo actives.
- **Canciones de un invitado en un jam (`api.jam_mandar`)**: en la red local **no se copian al anfitrión**. El invitado las sirve desde su
  dispositivo (`jam.compartir`: servidor propio en 47510–47519, `/pista/<token>` y `/portada/<token>`, el token es el permiso) y el anfitrión
  las reenvía por `/audio/<pid>` con Range (`_reenviar`); antes de aceptarla comprueba que alcanza al invitado (`_alcanzar_invitado`, 3 s).
  Por internet o si no lo alcanza (firewall, túnel) se sube completa como antes (`/subir`). El invitado deja de servirlas al sonar o salir
  de la cola (`soltarCompartidas` → `jam_dejar`) y al salir del jam; si se va, el anfitrión quita las suyas pendientes (`quitar_directas`)
  y si deja de responder la salta (`fallo_directa`). En Android la tarea de fondo `jam_compartir` evita que se duerma mientras tenga alguna.
  Unirse o crear un jam pide antes el permiso Dispositivos cercanos (`permisoRed`, Android 17).
- **SSE solo en red local; sondeo largo `/esperar` por internet**: los túneles rápidos de Cloudflare no pasan SSE. El SSE va en HTTP/1.1 chunked a propósito.
- **Seguridad del jam**: código de 4 dígitos + bloqueo tras 8 intentos fallidos por origen (`CF-Connecting-IP` por el túnel). No quites el límite.
- **`allow_reuse_address = False` en Windows** (`jam.py`): si no, dos jams comparten puerto y se roban conexiones.
- **Reglas R8 de `misiccord.pro`** (ML Kit, CameraX, Firebase components): sin ellas, en release el escáner QR cierra la app con el primer cuadro.
- **`use:aBody`** en ventanas/barras flotantes: `<main>` tiene `view-transition-name` (crea su propia capa) y nada adentro puede quedar encima de la barra.
- **Plugins con `#[cfg(desktop)]` / `#[cfg(mobile)]`** en `lib.rs` (updater y single-instance solo escritorio; barcode solo móvil) y permisos en la capability de su plataforma.
- **Borrar = de todos lados** (`api.eliminar_canciones`): archivo, biblioteca, playlists, historial, cola (y su `sesion.json`, por `olvidarRutas`), jam, MediaStore y carpetas vacías. Si agregas otro lugar donde
  viva una canción, agrégalo ahí también.
- **Video (ajustes `video_ver` y `video_descargar`, ambos apagados por defecto)**: el `<video>` va mudo y sigue al `<audio>` (`reproductor.svelte.js`). El clip se busca con
  `explorar.buscar_video` porque el id de la canción en YT Music suele ser audio con la portada. El video descargado es `<canción>.mp4` junto al audio
  (`.mp4` no está en `biblioteca.EXTENSIONES`: así no se toma por canción) y `eliminar_canciones` lo borra también. Para **transmitir** solo sirve el cliente
  `android` de yt-dlp (mp4 360p por rangos); tv/web dan más calidad pero YouTube responde 403 sin token (`flujo._extraer_video` prueba cada candidato).
  **El audio espera al video** (`retenido`, `alinear`): al empezar una canción con el video prendido no suena hasta que su video puede ir con ella (si en 10 s no llega, sigue sola: `sinEsperar`);
  al adelantar, al prender el video a media canción o si el video se queda cargando (`waiting`), el audio se pausa, el video salta a donde va y arrancan juntos.
  Antes el video saltaba solo y, como en un clip transmitido el salto tarda 1–2 s, llegaba tarde y volvía a saltar sin alcanzar nunca al audio. Diferencias de menos de 0.5 s
  se corrigen con `playbackRate` del video (±10 %). Mientras espera, `rep.sonando` sigue diciendo lo que quiere el usuario (la pausa de esperar no cuenta como pausa) y `rep.cargando` muestra el círculo.
  `buscar_video` elige el clip con la duración más parecida a la canción: uno con intro empezaría desfasado aunque la sincronía sea perfecta.
- **Letra (`Letra.svelte`)**: el espacio arriba y abajo de la letra son divs medidos en px con el alto real de la caja. Con `padding` en vh la caja
  crecía más que su lugar y en el cel tapaba la barra para adelantar (tocabas una línea en vez de la barra). Y `scrollTo` en la caja, no `scrollIntoView`
  (ese movía al reproductor entero).
- **Columnas de la cuadrícula** (`misiccord_columnas`): con el cel acostado se guardan aparte (`canciones:h`), así no hay que cambiarlas al girarlo.
- **Biblioteca**: buscar, ordenar y agrupar es todo en la interfaz (`lib/ordenar.js`, sin acentos, "The" ignorado); solo lo que no tienes se pide a
  YouTube Music. El orden elegido vive en `localStorage` (`misiccord_orden`).
- **Abrir Biblioteca debe ser instantáneo** (con 1,671 canciones llegó a tardar ~9 s en un cel simulado). Cuatro cosas lo sostienen:
  - **Listar no toca los archivos**: la portada está en la columna `canciones.portada` (ruta en la caché, `""` si no trae, `NULL` si falta buscarla). `api._completar_portadas`
    llena las que falten después de cada escaneo y `revisar_portadas` recupera las que Android borre de la caché. No regreses `portada_local()` a `_local()`: abre el archivo de cada canción (FUSE en Android).
  - **Los datos van fuera de `nav`**: `Biblioteca.svelte` los guarda en `memoria` (`<script module>`, `$state.raw`). En `e.datos` cada canción se vuelve un Proxy (`nav` es estado profundo).
  - **`ListaVirtual`**: las filas de un mismo `tipo` deben medir igual. Mide una sola vez por ancho: los textos en otros alfabetos usan otra fuente y cambian el alto 1 o 2 px,
    y medir con cada fila que entra crea un ciclo infinito entre listas (`effect_update_depth_exceeded`). Encabezados y `.ancla` siguen en el DOM: por eso funcionan `sticky` y el índice A–Z.
  - **El aviso `"biblioteca"` trae `sin_cambios`** si el escaneo no encontró nada: si no, cada arranque volvía a pedir y dibujar todo.
- **La cola es el orden real** (`rep.cola`): con aleatorio se baraja de verdad (`mezclar`) y `original` guarda el orden para regresar a él. Nunca elijas la siguiente al azar
  al momento: "A continuación" (`Cola.svelte`) debe decir lo que va a sonar. La que suena va hasta arriba; lo anterior se ve con "Ver las anteriores".
- **Álbum y artista: primero lo local** (`artista_local`, `album_local_buscar`): sale al instante y funciona sin internet; lo de YouTube Music se agrega después y sus errores no se muestran si ya hay algo tuyo.
- **Qué le falta a un álbum (`api.album_faltantes`)**: lo de YouTube Music se guarda 7 días en la caché (`albumes/`), qué tienes se calcula siempre y el botón Actualizar manda `forzar`. La interfaz corta a los 30 s: una red que no responde se veía como un álbum completo.
  `_album_igual` exige el mismo artista ("Greatest Hits" tiene cientos) y compara también sin edición (`biblioteca.nombre_album`: "Deluxe", "Remastered", solo al final para no tocar "1989"). Dentro de tu álbum basta el título: la pista puede decir "Queen, David Bowie" y tu archivo "Queen".
- **Historial** (`vistas/Historial.svelte`, `historial`): cada reproducción (tuya o en línea, `eventos` con `yt:<id>`), por día; "Escuchado recientemente" de Inicio sale de ahí sin repetir y lleva a "Ver historial". Las búsquedas recientes se guardan en el dispositivo (`misiccord_busquedas`, 15) al darle Enter o abrir un resultado, y salen al tocar la caja vacía.
- **Radio al tocar en Inicio y en la búsqueda** (`reproducirConRadio`): una canción de Para ti / recomendaciones / secciones / resultados de YouTube Music suena y detrás su radio de YouTube Music (50), como YouTube Music; "Reproducir todo" sigue tocando la sección.
- **Romanización** (`romanizar.py`): también árabe, hebreo y tailandés, por tablas y aproximada (no escriben las vocales cortas y el tailandés no separa palabras); sin librerías, para que sirva en Android.
- **Discos de YouTube Music con videos** (`explorar._solo_audio`): `get_album` trae algunas pistas como el video oficial (`MUSIC_VIDEO_TYPE_OMV`: Sugar de V dura 5:02 con su intro; la canción, 3:56). Se cambian por la pista de la lista de audio del disco (`audioPlaylistId`), que trae las mismas en el mismo orden ya como canción. Lo guardado antes de eso (`albumes_yt`, `discos`, `albumes`) se dejó de leer: ahora son `albumes_audio`, `discos_audio` y `faltantes_audio`.
- **Todas las canciones de un artista** (`vistas/ArtistaCanciones.svelte`): una sola vista, como en Musicolet (tira de álbumes arriba que filtra la lista, conteos con duración, buscador fijo abajo), para los dos "Ver todas" del artista: el de "En tu biblioteca" abre `soloTuyas` (sin internet) y el de "Populares" lo tuyo con la discografía. Cada disco de la discografía se pide entero con `disco_canciones` (4 a la vez, guardado 7 días), para que Thriller salga con las suyas y Thriller 40 con las suyas aunque se repitan. Por disco salen todas las pistas como en su página (un video puede ser dos pistas: la fila lleva `claveFila`); en las otras vistas cada grabación sale una vez. La lista `songs.browseId` (`artista_canciones`) no sirve para esto: trae una versión de cada canción repartida entre ediciones (Rubber Soul Super Deluxe salía con 4 de 68); solo se usa si no hay discografía. El buscador y el orden (`misiccord_orden_artista`) van en la interfaz, sin volver a internet.
  Lo tuyo que YouTube Music no tenga se suma. Esa lista no trae año: sale de la discografía por el nombre del disco, y lo que no aparezca ahí va al final.
- **En el artista, "Tienes 3 de 15"** cuenta discos, sin sencillos. `explorar._discografia` pide la lista completa porque `get_artist` solo trae los primeros 10.
- **Fuentes de datos**: YouTube Music primero (de ahí escuchas y descargas: el disco debe llamarse igual que en la app) y MusicBrainz de segunda, en los tres lugares: al descargar (`_etiquetar_descarga`: álbum, año, pista y portada del disco de YouTube Music en que sale la canción; MusicBrainz solo pone el género, o todo si no está en ningún disco), en Editar álbum (`album_opciones`, las de YouTube Music arriba con `yt`) y en Completar datos (`metadata_opciones`, con `portada_url`). YouTube Music no trae género ni disco. El disco se encuentra con `_albumes_yt`/`_puesto_album`: mismo artista y el mismo nombre, sin la edición, o las mismas palabras en otro orden ("Greatest Hits: Believers Never Die, Volume Two" es "Believers Never Die - Greatest Hits (Volume Two)"), y entre varios el que menos palabras agregue. **¿Ya la tienes?** (`buscar_existente`: palomita, "ya la tienes" al descargar, Me gusta, Inicio, Jams) cuenta solo tu copia del mismo álbum (`biblioteca.puesto_album`) o la que no dice de qué álbum es: el título sin paréntesis no distingue versiones (Sugar / Sugar (Remix), Call Me / Call Me (Remastered 2001)). Que una grabación idéntica de otro disco se duplique, a Omar no le importa; con un álbum genérico en tus archivos ("Singles") nada coincide.
  **No uses iTunes Search API**: Apple solo permite su carátula y vistas previas para promover su tienda, junto a su insignia, y sus términos no cubren apps independientes. **Tampoco Deezer** (uso privado y familiar) ni **Discogs** (pide token, y uno dentro del APK se puede sacar).
- **Ecualizador en el reproductor** (`Ecualizador.svelte`): 3, 5, 10, 15 o 31 bandas; cuántas hay lo dice el largo de `eq_bandas` (`convertirBandas` interpola al cambiar). Mono es `channelCount = 1` en el primer nodo.
  Mono y los visualizadores (`Visualizador.svelte`, `analizadorDeAudio`) también arman el grafo de Web Audio.
- **Completar datos** (`CompletarDatos.svelte`, `metadata_opciones`): primero hasta 3 discos de YouTube Music en que sale la canción; después, de `musicbrainz.opciones`, una opción por grupo de MusicBrainz, primero su edición más antigua (si no, Thriller salía de 2022). Respeta el límite de 1 consulta por segundo de `_get`.
- **Editar álbum** (`EditarAlbum.svelte`, `musicbrainz.buscar_albumes/album_detalle/emparejar`): las opciones van por edición (no por grupo) porque cambian las pistas. Solo es "exacta" si coinciden
  todas las letras (`_letras`); `normalizar` ignora paréntesis y "(en vivo)" pasaría por exacta. Las canciones que se dejan fuera no se tocan y siguen a `completarDatos`.
- **Carátulas como objeto** (ajuste `caratulas`, `ui.caratulas`, `Portada.svelte`): estuche de CD, vinilo o cassette solo con CSS, en lo grande (`objeto`: `Tarjeta`, álbum, reproductor, jam); en listas se quedan normales porque a 46 px es ruido.
  El cuadro sigue siendo cuadrado aunque el estuche no lo sea: las rejillas cuentan con eso. Con `giro` (true/false) el vinilo es el disco entero y la carátula su etiqueta (el brillo no gira), y en el cassette giran los carretes. El cassette grande lleva etiqueta como los japoneses (`etiqueta`: portada grande en la esquina izquierda, con la ventana encima de su esquina, canciones con su duración arriba a su lado, artista y álbum abajo, lado y año a la derecha) del color que más se repite en las orillas de la portada (`lib/colorPortada.svelte.js`, necesita CORS: las de yt3 se piden a lh3). En el reproductor la etiqueta trae el álbum como "Ir al álbum": lo tuyo si es local, el de YouTube Music si es en línea (una vez por álbum y solo con el cassette puesto), nunca lo que sigue en la cola. En una tarjeta chica no se leería y la portada es la etiqueta.
  En la lista de álbumes de Biblioteca cada fila es el lomo (`Costilla.svelte`): el color es una franja de la carátula. Cada estilo mide distinto, por eso su `tipo` de `ListaVirtual` también.
- **Sesión de reproducción** (`guardar_sesion`, `restaurarSesion`): en archivos de Python y no en `localStorage`, que tarda segundos en llegar al disco y pausar y cerrar de inmediato la perdería.
  La cola se escribe al cambiar y la posición aparte (al pausar, cada 10 s y al salir de la app). No guardes `fuente_previa`: es una dirección del flujo local que ya no sirve al reabrir.
  Al abrir no se carga el audio hasta darle play (`retomar`): una canción en línea pediría internet con solo abrir la app. Si la canción ya no se puede oír se brinca a la siguiente, con tope de una vuelta a la cola (`saltos`).
  `medios.svelte.js` no manda nada antes de `rep.sesionLista`: el "no hay canción" del arranque borraría la que recuerda el widget. La canción restaurada ya tiene notificación en pausa, por eso los audífonos también la retoman.
- **Play del widget (`ReanudarWidget.kt`)**: es una Activity y no el servicio porque un servicio no puede abrir la app desde segundo plano, y el widget no se entera de que la app se cerró (su botón sigue igual).
  Si `Medios.eventos` existe la app está viva y es un Play normal; si no, abre la app con `Medios.playAlAbrir` y la interfaz lo pregunta al arrancar (`revisarWidget`). Si `ReproductorAuto` está sonando (Android Auto con la app cerrada), el Play es para él.
- **Android Auto (`ServicioMedios.kt`, `AndroidAuto.kt`, `api.auto`)**:
  - `ServicioMedios` es un `MediaBrowserServiceCompat` **exportado** con la misma MediaSession de siempre. Android Auto lo enlaza aunque la app esté cerrada. Qué ve cada quien lo decide `onGetRoot`: tu música solo Android Auto, el Asistente y la propia app (`CONFIABLES`); a los demás se les da la raíz `"vacio"` (pueden controlar lo que suena, nada más). No lo abras a todos.
  - Las listas salen de **`api.auto`** y nada más: carpetas (`playlists`, `album:["nombre","grupo"]`, `artista:<nombre>`, `buscar:<texto>`…) y canciones `"<carpeta>#<n>"`. Al tocar una, la interfaz (`tocarDeAuto` en `medios.svelte.js`) o `ReproductorAuto` vuelven a pedir esa carpeta y tocan la `n`: por eso el número siempre es la misma canción. Se corta en el **último** `#` (un álbum puede llevar `#`). La raíz tiene 4 hijos a propósito: Android Auto los enseña como pestañas y no caben más.
  - **Sin interfaz** (`Medios.eventos` null: Android Auto arrancó solo el servicio) nada toca en la WebView, así que todo lo atiende `ReproductorAuto` (MediaPlayer, foco de audio, historial, sesión). `Nucleo.llamar` inicia el núcleo de Python como la interfaz si nadie lo ha hecho (idioma del teléfono). Al abrir la app, `PythonPlugin` llama `ReproductorAuto.entregar()`: guarda la sesión con el mismo formato que `guardarCola` y, si sonaba, `Medios.playAlAbrir` hace que la interfaz siga. `ReproductorAuto` no baraja ni repite (ponytail: se agrega si hace falta).
  - Android Auto vive en otra app: las portadas de las listas van como `content://` del FileProvider (`file_paths.xml` incluye `files/wavedrop` por las fotos de artistas y playlists) con `grantUriPermission` a quien navega. Las de internet no salen en las listas (sí en lo que suena: va como imagen).
  - Enlazado por Android Auto el servicio existe sin primer plano (`enPrimerPlano`): al empezar a sonar pasa por `startForegroundService`, y si deja de haber algo, `quitar()` le quita la notificación (enlazado no se destruye).
  - La cola que ve el coche: la interfaz manda la que suena y las 29 siguientes (`cola` como JSON e `indice` en el comando `medios`); cada una es un `QueueItem` con id = su lugar en `rep.cola`.
  - **Android Auto solo enseña apps de la Play Store** salvo que en Android Auto → Ajustes → (tocar 10 veces "Versión" para ser desarrollador) → menú ⋮ → Ajustes de desarrollador → **Fuentes desconocidas**. Misiccord se instala desde GitHub: sin eso no aparece en el coche (solo se ve "qué suena" por la notificación).
  - `ACTION_AUDIO_BECOMING_NOISY` (se desconectan el coche o los audífonos) pausa con `Medios.avisar("pausa")`, haya interfaz o no.
- **Importar playlists (`api._importar`, `_a_la_playlist`)**: las playlists de la app solo tienen canciones descargadas, así que importar = bajar lo que falte y que cada una entre en cuanto está, en el orden del original (las que agregaste tú van al final; repetida en el original, entra una vez). Las que ya tenías entran al momento.
  La playlist recuerda su link en `playlists.origen` (normalizado por `_origen`: sin el `?si=` ni `/intl-es/` de Spotify; en YouTube solo cuenta `list=`, en cualquier dominio): importarlo otra vez actualiza esa misma, no crea otra. No se borra de la playlist lo que el original ya no tenga.
  En Descargas la casilla "Guardarla también como playlist" viene puesta salvo en links de álbum (`/album/`, `list=OLAK5uy_`). Prueba: `scripts/probar_importar_auto.py`.
- **Categorías** (`lib/categorias.js`, `vistas/Categoria.svelte`): se deducen en la interfaz del género, el álbum y las 3 carpetas más cercanas al archivo, no de toda la ruta ("C:\Users\Anime Fan\…"). No se tocan las etiquetas.
  Gana lo que hizo el usuario: `categorias_canciones`, luego `categorias_albumes` y al final lo deducido más los géneros sumados en la tabla `categorias`. Esa tabla guarda las creadas y los cambios a las de la app, que no se borran: se ocultan (`oculta`), porque sus reglas siguen en el código.
  Las décadas son categorías más (id `d1980`): salen del año, pero se renombran, se llenan y se vacían igual. Lo corregido a mano sin ninguna década conserva la de su año; por eso sacar una canción de su década guarda `sin-decada`.
  Cada tarjeta lleva `data-categoria` (`d1980`, `anime`…): ahí va el diseño propio de cada una.
  "Soundtrack" es de películas y series: lo de videojuegos o anime no sale ahí. Las reglas corren una vez por canción (`WeakMap`): filtrar 1,500 tarda ~14 ms.
- **Fotos de artistas** (`lib/fotosArtistas.svelte.js`, `api.artista_foto`): mientras no haya, se usa una carátula suya (`artistas()` ya la trae, sin red). Solo se piden las de filas dibujadas, de una en una, y se detienen con una canción en línea sonando, en segundo plano o, en el cel, fuera de Wi-Fi (`navigator.connection.type`).
  Sin esos frenos serían cientos de consultas a YouTube Music con solo abrir la pestaña. Van en `datos/artistas`, no en la caché, y el nombre debe ser idéntico al de YouTube Music: mejor un ícono que la foto de otro. Sin foto se revisa otra vez a los 30 días.
- **Playlists**: la carátula propia va en `datos/playlists/<id>-<fecha>.jpg`; el nombre cambia con cada una porque la interfaz guardaría la vieja. Sin propia se usa la de alguna canción.
- **Pestaña Carpetas** (`lib/carpetas.js`): el árbol sale de las rutas de `b.canciones`, sin tocar el disco.
- **Resumen** (`lib/resumen.js`, `Resumen.svelte`): el último día del mes, trimestre o año avisa una vez por periodo (`misiccord_resumen_visto`); lo más grande gana (31 de diciembre = año).
- **Reproducir estando en un jam pregunta primero** (mandarla al jam o salir/cerrar el jam y escucharla aquí): todo pasa por `reproducir()`,
  y `jam.svelte.js` registra la pregunta con `preguntarAlReproducirEnJam` (el reproductor no importa al jam: el jam ya importa al reproductor).
  Si agregas otra forma de empezar a sonar, que pase por `reproducir()` o respete `{ aunEnJam }`.
- **Me gusta** (tabla `me_gusta`): por `clave` artista+título normalizados, así sirve para descargadas y vistas previas. Guarda el id de YouTube Music
  (si es tuya y no lo trae, se busca en segundo plano) para poder escucharla o descargarla aunque borres el archivo.
- **Ecualizador (Web Audio)**: el grafo se arma solo la primera vez que se prende (`aplicarEcualizador`); entonces los `<audio>` llevan `crossOrigin`
  y todo lo que suena **debe mandar CORS**: el protocolo asset de Tauri ya lo hace y `flujo.py` manda `Access-Control-Allow-Origin: *`. Si agregas otra
  fuente de audio sin CORS, con el ecualizador prendido sonará en silencio. Los jams usan su propio `<audio>` y no pasan por él.
- **Romanización de japonés (`pykakasi`)**: lee palabra por palabra, no entiende la frase: las lecturas equivocadas que más salen en canciones van en `romanizar._LECTURAS`.
  Se importa dentro de la función (su diccionario pesa 10 MB) y si falla se romaniza solo lo que no tenga kanji: un error ahí nunca debe dejarte sin letra. En Android necesita `extractPackages("pykakasi")`.
- **Traducción de letras**: el endpoint no oficial de Google (`translate_a/single`, cliente `gtx`) respondía 429 con captcha: no lo uses. Se usa MyMemory (`traduccion.py`).
- **Historial (`eventos`)**: las vistas previas también se cuentan, con ruta `yt:<id>` (y `duracion`/`portada`, columnas agregadas por migración). Las
  consultas que hacen JOIN con `canciones` (recientes, más escuchadas) las excluyen solas; `estadisticas()` y `semillas()` sí las usan.
- **Segundo plano en Android**: sin un servicio en primer plano Android congela la app al apagar la pantalla (`ServicioMedios` solo la cubre mientras suena música).
  Python anota los trabajos largos (descargas, video, APK de actualización, leer una carpeta, jam abierto) con `api._fondo_actualizar` y manda un resumen
  con el evento `"fondo"`; `PythonPlugin.Emisor` lo lee **directo** (no por la interfaz, que Android pausa) y `ServicioTareas.kt` (tipo `dataSync`, con
  WakeLock y notificación de avance) lo muestra. Una tarea nueva se anota **antes** de quitar la anterior (p. ej. el video antes de dar la canción por lista):
  Android 12+ no deja volver a arrancar un servicio en primer plano desde segundo plano, así que un hueco de "0 tareas" lo apagaría para siempre.
  Los permisos (notificaciones, sin límites de batería) se piden con el comando `segundo_plano` y se ven en Ajustes → Segundo plano (solo Android).
- **YouTube Music en el idioma de la app solo para mostrar** (`explorar._yt_idioma`: inicio, estados de ánimo, explorar, playlists). Las búsquedas
  usan el cliente sin idioma (`_yt`): ytmusicapi reconoce cada resultado por su texto en inglés y con `language="es"` los filtros (canciones, álbumes) regresan vacíos.
- **Tidal (`descargas._leer_tidal`)**: se lee `embed.tidal.com/<tipo>s/<id>` (canciones en `window.tidalMediaSessionMetadata`, orden y duración en
  sus `<list-item>`); el nombre y el total salen del JSON-LD de `tidal.com/<tipo>/<id>`. La página no dice su charset: se decodifica como UTF-8 a mano.
  Solo trae 50 canciones: `Coleccion.total` avisa cuántas faltan. **No** uses la API interna del reproductor web de Tidal (pide un token suyo).
- **Géneros de YouTube Music** (`explorar.playlists_de_estado`): `get_mood_playlists` de ytmusicapi solo sirve para los estados de ánimo; en los géneros
  truena ("Unable to find navigationEndpoint") porque vienen en secciones. Ahí se leen con `parse_mixed_content` (`_estado_por_secciones`).
- **Compartir en Android** pasa por `FileProvider` (`res/xml/file_paths.xml` incluye `/storage` para tarjetas SD) con `ClipData`: sin ella WhatsApp no recibe
  permiso para leer todos los archivos.
- **Volumen (`reproductor.svelte.js`)**: `rep.volumen` es la **posición de la barra (0–2)**, no la amplitud: `gananciaDe()` la pasa a decibeles
  (+10 dB = el doble de fuerte: 50 % = −10 dB, 100 % = el archivo tal cual, 200 % = +10 dB). El `<audio>` da hasta 1 y lo de arriba lo pone el nodo
  `refuerzo` del grafo de Web Audio (el mismo del ecualizador, que se arma al subir de 100 %), seguido de un limitador (−1.5 dB) y un recorte suave tanh,
  sin sobremuestreo (con "2x"/"4x" el filtro rebota y pasa de 0 dB); los dos solo actúan con refuerzo. `wavedrop_volumen` antes guardaba la amplitud:
  `misiccord_volumen_escala = "2"` marca que ya se convirtió. El audio de los jams usa la misma curva, pero sin refuerzo (tope 100 %).
- **Mis dispositivos (`sincronizar.py`, `componentes/MisDispositivos.svelte`)**:
  - **Sin nada vinculado no escucha nada en la red**: el servidor y el anuncio UDP solo arrancan al vincular (o al abrir Vincular). En Windows ahí sale el aviso del firewall, igual que con el jam.
  - Vincular: los dos tocan Vincular; uno elige al otro en "Cerca de ti" y escribe su código (o lo escanea: el QR es `misiccord://vincular?…` con la huella de su llave). Diffie-Hellman del grupo 14 de RFC 3526 con firmas hechas con el código; el secreto sale de ahí y **nunca viaja**. Vive en `datos/sincronizacion.json` (id, nombre y cada vinculado con su secreto): no lo registres ni lo imprimas.
  - Cada petición va firmada (`X-Sinc-Id/Hora/Firma`, HMAC del método, la ruta, la hora y el hash del cuerpo) y cada respuesta JSON también: si no, cualquiera en la red podría hacerse pasar por el otro. Las canciones van sin hash del cuerpo (son grandes).
  - **Qué cambió no se anota en cada lugar que edita**: `refrescar()` compara cómo está todo (`_proyeccion`) con la huella de `sinc_registros`; lo distinto es un cambio de aquí (`mod` = ahora) y lo que desapareció queda `borrado`. Si agregas algo sincronizable, súmalo a `_proyeccion` y a `_APLICAR`.
    `mod` decide quién gana; `cambio` (hora local) decide qué falta mandarle a cada dispositivo (`enviado_hasta`/`recibido_hasta`): con tres dispositivos, lo que llegó de uno también debe pasar al tercero.
  - Lo que depende de una canción que todavía no llega (su lugar en una playlist, su categoría) se guarda completo y se vuelve a aplicar al llegar (`_reaplicar_pendientes`); por eso una categoría sin su canción no cuenta como borrada.
  - Las canciones no pasan por "gana lo más reciente": cada quien ve la lista del otro y manda lo que le falta, menos lo que el otro borró (`tumbas`). Las playlists se identifican por `playlists.uid` (columna agregada por `sincronizar`); dos con el mismo nombre de antes de vincular se vuelven una.
    `sinc_recibidas` guarda con qué clave llegó cada una: si sus etiquetas dan otra, no se vuelve a pedir. Se deja de recibir con menos de 500 MB libres.
  - Solo inicia uno (I) y el otro responde: basta con que uno alcance al otro. Si los dos empiezan a la vez, uno contesta "ocupado" (409) y lo intenta luego; una sesión sin peticiones por 2 min se da por abandonada (`/sinc/soltar` la suelta de inmediato).
  - El historial solo crece (`evento_ultimo` marca hasta dónde se revisó). Lo de una canción que llegó antes que ella va con ruta `sinc:<clave>` y se corrige al llegar.
  - Para probar sin dos equipos: dos procesos de Python con carpetas distintas en la misma PC (cada uno toma otro puerto) y `vincular_con("127.0.0.1", puerto, código)`.
  - **Android 17+ (targetSdk 37) bloquea la red local** sin `ACCESS_LOCAL_NETWORK` ("Dispositivos cercanos"): las conexiones a la Wi-Fi fallan como si el otro
    no existiera. `PythonPlugin.redLocal` / comando `red_local` lo pide; `permisoRed()` (sincronizacion.svelte.js) lo llama antes de abrir Vincular o vincularse
    y, si ya se negó, ofrece abrir los ajustes de la app. En Python un `PermissionError` al conectar es justo eso.
  - El QR lleva **todas** las IPs de quien lo muestra (`ip` + `ips`): una PC con VPN o Tailscale tiene varias y la primera puede no ser la de la Wi-Fi.
    `_alcanzable` prueba `/sinc/hola` en todas a la vez y se queda con la que conteste (o da un error claro en ~4 s).
  - `HTTPServer.server_bind` llama `getfqdn()`, que en una PC con VPNs tarda ~12 s: `_Servidor` (aquí y en `jam.py`) lo salta. No lo quites.
  - Mientras se vincula sale una tarjeta "Vinculando con…" encima de todo (tras leer el QR la cámara se cierra sin más y parecía que no pasaba nada).
- **Lector de QR (`lib/qr.js` + `componentes/Escaner.svelte`)**: el escáner nativo va en modo `windowed` (la cámara detrás de la WebView transparente).
  `ui.escaner` muestra Escaner.svelte y pone `html.escaneando`, que vuelve transparentes `html`/`body` y oculta el resto de la app; la sombra del cuadro
  tapa todo menos él. "Cancelar" y "atrás" llaman `cancel()` del plugin.
- **Tocar otra vez la pestaña en la que estás** (`irPestana`, `ui.reinicio`): regresa a la raíz, arriba y sin búsqueda; venir de otra pestaña conserva tu lugar.
- **Regresar a donde estabas**: cada entrada de la pila guarda lo suyo (`scroll`, y `pestana`, `filtro` y `q` en Biblioteca) y `irPestana` conserva la raíz de cada pestaña (`raices`).
  El scroll se guarda **antes** de cambiar de vista (`recordarScroll`): en un `$effect` el contenido ya es otro y el navegador lo recortó, y por eso siempre regresaba arriba. Al volver se insiste hasta 2 s (`App.svelte`) porque lo que llega de Python tarda; tocar la pantalla lo cancela.
- **Ajustes va en `Navegacion`**, no en una vista: así se ve en todas las pantallas y los tres modos. No es pestaña: se abre encima de lo que estés viendo.
- **Artista de un álbum local** (`album_local` → `artista_principal`): el del más común de sus canciones. `artista_local` busca por artista principal exacto y "Varios artistas" o una colaboración no existen como artista.
- **Índice A–Z de Biblioteca**: salta a un `<span class="ancla">` antes de cada encabezado, no al encabezado: los encabezados son `sticky` y uno que ya
  se quedó pegado arriba no deja regresar a él con `scrollIntoView`.
- **Reproductor grande**: deslizar para cerrar no empieza sobre la barra de avance ni el volumen (`tocarInicio`), e `irA()` pone `rep.pos` al instante
  (si no, la barra regresaba un momento a donde iba y parpadeaba).
- **Quitar la app de recientes con música sonando (`MainActivity.kt`)**: Tauri cerraba el proceso al destruirse la Activity. Si algo suena,
  `isChangingConfigurations()` devuelve true en ese `onDestroy` (tao y wry creen que es un giro de pantalla) y la WebView se guarda; al reabrir,
  esa misma WebView se muda a la Activity nueva (Tauri no crea otra porque no conoce ese id). Consecuencias: los plugins siguen ligados a la
  Activity original, por eso `PythonPlugin` abre pantallas con `pantalla` (la visible) y el lector QR pide reiniciar (`sesion` → `reiniciar`)
  si `reanudada`. Si la Activity "mudada" se cierra sin música, se mata el proceso (Tauri no sabría que se cerró).
- **Burbuja flotante (escritorio)**: es otra ventana de Tauri (`burbuja`, la misma página con `?burbuja`) que solo existe con el ajuste prendido y que
  Rust muestra/esconde al minimizar o regresar a la principal (`burbuja::evento`, con `Resized` y `Focused`). No reproduce: la principal le manda
  `burbuja-estado` y ella manda `burbuja-control` (`lib/escritorio.svelte.js`). Por eso no puede usar `Volumen.svelte` (sería otro `rep`, sin música): tiene su propia barra. Para que abrir sea inmediato y suave, la ventana crece de un jalón con
  `SetWindowPos` (moverla y cambiar el tamaño en dos pasos hace brincar el círculo) y la píldora se estira con CSS; al cerrar, primero la píldora y luego
  la ventana. Antes de cerrarse pregunta a Rust si el cursor sigue encima (`dentro`): WebView2 manda `mouseleave` falsos. Al esconderse se cierra en
  círculo (`burbuja-oculta`): abierta, su parte transparente taparía clics. Su posición vive en `localStorage` (`misiccord_burbuja_posicion`) y no se
  guarda la de cuando nace (Windows avisa ese movimiento antes de colocarla). La ventana principal, al cerrarse, destruye la burbuja: si no, la app no terminaría.
- **Barra de tareas de Windows (`barra.rs`)**: `ITaskbarList3::ThumbBarAddButtons` y la ventana principal subclasificada para recibir `WM_COMMAND`/`THBN_CLICKED`
  (llegan como evento `barra-control`). Se vuelven a poner con `TaskbarButtonCreated` (Explorer reiniciado). Los íconos se dibujan en Rust y su color sigue al
  tema de la barra (`SystemUsesLightTheme`): con tema claro la vista previa es clara y un ícono blanco no se ve. Los clics simulados (`mouse_event`) no le
  atinan a esos botones: pruébalos con el mouse de verdad.
- **El servicio de Python fuerza UTF-8** en stdin/stdout (`servicio.py`): Windows usaba cp1252 y rompía acentos.

## Convenciones

- **Todo en español**: nombres de variables y funciones, comentarios, textos de la interfaz y mensajes de commit. Tono cercano en la UI ("tú").
- **Todo texto visible pasa por `t()`** (`lib/idioma.svelte.js`): se escribe en español, `t("“{titulo}” se agregó", { titulo })`, y se agrega su
  traducción en `lib/textos/en.js` (la clave es el texto en español exacto). Para contar canciones usa `canciones(n)`. **No** nombres `t` a una variable
  en un archivo que use `t()`. Para fechas y números: `local()`. Un idioma nuevo = otro archivo en `textos/` y una línea en `IDIOMAS`.
- Svelte 5 **runes**; nada de stores de Svelte 4. Estado compartido en módulos `*.svelte.js` con `$state` exportado.
- Comentarios: explican el **porqué** (sobre todo lo no obvio), no el qué. Mantén la densidad del archivo que tocas.
- Python: funciones de `api.py` reciben/devuelven `dict`; errores para el usuario con `RuntimeError("mensaje claro")`.
- Nada de dependencias nuevas si la librería estándar alcanza (el jam y el flujo usan `http.server`). Si agregas paquete de Python, ponlo en **los dos lados**:
  `app/build.gradle.kts` (Chaquopy) y el venv/PyInstaller de Windows (`construir_servicio.py`, `--collect-*` si trae datos).
- Responsive, tres modos: cel (barra inferior), **cel acostado** (`ui.horizontal`, `@media (orientation: landscape) and (max-height: 560px)`:
  riel de pestañas a la izquierda `--riel`, reproductor en dos columnas, sin `--nav`) y escritorio/tablet (`ui.amplio`, `@media (min-width: 900px) and (min-height: 561px)`:
  barra lateral). Lo de escritorio **siempre** lleva `min-height: 561px`: un cel acostado puede medir más de 900 de ancho (S25 Ultra: 915) y caería en el diseño de PC.
  Con el cel acostado respeta la muesca con `env(safe-area-inset-left/right)`. Prueba los tres (en el navegador: 412×892, 892×412 y 1360×820).

## Trampas del entorno (Windows)

- **No edites archivos con PowerShell `Get-Content`/`Set-Content`**: PowerShell 5 rompe UTF-8 y agrega BOM. Usa el editor o Python. Los JSON de Tauri **sin BOM**.
- En PowerShell 5, un programa que escribe en stderr (PyInstaller, go, gradle) se toma como error con `$ErrorActionPreference = "Stop"`: no uses `2>&1` con esos.
- Rutas largas: los repos de terceros para compilar van en `%TEMP%` (`wd-qjs`, `wd-cf`), no en carpetas profundas.

---

## Comandos

```powershell
# Requisitos de escritorio: Node, Rust, Python 3.14 en ..\venv (raíz del repo) con:
#   pip install -r requirements.txt
#   ffmpeg, ffprobe y deno en el PATH (winget). O WAVEDROP_PYTHON=ruta\python.exe
npm install
npx tauri dev                                   # escritorio con el Python del venv

# Android (SDK + NDK + Python 3.14 en C:\Python314 para Chaquopy)
npx tauri android build --apk --target x86_64   # para el emulador
npx tauri android build --apk --target aarch64  # para teléfonos (firmado con firma/)

# Binarios nativos de Android: una vez al clonar (no están en git) y cuando cambien de versión
.\scripts\compilar_qjs.ps1
.\scripts\compilar_cloudflared.ps1              # necesita Go (portátil en %LOCALAPPDATA%\wd-go)

# Publicar una versión (Windows + Android + Release en GitHub). Solo quien administra el proyecto, y cuando lo pida.
.\scripts\publicar.ps1 -Version 2.0.1 -Notas "Qué cambió"
```

`publicar.ps1` pone la versión en `tauri.conf.json`, empaqueta el servicio, compila y firma Windows (updater) y Android, arma `latest.json` y crea la Release.
Las apps instaladas se actualizan solas desde la Release más reciente (Windows con `latest.json`, Android bajando el APK).

## Cómo probar

- Python suelto: importa `wavedrop` con `sys.path` apuntando a `python/` y `plataforma.configurar(datos, musica, cache)` en una carpeta temporal.
  Para `api` sin `iniciar()`: `api._estado["db"] = biblioteca.Biblioteca(ruta)`. Para jams de prueba usa otro puerto (`jam.PUERTOS = [47495]`)
  si hay un Misiccord abierto.
- Emulador (`Medium_Phone_API_37.0`, x86_64): `adb install -r` el APK universal de release.
  - Tiempos de `flujo.py` en logcat: líneas `[flujo] …` (`adb logcat | findstr flujo`).
  - Medios/relojes: `adb shell dumpsys media_session`; simular botones del reloj: `adb shell cmd media_session dispatch pause|play|next`.
  - Links: `adb shell am start "intent://jam?ip=…&puerto=…&codigo=…#Intent;scheme=misiccord;package=com.wavedrop.movil;end"`.
  - El WebView del emulador **no conecta a `10.0.2.2`** (la PC): para unirse a un jam de la PC usa `adb reverse tcp:PUERTO tcp:PUERTO` e `ip=127.0.0.1`.
- Los jams entre dispositivos reales los prueba quien administra el proyecto: no los des por probados si solo los corriste en el emulador.
