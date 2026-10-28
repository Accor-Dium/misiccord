"""Paleta, fuentes e iconos de la interfaz."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap

FONDO = "#0a0f14"
PANEL = "#0d141b"
TARJETA = "#111a22"
TARJETA_HOVER = "#15212b"
BORDE = "#1c2a35"
BORDE_FUERTE = "#27394a"
TEXTO = "#e6edf3"
TENUE = "#8193a3"
CIAN = "#22d3ee"
AZUL = "#3b82f6"
VERDE = "#34d399"
ROJO = "#f87171"
AMBAR = "#fbbf24"

UI = '"Segoe UI Variable Text", "Segoe UI"'
MONO = '"Cascadia Mono", "Cascadia Code", Consolas'

# Glifos de Segoe Fluent Icons (Windows 11) / Segoe MDL2 Assets (Windows 10)
I_PLAY, I_PAUSA, I_ANTERIOR, I_SIGUIENTE = 0xE768, 0xE769, 0xE892, 0xE893
I_ALEATORIO, I_REPETIR, I_REPETIR_UNA, I_VOLUMEN, I_SILENCIO = 0xE8B1, 0xE8EE, 0xE8ED, 0xE767, 0xE74F
I_DESCARGA, I_CARPETA, I_REINTENTAR, I_BIBLIOTECA, I_LINK = 0xE896, 0xE8B7, 0xE72C, 0xE8F1, 0xE71B
I_BUSCAR, I_CERRAR, I_DETENER, I_PEGAR, I_RAYO, I_LIMPIAR = 0xE721, 0xE711, 0xE71A, 0xE77F, 0xE945, 0xE894
I_MUSICA, I_RELOJ = 0xEC4F, 0xE916
I_EXPANDIR, I_CONTRAER, I_COPIAR, I_LETRA = 0xE740, 0xE73F, 0xE8C8, 0xE720
I_ETIQUETA, I_DISCO, I_PERSONA, I_LISTA, I_ATRAS = 0xE895, 0xE93C, 0xE77B, 0xE8FD, 0xE72B
I_AGREGAR, I_EDITAR, I_BORRAR, I_ARRIBA, I_ABAJO = 0xE710, 0xE70F, 0xE74D, 0xE74A, 0xE74B


def fuente_iconos(px: int) -> QFont:
    f = QFont()
    f.setFamilies(["Segoe Fluent Icons", "Segoe MDL2 Assets"])
    f.setPixelSize(px)
    return f


def icono(glifo: int, color: str = TEXTO, px: int = 16) -> QIcon:
    pantalla = QGuiApplication.primaryScreen()
    dpr = pantalla.devicePixelRatio() if pantalla else 1.0
    pm = QPixmap(int(px * dpr), int(px * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setFont(fuente_iconos(px))
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, px, px), Qt.AlignCenter, chr(glifo))
    p.end()
    return QIcon(pm)


QSS = f"""
* {{ font-family: {UI}; font-size: 13px; color: {TEXTO}; }}
QMainWindow, #raiz {{ background: {FONDO}; }}
QToolTip {{ background: {TARJETA}; color: {TEXTO}; border: 1px solid {BORDE_FUERTE}; padding: 6px; }}

/* ---------- Barra lateral ---------- */
#lateral {{ background: {PANEL}; border-right: 1px solid {BORDE}; }}
#marca {{ font-size: 19px; font-weight: 700; }}
#marcaSub {{ font-family: {MONO}; font-size: 11px; color: {CIAN}; }}
#logo {{ background: {TARJETA}; border: 1px solid {BORDE_FUERTE}; border-radius: 10px; }}
#pegar {{ background: rgba(34,211,238,0.08); border: 1px solid rgba(34,211,238,0.45); border-radius: 8px;
          color: {CIAN}; font-weight: 600; padding: 10px; }}
#pegar:hover {{ background: rgba(34,211,238,0.16); }}
#nav {{ background: transparent; border: none; border-radius: 8px; text-align: left; padding: 10px 14px;
        color: {TENUE}; font-size: 14px; }}
#nav:hover {{ background: {TARJETA}; color: {TEXTO}; }}
#nav:checked {{ background: {TARJETA_HOVER}; color: {TEXTO}; }}
#estadoMotor {{ font-family: {MONO}; font-size: 11px; color: {TENUE}; }}

/* ---------- Entrada de URL ---------- */
#cajaUrl {{ background: {TARJETA}; border: 1px solid {BORDE_FUERTE}; border-radius: 10px; }}
#cajaUrl[foco="true"] {{ border-color: {CIAN}; }}
#url {{ background: transparent; border: none; font-size: 15px; padding: 10px 4px; selection-background-color: {AZUL}; }}
#fuentes {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 10px; }}
#fuente {{ font-family: {MONO}; font-size: 12px; padding: 4px 8px; border-radius: 5px;
           border: 1px solid {BORDE_FUERTE}; color: {TENUE}; }}
#fuente[activa="spotify"] {{ color: #1ed760; border-color: #1ed760; background: rgba(30,215,96,0.12); }}
#fuente[activa="ytmusic"], #fuente[activa="youtube"] {{ color: #ff5c5c; border-color: #ff5c5c; background: rgba(255,92,92,0.12); }}
#fuente[activa="soundcloud"] {{ color: #ff8a3d; border-color: #ff8a3d; background: rgba(255,138,61,0.12); }}
#fuente[activa="otro"] {{ color: {CIAN}; border-color: {CIAN}; background: rgba(34,211,238,0.12); }}

/* ---------- Botones ---------- */
QPushButton {{ background: {TARJETA}; border: 1px solid {BORDE_FUERTE}; border-radius: 8px; padding: 8px 14px; }}
QPushButton:hover {{ background: {TARJETA_HOVER}; border-color: #34495c; }}
QPushButton:disabled {{ color: #4a5966; border-color: {BORDE}; }}
#secundario {{ font-family: {MONO}; font-size: 13px; padding: 6px 14px; }}
#reintentarTodos {{ font-family: {MONO}; font-size: 13px; padding: 6px 14px; color: #fca5a5; border-color: #7f1d1d;
                    background: rgba(248,113,113,0.08); }}
#reintentarTodos:disabled {{ color: #4a5966; border-color: {BORDE}; background: {TARJETA}; }}
#analizar {{ color: {CIAN}; border-color: rgba(34,211,238,0.6); background: rgba(34,211,238,0.06);
             font-weight: 600; font-size: 14px; padding: 11px 22px; }}
#analizar:hover {{ background: rgba(34,211,238,0.14); }}
#iniciar {{ border: none; border-radius: 10px; font-size: 15px; font-weight: 700; color: #04121a; padding: 0 26px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {CIAN}, stop:1 #60a5fa); }}
#iniciar:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #67e8f9, stop:1 #93c5fd); }}
#iniciar:disabled {{ background: {TARJETA}; color: #4a5966; border: 1px solid {BORDE}; }}
#examinar {{ padding: 6px 12px; }}
#segmento {{ font-family: {MONO}; padding: 4px 0; min-width: 30px; border-radius: 6px; color: {TENUE}; }}
#segmento:checked {{ color: {CIAN}; border-color: {CIAN}; background: rgba(34,211,238,0.12); }}

/* ---------- Tarjetas de configuración ---------- */
#tarjeta {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 10px; }}
#etiqueta {{ font-family: {MONO}; font-size: 11px; color: {TENUE}; letter-spacing: 1px; }}
#valorMono {{ font-family: {MONO}; font-size: 13px; }}
#libre {{ font-family: {MONO}; font-size: 11px; color: {VERDE}; border: 1px solid rgba(52,211,153,0.45);
          background: rgba(52,211,153,0.08); border-radius: 5px; padding: 2px 6px; }}
QComboBox {{ background: {FONDO}; border: 1px solid {BORDE_FUERTE}; border-radius: 7px; padding: 6px 10px;
             font-family: {MONO}; }}
QComboBox:hover {{ border-color: #34495c; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {TARJETA}; border: 1px solid {BORDE_FUERTE}; outline: none;
                               selection-background-color: {TARJETA_HOVER}; selection-color: {CIAN}; padding: 4px; }}
QCheckBox {{ color: {TENUE}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDE_FUERTE}; background: {FONDO}; }}
QCheckBox::indicator:checked {{ background: {CIAN}; border-color: {CIAN}; }}

/* ---------- Monitor ---------- */
#tituloSeccion {{ font-size: 19px; font-weight: 700; }}
#punto {{ background: {CIAN}; border-radius: 6px; }}
#punto[activo="false"] {{ background: #3a4b5a; }}
#stat {{ font-family: {MONO}; font-size: 13px; color: {TENUE}; }}
#velocidad {{ font-family: {MONO}; font-size: 13px; color: {CIAN}; border: 1px solid rgba(34,211,238,0.45);
              background: rgba(34,211,238,0.08); border-radius: 5px; padding: 3px 8px; }}
#separador {{ background: {BORDE}; max-height: 1px; min-height: 1px; }}
#cabecera QLabel {{ font-family: {MONO}; font-size: 11px; color: {TENUE}; letter-spacing: 1px; }}
#vacio {{ color: {TENUE}; font-size: 14px; }}

/* ---------- Filas ---------- */
#fila {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 8px; }}
#fila:hover {{ background: {TARJETA}; }}
#fila[estado="activo"] {{ border-color: rgba(34,211,238,0.55); background: #0e1c24; }}
#fila[estado="error"] {{ border-color: #7f1d1d; background: #1d0f13; }}
#num {{ font-family: {MONO}; font-size: 14px; color: {TENUE}; }}
#num[activo="true"] {{ color: {CIAN}; }}
#num[error="true"] {{ color: {ROJO}; }}
#portada {{ background: {TARJETA_HOVER}; border-radius: 6px; }}
#tituloCancion {{ font-size: 14px; font-weight: 600; }}
#artistaCancion {{ color: {TENUE}; }}
#formato {{ font-family: {MONO}; font-size: 12px; color: {CIAN}; border: 1px solid rgba(34,211,238,0.35);
            background: rgba(34,211,238,0.06); border-radius: 5px; padding: 4px 8px; }}
#tamano {{ font-family: {MONO}; font-size: 13px; }}
#progIzq {{ font-size: 12px; color: {CIAN}; }}
#progDer {{ font-size: 12px; color: {TENUE}; }}
#progIzq[error="true"], #progDer[error="true"] {{ color: {ROJO}; }}
QProgressBar {{ background: {BORDE}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2dd4bf, stop:1 {CIAN}); }}
QProgressBar[error="true"]::chunk {{ background: {ROJO}; }}
#chip {{ font-size: 12px; border-radius: 5px; padding: 4px 8px; border: 1px solid {BORDE_FUERTE};
         color: {TENUE}; background: {TARJETA}; }}
#chip[tipo="ok"] {{ color: {VERDE}; border-color: rgba(52,211,153,0.5); background: rgba(52,211,153,0.08); }}
#chip[tipo="activo"] {{ color: {CIAN}; border-color: rgba(34,211,238,0.6); background: rgba(34,211,238,0.10); }}
#chip[tipo="error"] {{ color: {ROJO}; border-color: #7f1d1d; background: rgba(248,113,113,0.10); }}
#accion {{ background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 4px; }}
#accion:hover {{ background: {TARJETA_HOVER}; border-color: {BORDE_FUERTE}; }}
#accion[tipo="reintentar"] {{ color: #fca5a5; border-color: #7f1d1d; background: rgba(248,113,113,0.08);
                              font-family: {MONO}; font-size: 12px; padding: 4px 10px; }}

/* ---------- Biblioteca ---------- */
#buscar {{ background: {TARJETA}; border: 1px solid {BORDE_FUERTE}; border-radius: 8px; padding: 9px 12px; font-size: 14px; }}
#buscar:focus {{ border-color: {CIAN}; }}
#lista {{ background: transparent; border: none; outline: none; }}
#lista::item {{ background: {PANEL}; border: 1px solid {BORDE}; border-radius: 8px; padding: 10px 14px; margin: 3px 0; }}
#lista::item:hover {{ background: {TARJETA}; }}
#lista::item:selected {{ border-color: rgba(34,211,238,0.55); background: #0e1c24; color: {TEXTO}; }}

/* ---------- Reproductor ---------- */
#reproductor {{ background: {PANEL}; border-top: 1px solid {BORDE}; }}
#rpTitulo {{ font-size: 17px; font-weight: 700; }}
#rpArtista {{ color: {TENUE}; font-size: 14px; }}
#rpChip {{ font-family: {MONO}; font-size: 11px; color: {CIAN}; border: 1px solid rgba(34,211,238,0.35);
           border-radius: 4px; padding: 2px 6px; }}
#rpTiempo {{ font-family: {MONO}; font-size: 13px; color: {TENUE}; }}
#control {{ background: transparent; border: none; border-radius: 18px; padding: 6px; }}
#control:hover {{ background: {TARJETA_HOVER}; }}
#control[activo="true"] {{ background: rgba(34,211,238,0.12); }}
#playGrande {{ border: none; border-radius: 28px; background: {CIAN}; }}
#playGrande:hover {{ background: #67e8f9; }}
QSlider::groove:horizontal {{ height: 6px; background: {BORDE}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {CIAN}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; background: {TEXTO}; }}

#fondoLista {{ background: {FONDO}; }}
QDialog {{ background: {FONDO}; }}
#chip[tipo="info"] {{ color: #93c5fd; border-color: rgba(96,165,250,0.5); background: rgba(96,165,250,0.10); }}
#tabla {{ background: transparent; border: 1px solid {BORDE}; border-radius: 10px; outline: none;
          alternate-background-color: transparent; selection-background-color: rgba(34,211,238,0.12); }}
#tabla::item {{ padding: 0 8px; border-bottom: 1px solid {BORDE}; }}
#tabla::item:selected {{ background: rgba(34,211,238,0.12); color: {TEXTO}; }}
#tabla::item:hover {{ background: {TARJETA}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: {PANEL}; color: {TENUE}; border: none; border-bottom: 1px solid {BORDE};
                        padding: 8px; font-family: {MONO}; font-size: 11px; letter-spacing: 1px; }}
QHeaderView::section:first {{ border-top-left-radius: 10px; }}
QHeaderView::section:last {{ border-top-right-radius: 10px; }}
QTableCornerButton::section {{ background: {PANEL}; border: none; }}
#tira {{ background: transparent; border: none; outline: none; }}
#tira::item {{ border-radius: 10px; padding: 8px 4px; color: {TEXTO}; }}
#tira::item:hover {{ background: {TARJETA}; }}
#tira::item:selected {{ background: {TARJETA_HOVER}; color: {CIAN}; }}
#seccionInicio {{ font-size: 18px; font-weight: 700; padding-top: 14px; }}
#rejilla {{ background: transparent; border: none; outline: none; }}
#rejilla::item {{ border-radius: 10px; padding: 8px 4px; color: {TEXTO}; }}
#rejilla::item:hover {{ background: {TARJETA}; }}
#rejilla::item:selected {{ background: {TARJETA_HOVER}; color: {CIAN}; }}
QInputDialog QLineEdit {{ background: {TARJETA}; border: 1px solid {BORDE_FUERTE}; border-radius: 7px; padding: 7px 10px; }}
#pestana {{ font-family: {MONO}; font-size: 12px; letter-spacing: 1px; color: {TENUE}; padding: 6px 14px;
            border-radius: 14px; border: 1px solid {BORDE_FUERTE}; background: rgba(13,20,27,0.55); }}
#pestana:hover {{ color: {TEXTO}; }}
#pestana:checked {{ color: {CIAN}; border-color: rgba(34,211,238,0.6); background: rgba(34,211,238,0.10); }}
#fuenteLetra {{ font-family: {MONO}; font-size: 11px; color: {TENUE}; }}
#cola {{ background: rgba(13,20,27,0.55); border: 1px solid {BORDE}; border-radius: 10px; outline: none; padding: 6px; }}
#cola::item {{ border-radius: 6px; padding: 8px 6px; color: {TEXTO}; }}
#cola::item:hover {{ background: rgba(34,211,238,0.10); }}
#vpSobre {{ font-family: {MONO}; font-size: 12px; color: {CIAN}; letter-spacing: 2px; }}
#vpTitulo {{ font-size: 38px; font-weight: 800; }}
#vpArtista {{ font-size: 20px; color: {TEXTO}; }}
#vpAlbum {{ font-size: 15px; color: {TENUE}; }}
#vpPortada {{ background: {TARJETA}; border-radius: 16px; }}
#playXL {{ border: none; border-radius: 38px; background: {CIAN}; }}
#playXL:hover {{ background: #67e8f9; }}
#playGrande:pressed, #playXL:pressed {{ background: #0891b2; }}
#control:pressed {{ background: {BORDE_FUERTE}; }}
QSlider::handle:horizontal:hover {{ background: {CIAN}; }}
QSlider::sub-page:horizontal:hover {{ background: #67e8f9; }}
QMenu {{ background: {TARJETA}; border: 1px solid {BORDE_FUERTE}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 7px 22px 7px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background: {TARJETA_HOVER}; color: {CIAN}; }}
QMenu::separator {{ height: 1px; background: {BORDE}; margin: 5px 8px; }}
QMenu::icon {{ padding-left: 8px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDE_FUERTE}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #34495c; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ height: 0; background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDE_FUERTE}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal, QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ width: 0; background: none; }}
QMessageBox {{ background: {TARJETA}; }}
"""
