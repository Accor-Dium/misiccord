# Repositorio Misiccord (Accor-Dium/misiccord)

Aquí conviven dos generaciones de la app. **El desarrollo activo es `wavedrop-movil/`**: lee
[`wavedrop-movil/CLAUDE.md`](wavedrop-movil/CLAUDE.md) antes de tocar nada.

| Carpeta | Qué es | ¿Se modifica? |
|---|---|---|
| `wavedrop-movil/` | **Misiccord** actual: Tauri 2 + Svelte 5 + núcleo en Python, para Windows y Android. Lo que se publica en Releases. | Sí, aquí se trabaja. |
| raíz (`app.py`, `nucleo.py`, `explorar.py`, `biblioteca.py`, `letras.py`, `musicbrainz.py`, `estilos.py`, `instalador.iss`, `*.bat`, `DescargadorPlaylists.spec`) | **WaveDrop 2.2**, la app de escritorio vieja en PySide6 (y el descargador original por consola). Se conserva como referencia. | No, salvo que se pida explícitamente. |
| `venv/` | Entorno de Python del proyecto (no versionado). `wavedrop-movil` lo usa en desarrollo. | — |
| `build/`, `dist/`, `instalador/` | Salidas de la app vieja (no versionadas). | — |

Reglas que valen para todo el repo:
- Todo en **español** (código, comentarios, interfaz, commits).
- El núcleo nuevo (`wavedrop-movil/python/wavedrop/`) empezó como copia de los módulos de la raíz, pero **ya divergió**:
  no copies cambios de un lado a otro sin revisarlos.
- La carpeta `wavedrop-movil/firma/` tiene las llaves privadas de firma: nunca se sube ni se comparte.
- La página de los links de jam se publica desde la rama **`gh-pages`** (GitHub Pages), no desde `main`.
