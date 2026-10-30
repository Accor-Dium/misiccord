# Misiccord (carpeta `wavedrop-movil/`)

Reproductor y descargador de música (YouTube Music, Spotify, SoundCloud) con biblioteca local, letras
sincronizadas, recomendaciones y **jams** (escuchar juntos en red local o por internet).
Una sola base de código para **Windows** (instalador NSIS) y **Android** (APK).

> El nombre interno histórico es **WaveDrop** y así se queda en identificadores y rutas (ver "No cambiar").
> El nombre visible es **Misiccord**.

Lee este archivo completo antes de cambiar algo. Casi todo lo que "parece raro" aquí tiene una razón
documentada abajo; si algo no está documentado, pregunta antes de "arreglarlo".

---

## Estado del proyecto (al 30 de octubre de 2026 · versión publicada: **3.0.0**)

Resumen para que no tengas que leer todo el código. Actualiza esta sección cuando publiques una versión.

### Qué hace la app hoy
- **Biblioteca local**: escanea la carpeta de descargas (y las que se agreguen), agrupa por canción/álbum/artista, playlists propias,
  historial de reproducción, vista de lista o cuadrícula (cada pestaña recuerda la suya), índice A–Z con burbuja de la letra. Eliminar canciones: una, varias (modo selección en Biblioteca), un álbum o un artista completo.
- **Reproductor**: fundido entre canciones (0–12 s, en Ajustes), aleatorio/repetir, volumen de 0 a 200 % con curva perceptual, reproductor grande con letra sincronizada (LRCLIB)
  y cola, mini reproductor. En el cel: notificación de música, **widget de la pantalla de inicio** (abre la app; con música, canción y controles), pantalla bloqueada, relojes (Wear OS/Galaxy Watch) y audífonos Bluetooth.
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
  Metadatos de MusicBrainz, carpetas por artista, 1–4 descargas a la vez, carpeta configurable (en Android: carpeta de la app o la pública
  `Music/Misiccord`, que pide "Acceso a todos los archivos").
- **Jams** (escuchar juntos):
  - Modos *Sincronizado* (suena en todos) o *Solo aquí* (suena en el anfitrión, ideal con bocina). Cola compartida, votos para saltar, reacciones,
    invitados mandan canciones de su teléfono o de YouTube Music (suenan al momento, sin esperar descarga), agregar desde cualquier lista.
  - Unirse: QR (escáner de la app o cámara normal), **link** que abre la app y entra solo, jams cercanos (UDP en la red) o IP + código.
  - **Por internet**: el anfitrión (PC o cel) toca "Abrir" en Invitar; túnel de Cloudflare, sin cuenta ni configurar el módem.
- **Videos musicales** (apagado por defecto, en Ajustes): ver el clip en el reproductor (sigue al audio, sin sonido propio) y descargarlo junto a la canción.
- **Biblioteca por carpetas**: agregar o quitar carpetas de música y filtrar canciones, álbumes y artistas por carpeta.
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

### Qué está probado y dónde
- **En dispositivos reales** (lo probó quien administra el proyecto): app de Windows, Android en varios teléfonos (Samsung S25 Ultra, Pixel 7 Pro…),
  jams en red local, escáner QR, jam por internet abierto desde el cel.
- **Solo en el emulador o con scripts**: controles de reloj (con `cmd media_session dispatch`), links en Android, eliminar canciones,
  tiempos de streaming, streaming progresivo (en Chromium con la red frenada).
- **Sin probar todavía**: links y "una sola ventana" en Windows, panel de medios de Windows, un reloj real, un jam con YouTube Music entre teléfonos reales, videos musicales y carpetas de la biblioteca en el cel, lo de 1.0.8 (segundo plano, ecualizador, editar etiquetas) en teléfonos reales, y de 1.0.9: exportar a una USB real y todo en la app de Windows (se probó en navegador con el núcleo de Python y en el emulador: menú, compartir de Android, jalar para actualizar, idioma); de 1.0.10, el volumen arriba de 100 % con música real; de 2.0.1, el widget y quitar de recientes en teléfonos reales (en el emulador sí: sigue sonando, controles, reabrir, atrás, reiniciar para el QR) (la curva y el limitador se midieron en Chromium con señales de prueba).

### Dónde guarda las cosas
| | Windows | Android |
|---|---|---|
| Datos (`biblioteca.db`, `ajustes.json`, `recomendaciones.json`) | `%LOCALAPPDATA%\WaveDrop` | `files/wavedrop` de la app |
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
  `lib/menuCancion.js` (el menú de una canción) · `lib/compartir.js` (compartir/exportar) · `lib/jalar.js` (jalar para actualizar).
- `vistas/`: `Inicio` (con el buscador en vivo `componentes/Buscador.svelte`), `Explorar`, `Biblioteca` (selección para compartir o borrar), `Album`
  (también playlists de YouTube Music), `Artista`, `Playlist`, `MeGusta`, `Estadisticas`, `Jams`, `Descargas`, `Ajustes`.
- `componentes/`: `FilaCancion` (menú ⋯, agregar al jam, eliminar), `Hoja` (menú inferior / ventana en escritorio), `MiniReproductor` (también muestra el jam),
  `Reproductor`, `Cola`, `Ecualizador`, `Visualizador`, `Marquesina` (texto que se desliza si no cabe), `Resumen`, `CompletarDatos`, `Letra`, `Tarjeta`, `Portada` (reintenta si una portada falla), `Icono` (íconos SVG por nombre), `Volumen`, `Navegacion`, `ListaVirtual` (solo dibuja las filas cerca de la pantalla),
  `Avisos` (abajo, con acción y barra de avance: `aviso(texto, tipo, { id, duracion, accion, avance })`), `BotonDescarga`, `Paginas`, `InfoCancion`.
- `app.css`: tokens de color, `--margen`, carruseles (`scroll-padding` evita que se "corran"), tamaño de artistas `--artista`.

### `src-tauri/` — Rust y Android
- `src-tauri/src/lib.rs`: comandos `py`, `permiso_archivos`, `instalar_apk`, `medios`; plugins; arranque/cierre del servicio en Windows; puente de eventos en Android.
- `tauri.conf.json`: versión (la pone `publicar.ps1`), updater, deep-link `misiccord`, NSIS por usuario. `capabilities/{default,desktop,mobile}.json` (sin BOM).
- `gen/android/` **está editado a mano y versionado** (no es desechable):
  - `app/src/main/java/com/wavedrop/movil/PythonPlugin.kt` (llamar Python, eventos, permisos, instalar APK, medios) y `ServicioMedios.kt` (servicio en primer plano + MediaSession).
  - `WidgetMisiccord.kt` + `res/layout/widget_misiccord.xml` + `res/xml/widget_misiccord.xml`: widget 4×1. `ServicioMedios` lo actualiza solo cuando cambia algo que se ve
    (no con cada avance); sus botones van al servicio igual que los de la notificación. Sin música, todo el widget solo abre la app (Python vive dentro de ella).
    Textos en `res/values/strings.xml` y `res/values-en/`.
  - `app/src/main/AndroidManifest.xml` (permisos de archivos, cámara, servicio de medios, FileProvider, intent-filter `misiccord`).
  - `app/build.gradle.kts` (Chaquopy, Python 3.14, paquetes pip, ABIs, firma, `androidx.media`).
  - `app/misiccord.pro` (reglas R8: **sin ellas el lector QR truena**, ver abajo).
  - `buildSrc/.../RustPlugin.kt` (solo `arm64-v8a` y `x86_64`).
  - `app/src/main/jniLibs/<abi>/libqjs.so` y `libcloudflared.so`: **no están en git** (los `.so` se ignoran); genéralos con
    `compilar_qjs.ps1` y `compilar_cloudflared.ps1` antes de tu primer build de Android (ver Comandos).

### Otros
- `scripts/`: `publicar.ps1` (publica una versión), `construir_servicio.py` (PyInstaller del servicio de Windows), `compilar_qjs.ps1`, `compilar_cloudflared.ps1`, `crear_icono.py`.
- `web/`: código de la página de los links de jam. **Se publica en la rama `gh-pages`** (GitHub Pages → `https://accor-dium.github.io/misiccord/jam/`), no desde `main`.
- `firma/` (**privada, en .gitignore**): llave del APK (`misiccord.jks`, `keystore.properties`) y del updater (`actualizaciones.key(.pub)`, `actualizaciones.properties`). Nunca la subas, la imprimas ni la copies.
- `publicar/vX.Y.Z/`: lo que se subió a cada Release. `servicio-dist/`: salida de PyInstaller (generada).

---

## No cambiar (aunque parezca mejora)

- **Identificadores**: `identifier` = `com.wavedrop.movil` (cambiarlo = otra app; se pierden datos y actualizaciones), carpeta de datos `%LOCALAPPDATA%\WaveDrop`,
  claves de `localStorage` (`wavedrop_nombre`, `wavedrop_volumen`, `misiccord_ultima_revision`, `misiccord_idioma`, `misiccord_orden`, `misiccord_volumen_escala`, `misiccord_vista_biblioteca`), esquema `misiccord://`, URL de la página
  `https://accor-dium.github.io/misiccord/jam/` (está en `lib/enlaces.svelte.js` y en `api.jam_qr`: cambia las dos o ninguna), repo `Accor-Dium/misiccord`.
- **Llaves de firma**: si cambia la del APK, Android no deja actualizar encima; si cambia la del updater, las PCs instaladas no aceptan versiones nuevas.
- **Python 3.14 + Chaquopy 17.2** y **solo ABIs arm64/x86_64** (Chaquopy no compila 3.14 para armeabi-v7a).
- **`yt-dlp>=2026.10.26` + `yt-dlp-ejs`**, nunca `yt-dlp[default]` (pip resolvía una versión de 2021).
- **QuickJS en Android, deno en Windows** como motor de JS de yt-dlp (`plataforma.js_runtimes`). En Android no hay ffmpeg: se baja m4a/opus tal cual.
- **Cliente `android_music` sin JS** como primer intento en `flujo.py`: en el cel el JS por QuickJS tarda ~10 s por canción. Saltarse la página
  (`player_skip=webpage`) **provoca** "confirm you're not a bot": no lo actives.
- **SSE solo en red local; sondeo largo `/esperar` por internet**: los túneles rápidos de Cloudflare no pasan SSE. El SSE va en HTTP/1.1 chunked a propósito.
- **Seguridad del jam**: código de 4 dígitos + bloqueo tras 8 intentos fallidos por origen (`CF-Connecting-IP` por el túnel). No quites el límite.
- **`allow_reuse_address = False` en Windows** (`jam.py`): si no, dos jams comparten puerto y se roban conexiones.
- **Reglas R8 de `misiccord.pro`** (ML Kit, CameraX, Firebase components): sin ellas, en release el escáner QR cierra la app con el primer cuadro.
- **`use:aBody`** en ventanas/barras flotantes: `<main>` tiene `view-transition-name` (crea su propia capa) y nada adentro puede quedar encima de la barra.
- **Plugins con `#[cfg(desktop)]` / `#[cfg(mobile)]`** en `lib.rs` (updater y single-instance solo escritorio; barcode solo móvil) y permisos en la capability de su plataforma.
- **Borrar = de todos lados** (`api.eliminar_canciones`): archivo, biblioteca, playlists, historial, cola, jam, MediaStore y carpetas vacías. Si agregas otro lugar donde
  viva una canción, agrégalo ahí también.
- **Video (ajustes `video_ver` y `video_descargar`, ambos apagados por defecto)**: el `<video>` va mudo y sigue al `<audio>` (`reproductor.svelte.js`). El clip se busca con
  `explorar.buscar_video` porque el id de la canción en YT Music suele ser audio con la portada. El video descargado es `<canción>.mp4` junto al audio
  (`.mp4` no está en `biblioteca.EXTENSIONES`: así no se toma por canción) y `eliminar_canciones` lo borra también. Para **transmitir** solo sirve el cliente
  `android` de yt-dlp (mp4 360p por rangos); tv/web dan más calidad pero YouTube responde 403 sin token (`flujo._extraer_video` prueba cada candidato).
- **Letra (`Letra.svelte`)**: el espacio arriba y abajo de la letra son divs medidos en px con el alto real de la caja. Con `padding` en vh la caja
  crecía más que su lugar y en el cel tapaba la barra para adelantar (tocabas una línea en vez de la barra). Y `scrollTo` en la caja, no `scrollIntoView`
  (ese movía al reproductor entero).
- **Biblioteca**: buscar, ordenar y agrupar es todo en la interfaz (`lib/ordenar.js`, sin acentos, "The" ignorado); solo lo que no tienes se pide a
  YouTube Music. El orden elegido vive en `localStorage` (`misiccord_orden`).
- **Abrir Biblioteca debe ser instantáneo** (con 1,671 canciones llegó a tardar ~9 s en un cel simulado). Cuatro cosas lo sostienen:
  - **Listar no toca los archivos**: la portada está en la columna `canciones.portada` (ruta en la caché, `""` si no trae, `NULL` si falta buscarla). `api._completar_portadas`
    llena las que falten después de cada escaneo y `revisar_portadas` recupera las que Android borre de la caché. No regreses `portada_local()` a `_local()`: abre el archivo de cada canción (FUSE en Android).
  - **Los datos van fuera de `nav`**: `Biblioteca.svelte` los guarda en `memoria` (`<script module>`, `$state.raw`). En `e.datos` cada canción se vuelve un Proxy (`nav` es estado profundo)
    y además se pierden, porque `irPestana` crea una entrada nueva.
  - **`ListaVirtual`**: las filas de un mismo `tipo` deben medir igual. Mide una sola vez por ancho: los textos en otros alfabetos usan otra fuente y cambian el alto 1 o 2 px,
    y medir con cada fila que entra crea un ciclo infinito entre listas (`effect_update_depth_exceeded`). Encabezados y `.ancla` siguen en el DOM: por eso funcionan `sticky` y el índice A–Z.
  - **El aviso `"biblioteca"` trae `sin_cambios`** si el escaneo no encontró nada: si no, cada arranque volvía a pedir y dibujar todo.
- **La cola es el orden real** (`rep.cola`): con aleatorio se baraja de verdad (`mezclar`) y `original` guarda el orden para regresar a él. Nunca elijas la siguiente al azar
  al momento: "A continuación" (`Cola.svelte`) debe decir lo que va a sonar. La que suena va hasta arriba; lo anterior se ve con "Ver las anteriores".
- **Álbum y artista: primero lo local** (`artista_local`, `album_local_buscar`): sale al instante y funciona sin internet; lo de YouTube Music se agrega después y sus errores no se muestran si ya hay algo tuyo.
- **Ecualizador en el reproductor** (`Ecualizador.svelte`): 3, 5, 10, 15 o 31 bandas; cuántas hay lo dice el largo de `eq_bandas` (`convertirBandas` interpola al cambiar). Mono es `channelCount = 1` en el primer nodo.
  Mono y los visualizadores (`Visualizador.svelte`, `analizadorDeAudio`) también arman el grafo de Web Audio.
- **Completar datos** (`CompletarDatos.svelte`, `musicbrainz.opciones`): una opción por grupo de MusicBrainz, primero su edición más antigua (si no, Thriller salía de 2022). Respeta el límite de 1 consulta por segundo de `_get`.
- **Editar álbum** (`EditarAlbum.svelte`, `musicbrainz.buscar_albumes/album_detalle/emparejar`): las opciones van por edición (no por grupo) porque cambian las pistas. Solo es "exacta" si coinciden
  todas las letras (`_letras`); `normalizar` ignora paréntesis y "(en vivo)" pasaría por exacta. Las canciones que se dejan fuera no se tocan y siguen a `completarDatos`.
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
- **Índice A–Z de Biblioteca**: salta a un `<span class="ancla">` antes de cada encabezado, no al encabezado: los encabezados son `sticky` y uno que ya
  se quedó pegado arriba no deja regresar a él con `scrollIntoView`.
- **Reproductor grande**: deslizar para cerrar no empieza sobre la barra de avance ni el volumen (`tocarInicio`), e `irA()` pone `rep.pos` al instante
  (si no, la barra regresaba un momento a donde iba y parpadeaba).
- **Quitar la app de recientes con música sonando (`MainActivity.kt`)**: Tauri cerraba el proceso al destruirse la Activity. Si algo suena,
  `isChangingConfigurations()` devuelve true en ese `onDestroy` (tao y wry creen que es un giro de pantalla) y la WebView se guarda; al reabrir,
  esa misma WebView se muda a la Activity nueva (Tauri no crea otra porque no conoce ese id). Consecuencias: los plugins siguen ligados a la
  Activity original, por eso `PythonPlugin` abre pantallas con `pantalla` (la visible) y el lector QR pide reiniciar (`sesion` → `reiniciar`)
  si `reanudada`. Si la Activity "mudada" se cierra sin música, se mata el proceso (Tauri no sabría que se cerró).
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
- Responsive: <900 px es cel (barra inferior), ≥900 px escritorio (barra lateral, `ui.amplio`). Prueba los dos.

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
