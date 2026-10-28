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
                std::thread::spawn(move || loop {
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
    use std::sync::{mpsc, Mutex};
    use tauri::{AppHandle, Emitter, Manager};

    pub struct Servicio {
        entrada: Mutex<ChildStdin>,
        pendientes: Mutex<HashMap<u64, mpsc::Sender<String>>>,
        siguiente: AtomicU64,
        proceso: Mutex<Child>,
    }

    /// Empaquetado: resources/servicio/wavedrop-servicio.exe. En desarrollo: el Python del venv del proyecto.
    fn comando(app: &AppHandle) -> Command {
        if let Ok(dir) = app.path().resource_dir() {
            let exe = dir.join("servicio").join("wavedrop-servicio.exe");
            if exe.exists() {
                return Command::new(exe);
            }
        }
        let raiz = Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
        let python = std::env::var("WAVEDROP_PYTHON")
            .map(PathBuf::from)
            .unwrap_or_else(|_| raiz.join("..").join("venv").join("Scripts").join("python.exe"));
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
        let mut hijo = c.spawn().map_err(|e| format!("No se pudo arrancar el servicio de Python: {e}"))?;
        let entrada = hijo.stdin.take().ok_or("sin stdin")?;
        let salida = hijo.stdout.take().ok_or("sin stdout")?;

        let app2 = app.clone();
        std::thread::spawn(move || {
            for linea in BufReader::new(salida).lines() {
                let Ok(linea) = linea else { break };
                let Ok(v) = serde_json::from_str::<serde_json::Value>(&linea) else { continue };
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
            let linea = serde_json::json!({ "id": id, "funcion": funcion, "datos": datos }).to_string();
            {
                let mut e = self.entrada.lock().unwrap();
                writeln!(e, "{linea}").and_then(|_| e.flush()).map_err(|e| e.to_string())?;
            }
            rx.recv().map_err(|_| "El servicio de Python se cerró".to_string())
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(plugin_python())
        .setup(|_app| {
            #[cfg(not(target_os = "android"))]
            {
                let servicio = escritorio::iniciar(_app.handle())?;
                _app.manage(servicio);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![py])
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
