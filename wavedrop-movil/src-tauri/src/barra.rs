//! Windows: botones de anterior / reproducir-pausar / siguiente en la vista previa de la barra de tareas
//! (la miniatura que sale al pasar el mouse sobre el ícono de Misiccord) y el nombre de la canción en su descripción.
//!
//! Va con `ITaskbarList3::ThumbBarAddButtons`. Los clics llegan a la ventana como `WM_COMMAND` con `THBN_CLICKED`:
//! por eso la ventana principal se "subclasifica" y cada clic se manda a la interfaz como el evento `barra-control`.
//! Todo lo de COM pasa en el hilo de la ventana (`run_on_main_thread`).

use std::cell::RefCell;
use std::sync::OnceLock;

use tauri::{AppHandle, Emitter, Manager};
use windows::core::w;
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::Graphics::Gdi::{CreateBitmap, CreateDIBSection, DeleteObject, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS, HGDIOBJ};
use windows::Win32::System::Com::{CoCreateInstance, CLSCTX_INPROC_SERVER};
use windows::Win32::UI::Shell::{
    DefSubclassProc, ITaskbarList3, SetWindowSubclass, TaskbarList, THBF_DISABLED, THBF_ENABLED, THB_FLAGS, THB_ICON,
    THB_TOOLTIP, THUMBBUTTON, THUMBBUTTONFLAGS, THUMBBUTTONMASK,
};
use windows::Win32::UI::WindowsAndMessaging::{CreateIconIndirect, RegisterWindowMessageW, HICON, ICONINFO, WM_COMMAND};

const THBN_CLICKED: u32 = 0x1800;
const ANTERIOR: u32 = 1;
const PLAY: u32 = 2;
const SIGUIENTE: u32 = 3;

static APP: OnceLock<AppHandle> = OnceLock::new();

/// Lo que muestran los botones; se guarda para volver a ponerlos si Explorer se reinicia.
#[derive(Clone, Default)]
struct Estado {
    hay: bool,
    sonando: bool,
    textos: [String; 4], // anterior, reproducir, pausar, siguiente (en el idioma de la app)
}

thread_local! {
    static BARRA: RefCell<Option<ITaskbarList3>> = const { RefCell::new(None) };
    static ICONOS: RefCell<Option<[HICON; 4]>> = const { RefCell::new(None) };
    static ESTADO: RefCell<Estado> = RefCell::new(Estado::default());
    static VENTANA: RefCell<Option<HWND>> = const { RefCell::new(None) };
}

/// Engancha la ventana principal. Los botones se agregan cuando Windows avisa que ya existe su botón en la barra.
pub fn iniciar(app: &AppHandle) {
    let _ = APP.set(app.clone());
    let Some(ventana) = app.get_webview_window("main") else { return };
    let Ok(hwnd) = ventana.hwnd() else { return };
    let crudo = hwnd.0 as isize; // un puntero no puede cruzar de hilo: va como número
    let _ = app.run_on_main_thread(move || unsafe {
        let hwnd = HWND(crudo as *mut _);
        VENTANA.with(|v| *v.borrow_mut() = Some(hwnd));
        let _ = SetWindowSubclass(hwnd, Some(subclase), 0x4D53, 0);
        // Si el botón de la barra ya existía antes de engancharse, no llegará el aviso: se intenta de una vez
        agregar_botones(hwnd);
    });
}

/// Pone el estado de lo que suena: título de la ventana (sale en la vista previa) y el botón de reproducir o pausar.
pub fn actualizar(app: &AppHandle, titulo: String, artista: String, hay: bool, sonando: bool, textos: [String; 4]) {
    if let Some(v) = app.get_webview_window("main") {
        let nombre = if hay && !titulo.is_empty() {
            if artista.is_empty() { format!("{titulo} · Misiccord") } else { format!("{titulo} – {artista} · Misiccord") }
        } else {
            "Misiccord".to_string()
        };
        let _ = v.set_title(&nombre);
    }
    let _ = app.run_on_main_thread(move || {
        ESTADO.with(|e| *e.borrow_mut() = Estado { hay, sonando, textos });
        if let Some(hwnd) = VENTANA.with(|v| *v.borrow()) {
            unsafe { poner_botones(hwnd, false) };
        }
    });
}

unsafe extern "system" fn subclase(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM, _id: usize, _datos: usize) -> LRESULT {
    static CREADO: OnceLock<u32> = OnceLock::new();
    let creado = *CREADO.get_or_init(|| unsafe { RegisterWindowMessageW(w!("TaskbarButtonCreated")) });
    if msg == creado {
        // También llega si Explorer se reinicia: entonces hay que volver a poner los botones
        BARRA.with(|b| *b.borrow_mut() = None);
        unsafe { agregar_botones(hwnd) };
    } else if msg == WM_COMMAND && ((wparam.0 >> 16) as u32 & 0xFFFF) == THBN_CLICKED {
        let accion = match (wparam.0 & 0xFFFF) as u32 {
            ANTERIOR => "anterior",
            PLAY => "alternar",
            SIGUIENTE => "siguiente",
            _ => "",
        };
        if !accion.is_empty() {
            if let Some(app) = APP.get() {
                let _ = app.emit_to("main", "barra-control", serde_json::json!({ "accion": accion }));
            }
            return LRESULT(0);
        }
    }
    unsafe { DefSubclassProc(hwnd, msg, wparam, lparam) }
}

unsafe fn agregar_botones(hwnd: HWND) {
    let lista = BARRA.with(|b| b.borrow().clone());
    if lista.is_none() {
        let Ok(nueva) = (unsafe { CoCreateInstance::<_, ITaskbarList3>(&TaskbarList, None, CLSCTX_INPROC_SERVER) }) else { return };
        if unsafe { nueva.HrInit() }.is_err() {
            return;
        }
        BARRA.with(|b| *b.borrow_mut() = Some(nueva));
    }
    unsafe { poner_botones(hwnd, true) };
}

unsafe fn poner_botones(hwnd: HWND, agregar: bool) {
    let Some(lista) = BARRA.with(|b| b.borrow().clone()) else { return };
    let iconos = ICONOS.with(|i| *i.borrow_mut().get_or_insert_with(|| unsafe { crear_iconos() }));
    let e = ESTADO.with(|e| e.borrow().clone());
    let texto = |i: usize, por_defecto: &str| if e.textos[i].is_empty() { por_defecto.to_string() } else { e.textos[i].clone() };
    let flags = if e.hay { THBF_ENABLED } else { THBF_DISABLED };
    let botones = [
        boton(ANTERIOR, iconos[0], &texto(0, "Anterior"), flags),
        if e.sonando { boton(PLAY, iconos[2], &texto(2, "Pausar"), flags) } else { boton(PLAY, iconos[1], &texto(1, "Reproducir"), flags) },
        boton(SIGUIENTE, iconos[3], &texto(3, "Siguiente"), flags),
    ];
    let _ = if agregar {
        unsafe { lista.ThumbBarAddButtons(hwnd, &botones) }
    } else {
        unsafe { lista.ThumbBarUpdateButtons(hwnd, &botones) }
    };
}

fn boton(id: u32, icono: HICON, texto: &str, flags: THUMBBUTTONFLAGS) -> THUMBBUTTON {
    let mut b = THUMBBUTTON {
        dwMask: THUMBBUTTONMASK(THB_ICON.0 | THB_TOOLTIP.0 | THB_FLAGS.0),
        iId: id,
        hIcon: icono,
        dwFlags: flags,
        ..Default::default()
    };
    let utf16: Vec<u16> = texto.encode_utf16().take(259).collect();
    b.szTip[..utf16.len()].copy_from_slice(&utf16);
    b
}

// ---------- Íconos ----------
// Se dibujan aquí (32×32, con antialiasing) con las mismas formas que los de la interfaz (componentes/Icono.svelte):
// así no hace falta cargar archivos .ico. El color sigue al tema de Windows: la vista previa es clara con el tema claro
// y un ícono blanco ahí no se ve.

/// Blanco con el tema oscuro de la barra de tareas, casi negro con el claro
fn color_iconos() -> u32 {
    use windows::Win32::System::Registry::{RegGetValueW, HKEY_CURRENT_USER, RRF_RT_REG_DWORD};
    let mut claro: u32 = 0;
    let mut tam = std::mem::size_of::<u32>() as u32;
    let ok = unsafe {
        RegGetValueW(
            HKEY_CURRENT_USER,
            w!(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"),
            w!("SystemUsesLightTheme"),
            RRF_RT_REG_DWORD,
            None,
            Some(&mut claro as *mut u32 as *mut _),
            Some(&mut tam),
        )
    }
    .is_ok();
    if ok && claro == 1 { 0x1F1F1F } else { 0xFFFFFF }
}

const LADO: usize = 32;

/// ¿El punto está dentro del triángulo? (coordenadas en la cuadrícula de 24 de los íconos de la interfaz)
fn en_triangulo(p: (f32, f32), a: (f32, f32), b: (f32, f32), c: (f32, f32)) -> bool {
    let lado = |p: (f32, f32), q: (f32, f32), r: (f32, f32)| (p.0 - r.0) * (q.1 - r.1) - (q.0 - r.0) * (p.1 - r.1);
    let (d1, d2, d3) = (lado(p, a, b), lado(p, b, c), lado(p, c, a));
    !((d1 < 0.0 || d2 < 0.0 || d3 < 0.0) && (d1 > 0.0 || d2 > 0.0 || d3 > 0.0))
}

fn en_rect(p: (f32, f32), x0: f32, y0: f32, x1: f32, y1: f32) -> bool {
    p.0 >= x0 && p.0 <= x1 && p.1 >= y0 && p.1 <= y1
}

fn forma(cual: usize, p: (f32, f32)) -> bool {
    match cual {
        0 => en_triangulo(p, (19.0, 5.5), (19.0, 18.5), (9.5, 12.0)) || en_rect(p, 4.5, 5.0, 7.0, 19.0), // anterior
        1 => en_triangulo(p, (7.0, 4.5), (7.0, 19.5), (19.5, 12.0)),                                     // reproducir
        2 => en_rect(p, 7.0, 4.0, 10.5, 20.0) || en_rect(p, 13.5, 4.0, 17.0, 20.0),                       // pausar
        _ => en_triangulo(p, (5.0, 5.5), (5.0, 18.5), (14.5, 12.0)) || en_rect(p, 17.0, 5.0, 19.5, 19.0), // siguiente
    }
}

unsafe fn crear_iconos() -> [HICON; 4] {
    let color = color_iconos();
    [0, 1, 2, 3].map(|cual| unsafe { crear_icono(cual, color) })
}

unsafe fn crear_icono(cual: usize, color: u32) -> HICON {
    // 4×4 muestras por pixel para que las orillas salgan suaves
    let mut pixeles = vec![0u32; LADO * LADO];
    for y in 0..LADO {
        for x in 0..LADO {
            let mut dentro = 0;
            for sy in 0..4 {
                for sx in 0..4 {
                    let px = (x as f32 + (sx as f32 + 0.5) / 4.0) * 24.0 / LADO as f32;
                    let py = (y as f32 + (sy as f32 + 0.5) / 4.0) * 24.0 / LADO as f32;
                    dentro += forma(cual, (px, py)) as u32;
                }
            }
            let alfa = dentro * 255 / 16;
            // BGRA: el color y la transparencia en el alfa (los íconos no van premultiplicados)
            pixeles[(LADO - 1 - y) * LADO + x] = (alfa << 24) | color;
        }
    }
    let info = BITMAPINFO {
        bmiHeader: BITMAPINFOHEADER {
            biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
            biWidth: LADO as i32,
            biHeight: LADO as i32,
            biPlanes: 1,
            biBitCount: 32,
            biCompression: BI_RGB.0,
            ..Default::default()
        },
        ..Default::default()
    };
    let mut bits = std::ptr::null_mut();
    let Ok(color) = (unsafe { CreateDIBSection(None, &info, DIB_RGB_COLORS, &mut bits, None, 0) }) else { return HICON::default() };
    unsafe { std::ptr::copy_nonoverlapping(pixeles.as_ptr(), bits as *mut u32, pixeles.len()) };
    let mascara = unsafe { CreateBitmap(LADO as i32, LADO as i32, 1, 1, None) };
    let icono = ICONINFO { fIcon: true.into(), xHotspot: 0, yHotspot: 0, hbmMask: mascara, hbmColor: color };
    let resultado = unsafe { CreateIconIndirect(&icono) }.unwrap_or_default();
    unsafe {
        let _ = DeleteObject(HGDIOBJ(color.0));
        let _ = DeleteObject(HGDIOBJ(mascara.0));
    }
    resultado
}
