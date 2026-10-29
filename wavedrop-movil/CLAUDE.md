# Misiccord (carpeta `wavedrop-movil/`)

Reproductor y descargador de música (YouTube Music, Spotify, SoundCloud) con biblioteca local, letras
sincronizadas, recomendaciones y **jams** (escuchar juntos en red local o por internet).
Una sola base de código para **Windows** (instalador NSIS) y **Android** (APK).

> El nombre interno histórico es **WaveDrop** y así se queda en identificadores y rutas (ver "No cambiar").
> El nombre visible es **Misiccord**.

Lee este archivo completo antes de cambiar algo. Casi todo lo que "parece raro" aquí tiene una razón
documentada abajo; si algo no está documentado, pregunta antes de "arreglarlo".

---

## Estado del proyecto (al 29 de octubre de 2026 · versión publicada: **1.0.6**)

Resumen para que no tengas que leer todo el código. Actualiza esta sección cuando publiques una versión.

### Qué hace la app hoy
- **Biblioteca local**: escanea la carpeta de descargas (y las que se agreguen), agrupa por canción/álbum/artista, playlists propias,
  historial de reproducción. Eliminar canciones: una, varias (modo selección en Biblioteca), un álbum o un artista completo.
- **Reproductor**: fundido entre canciones (0–12 s, en Ajustes), aleatorio/repetir, volumen, reproductor grande con letra sincronizada (LRCLIB)
  y cola, mini reproductor. En el cel: notificación de música, pantalla bloqueada, relojes (Wear OS/Galaxy Watch) y audífonos Bluetooth.
- **En línea (YouTube Music)**: buscador en vivo en **Inicio** (resultados mientras escribes), álbumes y artistas, recomendaciones "Para ti"
  (radio a partir de lo que más escuchas/descargas, caché de 6 h). Lo que no tienes suena **al instante por streaming progresivo** y se guarda en caché si se escucha completo.
- **Descargas**: canciones sueltas o links de playlists/álbumes de YouTube, YouTube Music, **Spotify** (se lee la lista de la página *embed* de Spotify, que trae unas 100 canciones como máximo, y cada una se busca en YouTube Music) y SoundCloud.
  Metadatos de MusicBrainz, carpetas por artista, 1–4 descargas a la vez, carpeta configurable (en Android: carpeta de la app o la pública
  `Music/Misiccord`, que pide "Acceso a todos los archivos").
- **Jams** (escuchar juntos):
  - Modos *Sincronizado* (suena en todos) o *Solo aquí* (suena en el anfitrión, ideal con bocina). Cola compartida, votos para saltar, reacciones,
    invitados mandan canciones de su teléfono o de YouTube Music (suenan al momento, sin esperar descarga), agregar desde cualquier lista.
  - Unirse: QR (escáner de la app o cámara normal), **link** que abre la app y entra solo, jams cercanos (UDP en la red) o IP + código.
  - **Por internet**: el anfitrión (PC o cel) toca "Abrir" en Invitar; túnel de Cloudflare, sin cuenta ni configurar el módem.
- **Actualizaciones automáticas** desde GitHub Releases (Windows instala solo; Android baja el APK y abre el instalador).

### Historial de versiones
| Versión | Qué trajo |
|---|---|
| 1.0.0 | Migración de WaveDrop (PySide6) a Tauri 2: Windows + Android con el mismo núcleo de Python; jams en red local. |
| 1.0.1 | Carpeta pública Música en Android (permiso de archivos), primeras actualizaciones automáticas. |
| 1.0.2 | **Lector QR ya no cierra la app** (reglas R8), rediseño de Jams, respaldo ante "not a bot" de YouTube, arreglos de Inicio. |
| 1.0.3 | Jams por internet desde la PC, barra flotante del jam, agregar al jam desde cualquier lista, límite de intentos del código. |
| 1.0.4 | Eliminar canciones, primer streaming, controles de medios/relojes, jam por internet desde el cel (`cloudflared` para Android). |
| 1.0.5 | Streaming progresivo real (cliente `android_music` sin JS: de ~11 s a ~2 s en el cel) y precarga, YouTube en jams al instante, buscador en Inicio. |
| 1.0.6 | Links de jam (`https://accor-dium.github.io/misiccord/jam/#…` → `misiccord://`), el QR usa ese link, avisos si un jam no responde. |

### Qué está probado y dónde
- **En dispositivos reales** (lo probó quien administra el proyecto): app de Windows, Android en varios teléfonos (Samsung S25 Ultra, Pixel 7 Pro…),
  jams en red local, escáner QR, jam por internet abierto desde el cel.
- **Solo en el emulador o con scripts**: controles de reloj (con `cmd media_session dispatch`), links en Android, eliminar canciones,
  tiempos de streaming, streaming progresivo (en Chromium con la red frenada).
- **Sin probar todavía**: links y "una sola ventana" en Windows, panel de medios de Windows, un reloj real, un jam con YouTube Music entre teléfonos reales.

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
- `Buscar.svelte` quedó sin pestaña (la búsqueda está en Inicio); se puede quitar cuando nada la abra.
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
| `descargas.py` | yt-dlp: leer playlists/links (incluye Spotify por scraping), `Descargador`, `extraer()` con **respaldo de clientes** si YouTube pide "confirm you're not a bot", reintento si `descargados.txt` bloquea una canción borrada. Sin ffmpeg (Android) etiqueta con mutagen. |
| `explorar.py` | ytmusicapi: búsqueda, álbum, artista, radio, recomendaciones (caché 6 h), `previa()` (descarga completa a caché: **solo respaldo**). |
| `flujo.py` | **Streaming progresivo** de canciones que no tienes: servidor local `127.0.0.1:<puerto>/flujo/<id>?t=<token>` que pasa el audio de YouTube por pedazos (soporta Range) y lo guarda en caché si se escucha completo. Camino rápido con cliente `android_music` sin JS; precarga en segundo plano. `servir()` lo reutiliza el jam. |
| `biblioteca.py` | SQLite: canciones, carpetas, playlists, historial (`eventos`). Álbumes por álbum+artista del álbum. `buscar_existente()` para no descargar dos veces. |
| `jam.py` | Servidor HTTP del jam (solo librería estándar): sala, cola, votos, reacciones, sincronía por reloj, SSE `/eventos` (red local) y sondeo largo `/esperar` (internet), subir canciones de invitados, descubrimiento UDP. |
| `tunel.py` | Jam por internet: túnel rápido de Cloudflare (`cloudflared`). Windows lo baja la primera vez; Android lo trae en el APK. Job Object en Windows para que muera con el servicio. |
| `letras.py` | LRCLIB (letra sincronizada) con `.lrc` junto al archivo. **Nunca** imprimas ni registres letras en logs/salidas. |
| `musicbrainz.py` | Completa álbum/año/pista/portada al descargar. |

`python/servicio.py`: el proceso de escritorio (stdin/stdout en UTF-8 forzado; `print` va a stderr).

### `src/` — interfaz (Svelte 5 con runes: `$state`, `$derived`, `$effect`, `$props`)
- `App.svelte`: arranque, mapa de vistas, mini reproductor, hoja, avisos. Importa `lib/medios.svelte.js` y llama `escucharEnlaces()`.
- `lib/api.js` (`py`, `alEvento`, `src`, `tiempo`) · `lib/estado.svelte.js` (navegación con pila + historial de Android, `ui`, avisos, hojas, descargas) ·
  `lib/reproductor.svelte.js` (dos `<audio>` con fundido seno/coseno, cola, precarga de la siguiente, respaldo si el flujo falla) ·
  `lib/jam.svelte.js` (cliente del jam: SSE o sondeo largo, sincronía, agregar desde cualquier lista) ·
  `lib/medios.svelte.js` (notificación/pantalla bloqueada/relojes en Android; Media Session de WebView2 en Windows) ·
  `lib/enlaces.svelte.js` (links de jam: deep link `misiccord://` y la página `https`) ·
  `lib/eliminar.js` (borrar canciones con confirmación) · `lib/actualizaciones.svelte.js` · `lib/aBody.js`.
- `vistas/`: `Inicio` (con el buscador en vivo `componentes/Buscador.svelte`), `Biblioteca` (selección múltiple), `Album`, `Artista`,
  `Playlist`, `Jams`, `Descargas`, `Ajustes`. `Buscar.svelte` sigue registrada en `App.svelte` pero **ya no hay pestaña**: la búsqueda vive en Inicio.
- `componentes/`: `FilaCancion` (menú ⋯, agregar al jam, eliminar), `Hoja` (menú inferior / ventana en escritorio), `MiniReproductor` (también muestra el jam),
  `Reproductor`, `Letra`, `Tarjeta`, `Portada`, `Icono` (íconos SVG por nombre), `Volumen`, `Navegacion`, `Avisos`, `BotonDescarga`.
- `app.css`: tokens de color, `--margen`, carruseles (`scroll-padding` evita que se "corran"), tamaño de artistas `--artista`.

### `src-tauri/` — Rust y Android
- `src-tauri/src/lib.rs`: comandos `py`, `permiso_archivos`, `instalar_apk`, `medios`; plugins; arranque/cierre del servicio en Windows; puente de eventos en Android.
- `tauri.conf.json`: versión (la pone `publicar.ps1`), updater, deep-link `misiccord`, NSIS por usuario. `capabilities/{default,desktop,mobile}.json` (sin BOM).
- `gen/android/` **está editado a mano y versionado** (no es desechable):
  - `app/src/main/java/com/wavedrop/movil/PythonPlugin.kt` (llamar Python, eventos, permisos, instalar APK, medios) y `ServicioMedios.kt` (servicio en primer plano + MediaSession).
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
  claves de `localStorage` (`wavedrop_nombre`, `wavedrop_volumen`, `misiccord_ultima_revision`), esquema `misiccord://`, URL de la página
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
- **El servicio de Python fuerza UTF-8** en stdin/stdout (`servicio.py`): Windows usaba cp1252 y rompía acentos.

## Convenciones

- **Todo en español**: nombres de variables y funciones, comentarios, textos de la interfaz y mensajes de commit. Tono cercano en la UI ("tú").
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
#   pip install yt-dlp yt-dlp-ejs ytmusicapi mutagen qrcode requests pyinstaller
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
.\scripts\publicar.ps1 -Version 1.0.7 -Notas "Qué cambió"
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
