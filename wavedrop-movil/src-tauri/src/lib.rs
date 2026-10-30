#[cfg(windows)]
mod barra;

use tauri::plugin::{Builder, TauriPlugin};
use tauri::{Manager, Runtime};

#[cfg(target_os = "android")]
use tauri::Emitter;

// ---------- Android: Python vive dentro de la app (Chaquopy) y se llama por el plugin de Kotlin ----------

/// Argumentos que recibe PythonPlugin.llamar (Kotlin).
#[allow(dead_code)]
#[derive(serde::Serialize)]
struct Llamada {
    funcion: String,
    datos: String,
}

#[allow(dead_code)]
#[derive(serde::Deserialize)]
struct Respuesta {
    resultado: String,
}

#[allow(dead_code)]
#[derive(serde::Deserialize)]
struct Evento {
    evento: String,
}

#[cfg(target_os = "android")]
struct Python<R: Runtime>(tauri::plugin::PluginHandle<R>);

/// Registra el plugin de Kotlin que arranca Python (Chaquopy) y reenvía sus avisos como evento "python".
fn plugin_python<R: Runtime>() -> TauriPlugin<R> {
    Builder::new("python")
        .setup(|_app, _api| {
            #[cfg(target_os = "android")]
            {
                let handle = _api.register_android_plugin("com.wavedrop.movil", "PythonPlugin")?;
                _app.manage(Python(handle));
                let app = _app.clone();
                // Bucle de avisos: Kotlin responde en cuanto Python emite algo (o vacío cada 20 s)
                std::thread::spawn(move || {
                    loop {
                        let res = app
                            .state::<Python<R>>()
                            .0
                            .run_mobile_plugin::<Evento>("esperarEvento", serde_json::json!({}));
                        match res {
                            Ok(e) if !e.evento.is_empty() => {
                                let _ = app.emit("python", e.evento);
                            }
                            Ok(_) => {}
                            Err(_) => std::thread::sleep(std::time::Duration::from_secs(1)),
                        }
                    }
                });
            }
            Ok(())
        })
        .build()
}

// ---------- Escritorio: Python corre aparte como servicio y se le habla por stdin/stdout ----------

#[cfg(not(target_os = "android"))]
mod escritorio {
    use std::collections::HashMap;
    use std::io::{BufRead, BufReader, Write};
    use std::path::{Path, PathBuf};
    use std::process::{Child, ChildStdin, Command, Stdio};
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::{Mutex, mpsc};
    use tauri::{AppHandle, Emitter, Manager};

    pub struct Servicio {
        entrada: Mutex<ChildStdin>,
        pendientes: Mutex<HashMap<u64, mpsc::Sender<String>>>,
        siguiente: AtomicU64,
        proceso: Mutex<Child>,
    }

    /// Empaquetado: resources/servicio/misiccord-servicio.exe. En desarrollo: el Python del venv del proyecto
    /// (Tauri copia el .exe viejo de servicio-dist junto al binario de debug y sin esto tapaba los cambios de python/).
    fn comando(app: &AppHandle) -> Command {
        if let (false, Ok(dir)) = (cfg!(debug_assertions), app.path().resource_dir()) {
            let exe = dir.join("servicio").join("misiccord-servicio.exe");
            if exe.exists() {
                return Command::new(exe);
            }
        }
        let raiz = Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
        let python = std::env::var("WAVEDROP_PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                raiz.join("..")
                    .join("venv")
                    .join("Scripts")
                    .join("python.exe")
            });
        let mut c = Command::new(python);
        c.arg(raiz.join("python").join("servicio.py"));
        c
    }

    pub fn iniciar(app: &AppHandle) -> Result<Servicio, String> {
        let mut c = comando(app);
        c.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .env("PYTHONIOENCODING", "utf-8")
            .env("PYTHONUTF8", "1");
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            c.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: sin ventana de consola
        }
        let mut hijo = c
            .spawn()
            .map_err(|e| format!("No se pudo arrancar el servicio de Python: {e}"))?;
        let entrada = hijo.stdin.take().ok_or("sin stdin")?;
        let salida = hijo.stdout.take().ok_or("sin stdout")?;

        let app2 = app.clone();
        std::thread::spawn(move || {
            for linea in BufReader::new(salida).lines() {
                let Ok(linea) = linea else { break };
                let Ok(v) = serde_json::from_str::<serde_json::Value>(&linea) else {
                    continue;
                };
                if let Some(evento) = v.get("evento").and_then(|e| e.as_str()) {
                    let _ = app2.emit("python", evento.to_string());
                } else if let (Some(id), Some(res)) = (
                    v.get("id").and_then(|i| i.as_u64()),
                    v.get("resultado").and_then(|r| r.as_str()),
                ) {
                    let servicio = app2.state::<Servicio>();
                    let tx = servicio.pendientes.lock().unwrap().remove(&id);
                    if let Some(tx) = tx {
                        let _ = tx.send(res.to_string());
                    }
                }
            }
        });

        Ok(Servicio {
            entrada: Mutex::new(entrada),
            pendientes: Mutex::new(HashMap::new()),
            siguiente: AtomicU64::new(1),
            proceso: Mutex::new(hijo),
        })
    }

    impl Servicio {
        pub fn llamar(&self, funcion: &str, datos: &str) -> Result<String, String> {
            let id = self.siguiente.fetch_add(1, Ordering::SeqCst);
            let (tx, rx) = mpsc::channel();
            self.pendientes.lock().unwrap().insert(id, tx);
            let linea =
                serde_json::json!({ "id": id, "funcion": funcion, "datos": datos }).to_string();
            {
                let mut e = self.entrada.lock().unwrap();
                writeln!(e, "{linea}")
                    .and_then(|_| e.flush())
                    .map_err(|e| e.to_string())?;
            }
            rx.recv()
                .map_err(|_| "El servicio de Python se cerró".to_string())
        }

        pub fn cerrar(&self) {
            let _ = self.proceso.lock().unwrap().kill();
        }
    }
}

/// Llama a wavedrop.api.despachar(funcion, datos) en Python y devuelve su JSON como texto.
#[tauri::command]
async fn py(app: tauri::AppHandle, funcion: String, datos: String) -> Result<String, String> {
    // Python puede tardar (búsquedas, vistas previas): se espera en un hilo aparte
    tauri::async_runtime::spawn_blocking(move || {
        #[cfg(target_os = "android")]
        {
            app.state::<Python<tauri::Wry>>()
                .0
                .run_mobile_plugin::<Respuesta>("llamar", Llamada { funcion, datos })
                .map(|r| r.resultado)
                .map_err(|e| e.to_string())
        }
        #[cfg(not(target_os = "android"))]
        {
            app.state::<escritorio::Servicio>().llamar(&funcion, &datos)
        }
    })
    .await
    .map_err(|e| e.to_string())?
}

#[allow(dead_code)]
#[derive(serde::Serialize)]
struct Pedido {
    pedir: bool,
}

#[allow(dead_code)]
#[derive(serde::Serialize)]
struct Apk {
    ruta: String,
}

#[allow(dead_code)]
#[derive(serde::Deserialize)]
struct Permiso {
    concedido: bool,
}

/// Android: ¿se puede escribir en carpetas públicas? Con pedir=true abre la pantalla del permiso.
/// En escritorio no hace falta permiso.
#[tauri::command]
async fn permiso_archivos(app: tauri::AppHandle, pedir: bool) -> Result<bool, String> {
    #[cfg(target_os = "android")]
    {
        return app
            .state::<Python<tauri::Wry>>()
            .0
            .run_mobile_plugin::<Permiso>("permisoArchivos", Pedido { pedir })
            .map(|p| p.concedido)
            .map_err(|e| e.to_string());
    }
    #[cfg(not(target_os = "android"))]
    {
        let _ = (app, pedir);
        Ok(true)
    }
}

/// Android: abre el instalador del sistema con el APK de una actualización ya descargada.
#[tauri::command]
async fn instalar_apk(app: tauri::AppHandle, ruta: String) -> Result<serde_json::Value, String> {
    #[cfg(target_os = "android")]
    {
        return app
            .state::<Python<tauri::Wry>>()
            .0
            .run_mobile_plugin::<serde_json::Value>("instalarApk", Apk { ruta })
            .map_err(|e| e.to_string());
    }
    #[cfg(not(target_os = "android"))]
    {
        let _ = (app, ruta);
        Err("Solo en Android".into())
    }
}

/// Android: lo que suena, para la notificación de música, la pantalla bloqueada y los relojes (MediaSession).
/// En escritorio no hace nada: ahí la interfaz usa la Media Session API de WebView2 (controles de Windows).
#[tauri::command]
async fn medios(app: tauri::AppHandle, estado: serde_json::Value) -> Result<(), String> {
    #[cfg(target_os = "android")]
    {
        return app
            .state::<Python<tauri::Wry>>()
            .0
            .run_mobile_plugin::<serde_json::Value>("medios", estado)
            .map(|_| ())
            .map_err(|e| e.to_string());
    }
    #[cfg(not(target_os = "android"))]
    {
        let _ = (app, estado);
        Ok(())
    }
}

#[allow(dead_code)]
#[derive(serde::Serialize)]
struct PedidoFondo {
    pedir: String,
}

/// Android: permisos para trabajar en segundo plano (notificaciones de avance y sin límites de batería).
/// `pedir` = "notificaciones" | "bateria" abre el diálogo del sistema; vacío solo consulta.
/// Responde { notificaciones, bateria }. En escritorio la app sigue funcionando minimizada: todo está permitido.
#[tauri::command]
async fn segundo_plano(app: tauri::AppHandle, pedir: String) -> Result<serde_json::Value, String> {
    #[cfg(target_os = "android")]
    {
        return app
            .state::<Python<tauri::Wry>>()
            .0
            .run_mobile_plugin::<serde_json::Value>("segundoPlano", PedidoFondo { pedir })
            .map_err(|e| e.to_string());
    }
    #[cfg(not(target_os = "android"))]
    {
        let _ = (app, pedir);
        Ok(serde_json::json!({ "notificaciones": true, "bateria": true }))
    }
}

/// Android: menú "Compartir" del sistema con archivos de canciones ({ rutas, texto, titulo }).
/// En escritorio no existe: ahí se copian al portapapeles o a una USB desde Python.
#[tauri::command]
async fn compartir(app: tauri::AppHandle, datos: serde_json::Value) -> Result<serde_json::Value, String> {
    #[cfg(target_os = "android")]
    {
        return app
            .state::<Python<tauri::Wry>>()
            .0
            .run_mobile_plugin::<serde_json::Value>("compartir", datos)
            .map_err(|e| e.to_string());
    }
    #[cfg(not(target_os = "android"))]
    {
        let _ = (app, datos);
        Err("Solo en Android".into())
    }
}

/// Android: sesión conservada al quitar la app de recientes con música ({ accion: "" | "reiniciar" }).
#[tauri::command]
async fn sesion(app: tauri::AppHandle, datos: serde_json::Value) -> Result<serde_json::Value, String> {
    #[cfg(target_os = "android")]
    {
        return app
            .state::<Python<tauri::Wry>>()
            .0
            .run_mobile_plugin::<serde_json::Value>("sesion", datos)
            .map_err(|e| e.to_string());
    }
    #[cfg(not(target_os = "android"))]
    {
        let _ = (app, datos);
        Ok(serde_json::json!({ "reanudada": false }))
    }
}

/// Escritorio: burbuja flotante para controlar la música con la ventana minimizada (`src/componentes/Burbuja.svelte`).
///
/// Es otra ventana (pequeña, redonda, transparente y siempre encima) que solo muestra y manda órdenes: la música sigue
/// sonando en la ventana principal, que le pasa lo que suena por eventos. Se crea solo si el ajuste está prendido.
#[cfg(desktop)]
mod burbuja {
    use std::sync::atomic::{AtomicBool, Ordering};
    use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder, Window, WindowEvent};

    pub const TAM: f64 = 64.0;
    static ACTIVA: AtomicBool = AtomicBool::new(false);

    pub fn activar(app: &AppHandle, activa: bool) {
        ACTIVA.store(activa, Ordering::Relaxed);
        let existe = app.get_webview_window("burbuja");
        match (activa, existe) {
            (true, None) => {
                // En otro hilo: crear una WebView dentro de un comando o un evento puede trabar Windows
                let app = app.clone();
                std::thread::spawn(move || {
                    let _ = WebviewWindowBuilder::new(&app, "burbuja", WebviewUrl::App("index.html?burbuja".into()))
                        .title("Misiccord")
                        .inner_size(TAM, TAM)
                        .resizable(false)
                        .decorations(false)
                        .transparent(true)
                        .shadow(false)
                        .always_on_top(true)
                        .skip_taskbar(true)
                        .focused(false)
                        .visible(false)
                        .build();
                });
            }
            (false, Some(b)) => {
                let _ = b.destroy();
            }
            _ => {}
        }
    }

    /// La burbuja aparece al minimizar la ventana principal y se va al regresar a ella
    pub fn evento(ventana: &Window, evento: &WindowEvent) {
        if ventana.label() != "main" {
            return;
        }
        let Some(b) = ventana.app_handle().get_webview_window("burbuja") else { return };
        match evento {
            WindowEvent::Resized(_) | WindowEvent::Focused(_) => {
                if ventana.is_minimized().unwrap_or(false) {
                    if ACTIVA.load(Ordering::Relaxed) && !b.is_visible().unwrap_or(true) {
                        let _ = b.show();
                    }
                } else if b.is_visible().unwrap_or(false) {
                    ocultar(&b);
                }
            }
            // Sin esto la app no se cerraría: la burbuja escondida seguiría siendo una ventana abierta
            WindowEvent::Destroyed => {
                let _ = b.destroy();
            }
            _ => {}
        }
    }

    /// Mueve y cambia el tamaño en un solo paso (px lógicos): en dos pasos el círculo brinca un cuadro al crecer hacia la izquierda.
    pub fn marco(app: &AppHandle, x: f64, y: f64, ancho: f64) {
        let Some(b) = app.get_webview_window("burbuja") else { return };
        let f = b.scale_factor().unwrap_or(1.0);
        let (px, py, pw, ph) = ((x * f).round() as i32, (y * f).round() as i32, (ancho * f).round() as i32, (TAM * f).round() as i32);
        #[cfg(windows)]
        if let Ok(h) = b.hwnd() {
            use windows::Win32::UI::WindowsAndMessaging::{SetWindowPos, SWP_NOACTIVATE, SWP_NOZORDER};
            unsafe {
                let _ = SetWindowPos(windows::Win32::Foundation::HWND(h.0), None, px, py, pw, ph, SWP_NOZORDER | SWP_NOACTIVATE);
            }
            return;
        }
        let _ = b.set_size(tauri::PhysicalSize::new(pw, ph));
        let _ = b.set_position(tauri::PhysicalPosition::new(px, py));
    }

    /// Escondida se vuelve a cerrar en círculo: abierta, su parte transparente taparía clics al volver a salir
    fn ocultar(b: &tauri::WebviewWindow) {
        let _ = b.hide();
        let _ = b.emit_to("burbuja", "burbuja-oculta", ());
    }

    /// ¿El cursor sigue sobre la burbuja? WebView2 a veces avisa que el mouse salió sin que se haya movido
    pub fn dentro(app: &AppHandle) -> bool {
        let Some(b) = app.get_webview_window("burbuja") else { return false };
        let (Ok(c), Ok(p), Ok(t)) = (app.cursor_position(), b.outer_position(), b.outer_size()) else { return false };
        c.x >= p.x as f64 && c.x < (p.x + t.width as i32) as f64 && c.y >= p.y as f64 && c.y < (p.y + t.height as i32) as f64
    }

    pub fn abrir(app: &AppHandle) {
        if let Some(b) = app.get_webview_window("burbuja") {
            ocultar(&b);
        }
        if let Some(v) = app.get_webview_window("main") {
            let _ = v.unminimize();
            let _ = v.show();
            let _ = v.set_focus();
        }
    }
}

/// Burbuja flotante (solo escritorio): { accion: "activar", activa } desde Ajustes o al arrancar; desde la burbuja,
/// { accion: "abrir" } (volver a la app), { accion: "marco", x, y, ancho } (crecer o encogerse sin brincar) y
/// { accion: "dentro" } (true si el cursor está sobre ella).
#[tauri::command]
fn burbuja(app: tauri::AppHandle, accion: String, activa: Option<bool>, x: Option<f64>, y: Option<f64>, ancho: Option<f64>) -> bool {
    #[cfg(desktop)]
    match accion.as_str() {
        "activar" => burbuja::activar(&app, activa.unwrap_or(false)),
        "abrir" => burbuja::abrir(&app),
        "marco" => burbuja::marco(&app, x.unwrap_or(0.0), y.unwrap_or(0.0), ancho.unwrap_or(burbuja::TAM)),
        "dentro" => return burbuja::dentro(&app),
        _ => {}
    }
    #[cfg(mobile)]
    let _ = (app, accion, activa, x, y, ancho);
    false
}

/// Windows: lo que suena, para la vista previa de la barra de tareas (título de la ventana y botón de reproducir/pausar).
/// `textos`: anterior, reproducir, pausar y siguiente en el idioma de la app.
#[tauri::command]
fn barra_tareas(app: tauri::AppHandle, titulo: String, artista: String, hay: bool, sonando: bool, textos: Vec<String>) {
    #[cfg(windows)]
    {
        let mut t: [String; 4] = Default::default();
        for (i, x) in textos.into_iter().take(4).enumerate() {
            t[i] = x;
        }
        barra::actualizar(&app, titulo, artista, hay, sonando, t);
    }
    #[cfg(not(windows))]
    let _ = (app, titulo, artista, hay, sonando, textos);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let constructor = tauri::Builder::default().plugin(tauri_plugin_process::init());
    // Escritorio: actualizaciones automáticas desde GitHub Releases (en Android se hace aparte, con el APK)
    #[cfg(desktop)]
    let constructor = constructor
        // Va primero: si ya hay un Misiccord abierto, el link misiccord:// se le pasa a ese y se trae al frente
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(ventana) = app.get_webview_window("main") {
                let _ = ventana.unminimize();
                let _ = ventana.set_focus();
            }
        }))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .on_window_event(burbuja::evento);
    // El escáner de QR (cámara) solo existe en el cel
    #[cfg(mobile)]
    let constructor = constructor.plugin(tauri_plugin_barcode_scanner::init());
    let app = constructor
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(plugin_python())
        .setup(|_app| {
            #[cfg(not(target_os = "android"))]
            {
                let servicio = escritorio::iniciar(_app.handle())?;
                _app.manage(servicio);
                // Windows: que los links misiccord:// abran esta app (el instalador también lo registra)
                use tauri_plugin_deep_link::DeepLinkExt;
                let _ = _app.deep_link().register_all();
                #[cfg(windows)]
                barra::iniciar(_app.handle());
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![py, permiso_archivos, instalar_apk, medios, segundo_plano, compartir, sesion, burbuja, barra_tareas])
        .build(tauri::generate_context!())
        .expect("error while running tauri application");

    app.run(|_app, evento| {
        #[cfg(not(target_os = "android"))]
        if let tauri::RunEvent::Exit = evento {
            if let Some(s) = _app.try_state::<escritorio::Servicio>() {
                s.cerrar();
            }
        }
        #[cfg(target_os = "android")]
        let _ = evento;
    });
}
