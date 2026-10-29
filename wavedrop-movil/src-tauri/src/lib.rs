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
        .plugin(tauri_plugin_updater::Builder::new().build());
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
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![py, permiso_archivos, instalar_apk, medios])
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
