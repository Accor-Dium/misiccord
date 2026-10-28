"""WaveDrop: descargador de playlists con interfaz gráfica y reproductor."""
import base64
import bisect
import faulthandler
import math
import os
import platform
import random
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mutagen
from PySide6.QtCore import (
    QEasingCurve, QObject, QPropertyAnimation, QRectF, QSettings, QSize, QStandardPaths, Qt, QThread, QTimer, QUrl,
    QVariantAnimation, Signal, qInstallMessageHandler,
)
from PySide6.QtGui import (
    QColor, QCursor, QDesktopServices, QFont, QFontMetrics, QIcon, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPalette, QPixmap, QShortcut,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QAbstractItemView,
    QDialog,
    QGraphicsOpacityEffect,
    QHeaderView,
    QInputDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

import biblioteca
import explorar
import letras
import musicbrainz
import nucleo
from estilos import (
    AZUL, BORDE_FUERTE, CIAN, FONDO, QSS, ROJO, TARJETA, TENUE, TEXTO,
    I_ALEATORIO, I_ANTERIOR, I_BIBLIOTECA, I_BUSCAR, I_CARPETA, I_CERRAR, I_CONTRAER, I_COPIAR, I_DESCARGA,
    I_EXPANDIR, I_LETRA, I_LIMPIAR, I_ETIQUETA, I_DISCO, I_PERSONA, I_LISTA, I_ATRAS, I_AGREGAR, I_EDITAR,
    I_BORRAR, I_ARRIBA, I_ABAJO,
    I_LINK, I_PAUSA, I_PEGAR, I_PLAY, I_RAYO, I_REINTENTAR, I_REPETIR, I_REPETIR_UNA, I_SIGUIENTE, I_VOLUMEN,
    I_SILENCIO, I_MUSICA,
    icono,
)

NOMBRE_APP = "WaveDrop"
VERSION = "2.2"

# Estados de una canción
ESPERA, COLA, BUSCANDO, DESCARGANDO, CONVIRTIENDO = "En espera", "En cola", "Buscando en YT Music", "Descargando", "Convirtiendo"
LISTO, YA, FALLO, CANCELADA = "Listo", "Ya descargada", "Error", "Cancelada"
ETIQUETANDO, EXISTE = "Etiquetando", "En tu biblioteca"
ACTIVOS = {BUSCANDO, DESCARGANDO, CONVIRTIENDO, ETIQUETANDO}
CHIP = {  # texto, tipo de estilo
    ESPERA: ("En espera", "neutro"), COLA: ("En cola", "neutro"), BUSCANDO: ("Buscando…", "activo"),
    DESCARGANDO: ("Descargando…", "activo"), CONVIRTIENDO: ("Convirtiendo…", "activo"),
    LISTO: ("Listo", "ok"), YA: ("Ya estaba", "ok"), FALLO: ("Error", "error"), CANCELADA: ("Cancelada", "neutro"),
    ETIQUETANDO: ("Etiquetando…", "activo"), EXISTE: ("Ya la tienes", "info"),
}

# Anchos de columna compartidos por la cabecera y las filas
C_NUM, C_PORTADA, C_FORMATO, C_TAMANO, C_PROGRESO, C_ESTADO, C_ACCION = 30, 48, 124, 70, 200, 104, 120
ESPACIO = 12


def recurso(nombre: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / nombre


def fmt_tiempo(ms: int) -> str:
    s = max(ms, 0) // 1000
    return f"{s // 60}:{s % 60:02d}"


def fmt_bytes(n: float | None) -> str:
    if not n:
        return "—"
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unidad == "TB":
            return f"{n:.1f} {unidad}" if unidad not in ("B", "KB") else f"{n:.0f} {unidad}"
        n /= 1024


def set_prop(w: QWidget, nombre: str, valor) -> None:
    """Cambia una propiedad usada por el QSS y vuelve a aplicar el estilo."""
    if w.property(nombre) != valor:
        w.setProperty(nombre, valor)
        w.style().unpolish(w)
        w.style().polish(w)


def redondear(pm: QPixmap, lado: int, radio: int) -> QPixmap:
    """Recorta al centro en cuadrado y redondea las esquinas."""
    dpr = 2.0
    escalado = pm.scaled(int(lado * dpr), int(lado * dpr), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (escalado.width() - int(lado * dpr)) // 2
    y = (escalado.height() - int(lado * dpr)) // 2
    escalado = escalado.copy(x, y, int(lado * dpr), int(lado * dpr))
    salida = QPixmap(int(lado * dpr), int(lado * dpr))
    salida.fill(Qt.transparent)
    p = QPainter(salida)
    p.setRenderHint(QPainter.Antialiasing)
    camino = QPainterPath()
    camino.addRoundedRect(QRectF(0, 0, lado * dpr, lado * dpr), radio * dpr, radio * dpr)
    p.setClipPath(camino)
    p.drawPixmap(0, 0, escalado)
    p.end()
    salida.setDevicePixelRatio(dpr)
    return salida


def portada_incrustada(ruta: str) -> QPixmap | None:
    """Saca la portada guardada dentro del archivo de audio (MP3, M4A u Opus)."""
    try:
        f = mutagen.File(ruta)
    except Exception:
        return None
    if f is None or f.tags is None:
        return None
    datos = None
    try:
        for clave in f.tags.keys():
            if clave.startswith("APIC"):
                datos = f.tags[clave].data
                break
        if datos is None and "covr" in f.tags:
            datos = bytes(f.tags["covr"][0])
        if datos is None and "metadata_block_picture" in f.tags:
            from mutagen.flac import Picture
            datos = Picture(base64.b64decode(f.tags["metadata_block_picture"][0])).data
    except Exception:
        return None
    if not datos:
        return None
    pm = QPixmap()
    return pm if pm.loadFromData(datos) else None


def metadatos(ruta: Path, carpeta: str) -> dict:
    """Título, artista y álbum guardados en el archivo; si faltan, se sacan de la ruta."""
    try:
        partes = ruta.relative_to(carpeta).parts
    except ValueError:
        partes = (ruta.name,)
    datos = {"titulo": ruta.stem, "artista": partes[0] if len(partes) > 1 else "", "album": ""}
    try:
        f = mutagen.File(ruta, easy=True)
        if f is not None and f.tags is not None:
            for clave, tag in (("titulo", "title"), ("artista", "artist"), ("album", "album")):
                valor = f.tags.get(tag)
                if valor:
                    datos[clave] = str(valor[0])
    except Exception:
        pass
    return datos


def abrir_en_explorador(ruta: Path) -> None:
    if ruta.is_file():
        subprocess.Popen(["explorer", "/select,", str(ruta)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta)))


class LabelRecortado(QLabel):
    """QLabel que pone "…" cuando el texto no cabe."""

    def __init__(self, texto="", modo=Qt.ElideRight):
        super().__init__(texto)
        self.modo = modo
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(20)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        texto = self.fontMetrics().elidedText(self.text(), self.modo, self.width())
        p.drawText(self.rect(), int(self.alignment() | Qt.AlignVCenter), texto)


class Imagenes(QObject):
    """Descarga miniaturas una sola vez y las reparte a quien las pidió."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.red = QNetworkAccessManager(self)
        self.cache: dict[str, QPixmap] = {}
        self.esperando: dict[str, list] = {}

    def pedir(self, url: str | None, cb) -> None:
        if not url:
            return
        if url in self.cache:
            if not self.cache[url].isNull():
                cb(self.cache[url])
            return
        if url in self.esperando:
            self.esperando[url].append(cb)
            return
        self.esperando[url] = [cb]
        resp = self.red.get(QNetworkRequest(QUrl(url)))
        resp.finished.connect(lambda r=resp, u=url: self._lista(r, u))

    def _lista(self, resp, url):
        pm = QPixmap()
        pm.loadFromData(resp.readAll().data())
        resp.deleteLater()
        self.cache[url] = pm
        for cb in self.esperando.pop(url, []):
            if not pm.isNull():
                try:
                    cb(pm)
                except RuntimeError:  # la fila ya se borró
                    pass


# ---------- Trabajo en segundo plano ----------

class Analizador(QThread):
    listo = Signal(object)  # nucleo.Coleccion
    fallo = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            self.listo.emit(nucleo.obtener_coleccion(self.url))
        except Exception as e:
            self.fallo.emit(str(e))


class Gestor(QObject):
    """Reparte las descargas entre varios hilos y avisa el progreso con señales."""

    estado = Signal(int, str, int, float, float, str)  # fila, estado, %, bytes/s, eta, detalle
    resultado = Signal(int, object)  # fila, nucleo.Resultado
    terminado = Signal()

    def __init__(self):
        super().__init__()
        self.pool: ThreadPoolExecutor | None = None
        self.descargador: nucleo.Descargador | None = None
        self.corriendo = threading.Event()
        self.corriendo.set()
        self.cancelados: set[int] = set()
        self.detenido = False
        self.pendientes = 0
        self.postproceso = None  # función(Resultado) que corre en el hilo después de cada descarga
        self.candado = threading.Lock()

    @property
    def activo(self) -> bool:
        return self.pendientes > 0

    def encolar(self, descargador: nucleo.Descargador, filas: list[tuple[int, nucleo.Entrada]], hilos: int):
        if self.pool is None:
            self.descargador = descargador
            self.pool = ThreadPoolExecutor(max_workers=hilos)
            self.detenido = False
        for fila, entrada in filas:
            self.cancelados.discard(fila)
            with self.candado:
                self.pendientes += 1
            self.estado.emit(fila, COLA, 0, 0, 0, "")
            self.pool.submit(self._tarea, fila, entrada)

    def cancelar(self, fila: int):
        self.cancelados.add(fila)

    def pausar(self, pausa: bool):
        if pausa:
            self.corriendo.clear()
        else:
            self.corriendo.set()

    def detener(self):
        self.detenido = True
        self.corriendo.set()
        if self.pool:
            self.pool.shutdown(wait=True, cancel_futures=True)

    def _cancelada(self, fila):
        return self.detenido or fila in self.cancelados

    def _tarea(self, fila: int, entrada: nucleo.Entrada):
        try:
            while not self.corriendo.wait(0.3):  # en pausa: no empezar nuevas
                if self._cancelada(fila):
                    break
            if self._cancelada(fila):
                self.estado.emit(fila, CANCELADA, 0, 0, 0, "")
                return
            if self.descargador.ya_descargada(entrada):
                self.estado.emit(fila, YA, 100, 0, 0, "")
                return

            def progreso(est, pct, vel, eta):
                self.estado.emit(fila, est, pct, float(vel or 0), float(eta or 0), "")

            res = self.descargador.descargar(entrada, progreso, lambda: self._cancelada(fila))
            if self.postproceso:
                self.estado.emit(fila, ETIQUETANDO, 100, 0, 0, "")
                try:
                    self.postproceso(res)
                except Exception:
                    print("Postproceso falló:\n" + traceback.format_exc(), flush=True)
            self.resultado.emit(fila, res)
            self.estado.emit(fila, LISTO, 100, 0, 0, res.ruta)
        except nucleo.Cancelado:
            self.estado.emit(fila, CANCELADA, 0, 0, 0, "")
        except Exception as e:
            self.estado.emit(fila, FALLO, 0, 0, 0, str(e) or type(e).__name__)
        finally:
            with self.candado:
                self.pendientes -= 1
                fin = self.pendientes == 0
            if fin:
                pool, self.pool = self.pool, None
                if pool:
                    pool.shutdown(wait=False)
                self.terminado.emit()


# ---------- Widgets ----------

class FilaCancion(QFrame):
    accion = Signal(int, str)  # fila, "reintentar" | "cancelar" | "reproducir"

    def __init__(self, fila: int, entrada: nucleo.Entrada, formato: str, imagenes: Imagenes):
        super().__init__()
        self.setObjectName("fila")
        self.fila = fila
        self.entrada = entrada
        self.estado = ESPERA
        self.ruta: str | None = None
        self.detalle = ""

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 14, 10)
        lay.setSpacing(ESPACIO)

        self.num = QLabel(f"{entrada.indice:02d}")
        self.num.setObjectName("num")
        self.num.setFixedWidth(C_NUM)
        self.num.setAlignment(Qt.AlignCenter)

        self.portada = QLabel()
        self.portada.setObjectName("portada")
        self.portada.setFixedSize(C_PORTADA, C_PORTADA)
        self.portada.setAlignment(Qt.AlignCenter)
        self.portada.setPixmap(icono(I_MUSICA, TENUE, 20).pixmap(20, 20))
        self._con_portada = False
        imagenes.pedir(entrada.miniatura, self.poner_portada)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.titulo = LabelRecortado(entrada.titulo)
        self.titulo.setObjectName("tituloCancion")
        self.artista = LabelRecortado(entrada.artista or "—")
        self.artista.setObjectName("artistaCancion")
        textos.addStretch()
        textos.addWidget(self.titulo)
        textos.addWidget(self.artista)
        textos.addStretch()

        self.formato = QLabel(formato)
        self.formato.setObjectName("formato")
        cont_formato = self._columna(self.formato, C_FORMATO, Qt.AlignLeft)

        self.tamano = QLabel("—")
        self.tamano.setObjectName("tamano")
        self.tamano.setFixedWidth(C_TAMANO)

        progreso = QWidget()
        progreso.setFixedWidth(C_PROGRESO)
        lp = QVBoxLayout(progreso)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.setSpacing(6)
        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setTextVisible(False)
        textos_prog = QHBoxLayout()
        self.prog_izq = QLabel("0%")
        self.prog_izq.setObjectName("progIzq")
        self.prog_der = LabelRecortado("Lista para descargar")
        self.prog_der.setObjectName("progDer")
        self.prog_der.setAlignment(Qt.AlignRight)
        textos_prog.addWidget(self.prog_izq)
        textos_prog.addWidget(self.prog_der, 1)
        lp.addStretch()
        lp.addWidget(self.barra)
        lp.addLayout(textos_prog)
        lp.addStretch()

        self.chip = QLabel()
        self.chip.setObjectName("chip")
        self.chip.setAlignment(Qt.AlignCenter)
        cont_chip = self._columna(self.chip, C_ESTADO, Qt.AlignRight)

        self.boton = QToolButton()
        self.boton.setObjectName("accion")
        self.boton.setCursor(Qt.PointingHandCursor)
        self.boton.setIconSize(QSize(16, 16))
        self.boton.clicked.connect(self._click)
        cont_boton = self._columna(self.boton, C_ACCION, Qt.AlignCenter)

        lay.addWidget(self.num)
        lay.addWidget(self.portada)
        lay.addLayout(textos, 1)
        lay.addWidget(cont_formato)
        lay.addWidget(self.tamano)
        lay.addWidget(progreso)
        lay.addWidget(cont_chip)
        lay.addWidget(cont_boton)
        self.setFixedHeight(72)
        self.actualizar(ESPERA, 0, 0, 0, "")

    @staticmethod
    def _columna(w: QWidget, ancho: int, alineacion) -> QWidget:
        cont = QWidget()
        cont.setFixedWidth(ancho)
        w.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        l = QHBoxLayout(cont)
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(w, 0, alineacion | Qt.AlignVCenter)
        return cont

    def poner_portada(self, pm: QPixmap):
        self.portada.setPixmap(redondear(pm, C_PORTADA, 6))
        self._con_portada = True

    def mouseDoubleClickEvent(self, _):
        if self.ruta:
            self.accion.emit(self.fila, "reproducir")

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        emitir = lambda tipo: (lambda: self.accion.emit(self.fila, tipo))
        if self.ruta:
            menu.addAction(icono(I_PLAY, CIAN, 14), "Reproducir", emitir("reproducir"))
            menu.addAction(icono(I_CARPETA, TEXTO, 14), "Mostrar en carpeta", emitir("carpeta"))
        if self.estado in (FALLO, CANCELADA):
            menu.addAction(icono(I_REINTENTAR, "#fca5a5", 14), "Reintentar", emitir("reintentar"))
        if self.estado == EXISTE:
            menu.addAction(icono(I_DESCARGA, TEXTO, 14), "Descargar de todos modos", emitir("forzar"))
        if self.estado in (ESPERA, COLA) or self.estado in ACTIVOS:
            menu.addAction(icono(I_CERRAR, TENUE, 14), "Detener" if self.estado in ACTIVOS else "Quitar de la cola",
                           emitir("cancelar"))
        menu.addSeparator()
        menu.addAction(icono(I_COPIAR, TEXTO, 14), "Copiar link", emitir("copiar"))
        if self.estado == FALLO:
            menu.addAction(icono(I_COPIAR, ROJO, 14), "Copiar error", emitir("copiar_error"))
        menu.exec(e.globalPos())

    def _click(self):
        tipo = self.boton.property("tipo")
        if tipo:
            self.accion.emit(self.fila, tipo)

    def _poner_boton(self, tipo: str | None, glifo: int | None = None, color: str = TEXTO, texto: str = "", tip: str = ""):
        self.boton.setVisible(tipo is not None)
        set_prop(self.boton, "tipo", tipo or "")
        self.boton.setIcon(icono(glifo, color, 14) if glifo else QIcon())
        self.boton.setText(texto)
        self.boton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if texto else Qt.ToolButtonIconOnly)
        self.boton.setToolTip(tip)

    def actualizar(self, estado: str, pct: int, vel: float, eta: float, detalle: str):
        self.estado = estado
        texto, tipo = CHIP[estado]
        self.chip.setText(texto)
        set_prop(self.chip, "tipo", tipo)
        self.barra.setValue(pct)

        error = estado == FALLO
        set_prop(self, "estado", "error" if error else "activo" if estado in ACTIVOS else "")
        set_prop(self.num, "activo", estado in ACTIVOS)
        set_prop(self.num, "error", error)
        for w in (self.barra, self.prog_izq, self.prog_der):
            set_prop(w, "error", error)

        if error:
            self.detalle = detalle
            self.barra.setValue(100)
            self.prog_izq.setText("Falló")
            self.prog_der.setText(detalle.split("\n")[0])
            self.setToolTip(detalle)
        else:
            self.setToolTip("")
        if estado == DESCARGANDO:
            vel_txt = f" · {fmt_bytes(vel)}/s" if vel else ""
            self.prog_izq.setText(f"{pct}%{vel_txt}")
            self.prog_der.setText(f"ETA {int(eta)}s" if eta else "")
        else:
            textos = {
                ESPERA: ("0%", "Lista para descargar"), COLA: ("0%", "Esperando hilo"),
                BUSCANDO: ("0%", "Buscando en YouTube Music"), CONVIRTIENDO: ("100%", "Convirtiendo audio"),
                LISTO: ("100%", "Completado"), YA: ("100%", "Ya estaba descargada"), CANCELADA: ("—", "Cancelada"),
                ETIQUETANDO: ("100%", "Completando datos con MusicBrainz"),
                EXISTE: ("—", "Ya está en tu biblioteca"),
            }
            if estado in textos:
                izq, der = textos[estado]
                self.prog_izq.setText(izq)
                self.prog_der.setText(der)
        if estado == EXISTE:
            self.setToolTip(f"Ya tienes esta canción en:\n{detalle}\n\nClic derecho → Descargar de todos modos")

        if estado in (LISTO, EXISTE):
            self.ruta = detalle or self.ruta
        if estado in (ESPERA, COLA) or estado in ACTIVOS:
            self._poner_boton("cancelar", I_CERRAR, ROJO if estado in ACTIVOS else TENUE,
                              tip="Detener" if estado in ACTIVOS else "Quitar de la cola")
        elif estado in (FALLO, CANCELADA):
            self._poner_boton("reintentar", I_REINTENTAR, "#fca5a5", "Reintentar")
        elif estado in (LISTO, EXISTE) and self.ruta:
            self._poner_boton("reproducir", I_PLAY, CIAN, tip="Escuchar")
        else:
            self._poner_boton(None)

    def poner_resultado(self, res: nucleo.Resultado):
        self.ruta = res.ruta
        self.tamano.setText(fmt_bytes(res.tamano))
        self.titulo.setText(res.titulo)
        self.titulo.update()
        if res.artista:
            self.artista.setText(res.artista)
            self.artista.update()
        # La portada guardada en el archivo es la de la canción (en Spotify la previa era la de la playlist)
        pm = portada_incrustada(res.ruta)
        if pm:
            self.poner_portada(pm)


def mezclar(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(
        int(ca.red() + (cb.red() - ca.red()) * t),
        int(ca.green() + (cb.green() - ca.green()) * t),
        int(ca.blue() + (cb.blue() - ca.blue()) * t),
    )


class Onda(QWidget):
    """Barra de avance con forma de onda (decorativa).

    Clic o arrastre para adelantar, rueda del mouse para saltar 5 s; al pasar el mouse muestra el tiempo.
    """

    buscar = Signal(float)
    saltar = Signal(int)

    def __init__(self, barras: int = 64):
        super().__init__()
        self.n = barras
        self.fraccion = 0.0
        self.alturas = [0.3] * barras
        self.hover: float | None = None
        self.duracion_ms = 0
        self.setMinimumHeight(34)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def semilla(self, texto: str):
        rnd = random.Random(texto)
        self.alturas = [
            max(0.18, min(1.0, 0.35 + 0.45 * abs(math.sin(i * 0.31 + rnd.random())) + rnd.uniform(-0.15, 0.25)))
            for i in range(self.n)
        ]
        self.update()

    def poner(self, fraccion: float):
        self.fraccion = fraccion
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        paso = self.width() / self.n
        ancho = max(2.0, paso * 0.55)
        for i, h in enumerate(self.alturas):
            centro = (i + 0.5) / self.n
            if centro <= self.fraccion:
                color = mezclar("#2dd4bf", CIAN, centro)
            elif self.hover is not None and centro <= self.hover:
                color = QColor("#3d5a6e")
            else:
                color = QColor(BORDE_FUERTE)
            alto = h * self.height()
            p.setBrush(color)
            p.drawRoundedRect(QRectF(i * paso + (paso - ancho) / 2, (self.height() - alto) / 2, ancho, alto),
                              ancho / 2, ancho / 2)
        if self.hover is not None:
            x = self.hover * self.width()
            p.setBrush(QColor(230, 237, 243, 170))
            p.drawRoundedRect(QRectF(x - 1, 0, 2, self.height()), 1, 1)

    def _fraccion(self, e) -> float:
        return min(max(e.position().x() / max(self.width(), 1), 0.0), 1.0)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.buscar.emit(self._fraccion(e))

    def mouseMoveEvent(self, e):
        self.hover = self._fraccion(e)
        self.update()
        if self.duracion_ms:
            QToolTip.showText(e.globalPosition().toPoint(), fmt_tiempo(int(self.hover * self.duracion_ms)), self)
        if e.buttons() & Qt.LeftButton:
            self.buscar.emit(self.hover)

    def leaveEvent(self, _):
        self.hover = None
        self.update()
        QToolTip.hideText()

    def wheelEvent(self, e):
        self.saltar.emit(5000 if e.angleDelta().y() > 0 else -5000)


class PortadaClic(QLabel):
    """Portada que al pasar el mouse muestra el icono de maximizar."""

    clicked = Signal()

    def __init__(self, lado: int, radio: int, glifo: int):
        super().__init__()
        self.setObjectName("portada")
        self.setFixedSize(lado, lado)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.radio = radio
        self.glifo = glifo
        self._hover = False

    def enterEvent(self, _):
        self._hover = True
        self.update()

    def leaveEvent(self, _):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self._hover:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        camino = QPainterPath()
        camino.addRoundedRect(QRectF(self.rect()), self.radio, self.radio)
        p.fillPath(camino, QColor(0, 0, 0, 150))
        lado = min(28, self.width() // 2)
        pm = icono(self.glifo, TEXTO, lado).pixmap(lado, lado)
        p.drawPixmap((self.width() - lado) // 2, (self.height() - lado) // 2, pm)


class PanelLetra(QWidget):
    """Letra de la canción. Si es sincronizada resalta la línea actual y se desplaza sola;
    clic en una línea para saltar a ese momento, rueda del mouse para leer a tu ritmo."""

    buscar = Signal(int)

    def __init__(self):
        super().__init__()
        self.textos: list[str] = []
        self.tiempos: list[int] = []
        self.sincronizada = False
        self.actual = -1
        self.hover = -1
        self.mensaje = "Reproduce una canción para ver su letra"
        self.desplazamiento = 0.0
        self._manual_hasta = 0.0
        self._cajas: list[tuple[float, float]] = []
        self.fuente = QFont()
        self.fuente.setPixelSize(22)
        self.fuente.setWeight(QFont.DemiBold)
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(420)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._mover)
        self.setMouseTracking(True)

    def poner(self, letra, mensaje: str = ""):
        self.anim.stop()
        self.mensaje = mensaje
        self.actual = self.hover = -1
        self.desplazamiento = 0.0
        self._manual_hasta = 0.0
        if letra and letra.lineas:
            self.textos = [t for _, t in letra.lineas]
            self.sincronizada = letra.tipo == "sincronizada"
            self.tiempos = [ms for ms, _ in letra.lineas] if self.sincronizada else []
        else:
            self.textos, self.tiempos, self.sincronizada = [], [], False
        self.setCursor(Qt.PointingHandCursor if self.sincronizada else Qt.ArrowCursor)
        self._acomodar()
        self.update()

    def _ancho(self) -> int:
        return max(self.width() - 24, 50)

    def _acomodar(self):
        fm = QFontMetrics(self.fuente)
        y = 0.0
        self._cajas = []
        for t in self.textos:
            alto = fm.boundingRect(0, 0, self._ancho(), 10000, Qt.TextWordWrap, t or "♪").height()
            self._cajas.append((y, alto))
            y += alto + 18

    def _margen(self) -> float:
        return self.height() * 0.38 if self.sincronizada else 24

    def _limite(self) -> float:
        if not self._cajas:
            return 0.0
        total = self._cajas[-1][0] + self._cajas[-1][1]
        return total if self.sincronizada else max(0.0, total - self.height() + 48)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._acomodar()
        if self.sincronizada and self.actual >= 0:
            self.desplazamiento = self._objetivo(self.actual)

    def _objetivo(self, i: int) -> float:
        y, alto = self._cajas[i]
        return min(max(y + alto / 2, 0.0), self._limite())

    def _mover(self, valor):
        self.desplazamiento = float(valor)
        self.update()

    def posicion(self, ms: int):
        if not self.sincronizada or not self.tiempos:
            return
        i = bisect.bisect_right(self.tiempos, ms + 150) - 1
        if i == self.actual:
            return
        self.actual = i
        if time.monotonic() >= self._manual_hasta:
            self.anim.stop()
            self.anim.setStartValue(self.desplazamiento)
            self.anim.setEndValue(self._objetivo(i) if i >= 0 else 0.0)
            self.anim.start()
        self.update()

    def _linea_en(self, y_pantalla: float) -> int:
        y = y_pantalla - self._margen() + self.desplazamiento
        for i, (arriba, alto) in enumerate(self._cajas):
            if arriba - 9 <= y <= arriba + alto + 9:
                return i
        return -1

    def paintEvent(self, _):
        dpr = self.devicePixelRatioF()
        capa = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        capa.setDevicePixelRatio(dpr)
        capa.fill(Qt.transparent)
        p = QPainter(capa)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(self.fuente)

        if not self.textos:
            p.setPen(QColor(TENUE))
            p.drawText(self.rect().adjusted(12, 0, -12, 0), Qt.AlignCenter | Qt.TextWordWrap, self.mensaje)
        margen = self._margen()
        for i, (y, alto) in enumerate(self._cajas):
            arriba = margen + y - self.desplazamiento
            if arriba > self.height() or arriba + alto < 0:
                continue
            if not self.sincronizada:
                color = QColor(TEXTO)
                color.setAlphaF(0.85)
            elif i == self.actual:
                color = QColor(TEXTO)
            elif i == self.hover:
                color = QColor(CIAN)
                color.setAlphaF(0.85)
            else:
                color = QColor(TENUE)
                color.setAlphaF(0.45 if i < self.actual else 0.75)
            p.setPen(color)
            p.drawText(QRectF(12, arriba, self._ancho(), alto), Qt.TextWordWrap, self.textos[i] or "♪")

        # Desvanecer arriba y abajo
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, QColor(0, 0, 0, 0))
        g.setColorAt(0.10, QColor(0, 0, 0, 255))
        g.setColorAt(0.86, QColor(0, 0, 0, 255))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), g)
        p.end()
        QPainter(self).drawPixmap(0, 0, capa)

    def wheelEvent(self, e):
        if not self._cajas:
            return
        self.anim.stop()
        self.desplazamiento = min(max(self.desplazamiento - e.angleDelta().y() * 0.6, 0.0), self._limite())
        self._manual_hasta = time.monotonic() + 3.5  # deja de seguir la canción un momento
        self.update()

    def mouseMoveEvent(self, e):
        i = self._linea_en(e.position().y()) if self.sincronizada else -1
        if i != self.hover:
            self.hover = i
            self.update()

    def leaveEvent(self, _):
        self.hover = -1
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.sincronizada:
            i = self._linea_en(e.position().y())
            if i >= 0:
                self._manual_hasta = 0.0
                self.buscar.emit(self.tiempos[i])


class CargadorLetra(QObject):
    """Busca la letra en otro hilo para no congelar la ventana."""

    lista = Signal(str, object)  # ruta, letras.Letra o Exception

    def pedir(self, ruta: Path, meta: dict):
        def trabajo():
            try:
                res = letras.obtener_letra(ruta, meta["titulo"], meta["artista"], meta["album"])
            except Exception as e:
                res = e
            self.lista.emit(str(ruta), res)

        threading.Thread(target=trabajo, daemon=True).start()


class VistaReproduccion(QWidget):
    """Fondo de la vista maximizada: la portada difuminada con un degradado encima."""

    def __init__(self):
        super().__init__()
        self.portada: QPixmap | None = None
        self._cache: tuple[QSize, QPixmap] | None = None

    def poner_portada(self, pm: QPixmap | None):
        # Reducir a 10x10 y volver a agrandar con suavizado da un desenfoque barato y bonito
        self.portada = pm.scaled(10, 10, Qt.IgnoreAspectRatio, Qt.SmoothTransformation) if pm else None
        self._cache = None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(FONDO))
        if self.portada:
            if not self._cache or self._cache[0] != self.size():
                self._cache = (self.size(), self.portada.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            p.setOpacity(0.55)
            p.drawPixmap(0, 0, self._cache[1])
            p.setOpacity(1.0)
        degradado = QLinearGradient(0, 0, 0, self.height())
        degradado.setColorAt(0.0, QColor(10, 15, 20, 120))
        degradado.setColorAt(0.55, QColor(10, 15, 20, 200))
        degradado.setColorAt(1.0, QColor(FONDO))
        p.fillRect(self.rect(), degradado)


def boton_icono(glifo: int, tip: str, color: str = TEXTO, px: int = 18, nombre: str = "control") -> QToolButton:
    b = QToolButton()
    b.setObjectName(nombre)
    b.setIcon(icono(glifo, color, px))
    b.setIconSize(QSize(px, px))
    b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


def etiqueta(texto: str, nombre: str = "etiqueta") -> QLabel:
    l = QLabel(texto)
    l.setObjectName(nombre)
    return l


# ---------- Biblioteca ----------

class SenalesFondo(QObject):
    """Señales para avisar a la ventana desde hilos (escaneo de carpetas y MusicBrainz)."""

    escaneo_progreso = Signal(int)
    escaneo_fin = Signal(int, int)  # nuevas, quitadas
    mb_progreso = Signal(int, int, str)  # i, total, título
    mb_fin = Signal(int, int)  # completadas, sin coincidencia
    recs_listas = Signal(list)  # [explorar.Seccion]
    recs_error = Signal(str)
    previa_lista = Signal(object, str)  # ResultadoCancion, ruta del audio
    previa_error = Signal(str)
    album_listo = Signal(str)  # link de la playlist del álbum
    album_error = Signal(str)


class TablaCanciones(QTableWidget):
    """Lista de canciones con columnas ordenables. Doble clic reproduce; clic derecho abre el menú."""

    reproducir = Signal(int)  # índice dentro de self.canciones
    menu = Signal(object, object)  # [Cancion] seleccionadas, posición global

    COLUMNAS = ["#", "TÍTULO", "ARTISTA", "ÁLBUM", "AÑO", "DURACIÓN"]

    def __init__(self, numerar_por_pista: bool = False):
        super().__init__(0, len(self.COLUMNAS))
        self.setObjectName("tabla")
        self.canciones: list[biblioteca.Cancion] = []
        self.numerar_por_pista = numerar_por_pista
        self.setHorizontalHeaderLabels(self.COLUMNAS)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(40)
        self.setShowGrid(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)
        self.setFocusPolicy(Qt.NoFocus)
        cab = self.horizontalHeader()
        cab.setHighlightSections(False)
        cab.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for col, modo in enumerate([QHeaderView.Fixed, QHeaderView.Stretch, QHeaderView.Stretch,
                                    QHeaderView.Stretch, QHeaderView.Fixed, QHeaderView.Fixed]):
            cab.setSectionResizeMode(col, modo)
        self.setColumnWidth(0, 48)
        self.setColumnWidth(4, 64)
        self.setColumnWidth(5, 90)
        cab.setSortIndicator(0, Qt.AscendingOrder)
        self.cellDoubleClicked.connect(lambda fila, _c: self.reproducir.emit(self._indice(fila)))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.seleccionadas() and self.menu.emit(self.seleccionadas(), self.viewport().mapToGlobal(pos)))
        self._sonando: Path | None = None

    def poner(self, canciones: list[biblioteca.Cancion]):
        self.setSortingEnabled(False)
        self.canciones = canciones
        self.setRowCount(len(canciones))
        for fila, c in enumerate(canciones):
            numero = c.pista if self.numerar_por_pista and c.pista else fila + 1
            valores = [numero, c.titulo, c.artista, c.album, c.anio, fmt_tiempo(int((c.duracion or 0) * 1000))]
            for col, v in enumerate(valores):
                it = QTableWidgetItem()
                if col == 0:
                    it.setData(Qt.DisplayRole, int(v))
                else:
                    it.setText(str(v or "—"))
                if col == 0:
                    it.setData(Qt.UserRole, fila)  # índice original aunque se reordene la tabla
                it.setToolTip(str(c.ruta) if col == 1 else "")
                self.setItem(fila, col, it)
        self.setSortingEnabled(True)
        cab = self.horizontalHeader()
        self.sortItems(cab.sortIndicatorSection(), cab.sortIndicatorOrder())
        self.marcar(self._sonando)

    def _indice(self, fila_visible: int) -> int:
        it = self.item(fila_visible, 0)
        return it.data(Qt.UserRole) if it else 0

    def orden_visible(self) -> list[biblioteca.Cancion]:
        """Las canciones en el orden en que se ven (respeta si el usuario ordenó por columna)."""
        return [self.canciones[self._indice(f)] for f in range(self.rowCount())]

    def seleccionadas(self) -> list[biblioteca.Cancion]:
        filas = sorted({i.row() for i in self.selectedIndexes()})
        return [self.canciones[self._indice(f)] for f in filas]

    def marcar(self, ruta: Path | None):
        self._sonando = ruta
        for f in range(self.rowCount()):
            c = self.canciones[self._indice(f)]
            sonando = ruta is not None and c.ruta == ruta
            for col in range(self.columnCount()):
                it = self.item(f, col)
                fuente = it.font()
                fuente.setBold(sonando)
                it.setFont(fuente)
                it.setForeground(QColor(CIAN) if sonando else QColor(TEXTO if col == 1 else TENUE))


class DialogoCarpetas(QDialog):
    """Elige qué carpetas de tu PC forman la biblioteca."""

    def __init__(self, db: biblioteca.Biblioteca, carpeta_descargas: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Carpetas de la biblioteca")
        self.setMinimumSize(640, 400)
        self.db = db
        self.descargas = Path(carpeta_descargas)
        self.cambio = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)
        lay.addWidget(etiqueta("CARPETAS DONDE BUSCAR MÚSICA"))
        texto = QLabel("WaveDrop lee las canciones de estas carpetas (y sus subcarpetas) para armar tu biblioteca "
                       "y avisarte si una canción que vas a descargar ya la tienes.")
        texto.setWordWrap(True)
        texto.setObjectName("artistaCancion")
        lay.addWidget(texto)
        self.lista = QListWidget()
        self.lista.setObjectName("lista")
        lay.addWidget(self.lista, 1)
        botones = QHBoxLayout()
        agregar = QPushButton("  Agregar carpeta…")
        agregar.setIcon(icono(I_CARPETA, CIAN, 14))
        agregar.clicked.connect(self._agregar)
        self.quitar = QPushButton("  Quitar")
        self.quitar.setIcon(icono(I_CERRAR, TENUE, 12))
        self.quitar.clicked.connect(self._quitar)
        cerrar = QPushButton("Listo")
        cerrar.setObjectName("analizar")
        cerrar.clicked.connect(self.accept)
        botones.addWidget(agregar)
        botones.addWidget(self.quitar)
        botones.addStretch()
        botones.addWidget(cerrar)
        lay.addLayout(botones)
        self.lista.currentRowChanged.connect(self._seleccion)
        self._llenar()

    def _llenar(self):
        self.lista.clear()
        for c in self.db.carpetas():
            es_descargas = c == self.descargas
            it = QListWidgetItem(icono(I_DESCARGA if es_descargas else I_CARPETA, CIAN if es_descargas else TENUE, 16),
                                 f"  {c}" + ("   (descargas)" if es_descargas else ""))
            it.setData(Qt.UserRole, str(c))
            self.lista.addItem(it)
        self._seleccion(self.lista.currentRow())

    def _seleccion(self, fila: int):
        it = self.lista.item(fila) if fila >= 0 else None
        self.quitar.setEnabled(bool(it) and Path(it.data(Qt.UserRole)) != self.descargas)

    def _agregar(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Agregar carpeta de música")
        if carpeta:
            self.db.agregar_carpeta(Path(carpeta))
            self.cambio = True
            self._llenar()

    def _quitar(self):
        it = self.lista.currentItem()
        if it:
            self.db.quitar_carpeta(Path(it.data(Qt.UserRole)))
            self.cambio = True
            self._llenar()


class PaginaBiblioteca(QWidget):
    """Canciones, álbumes, artistas y playlists de la base de datos local."""

    reproducir = Signal(list, int)  # [Path], índice
    reproducir_aleatorio = Signal(list)
    completar_mb = Signal(list)  # [Cancion]
    administrar_carpetas = Signal()
    escanear = Signal()
    previa = Signal(object)  # explorar.ResultadoCancion
    descargar = Signal(list)  # [explorar.ResultadoCancion]
    buscar_en_linea = Signal(str)
    actualizar_recomendaciones = Signal()

    INICIO = 4  # índice de la pestaña Inicio (va primero en la barra, pero se agregó al final)

    def __init__(self, db: biblioteca.Biblioteca, imagenes: "Imagenes"):
        super().__init__()
        self.db = db
        self.imagenes = imagenes
        self.sonando: Path | None = None
        self.album_abierto: biblioteca.Album | None = None
        self._portadas_pendientes: list[tuple[QListWidgetItem, Path]] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 12)
        lay.setSpacing(14)

        cab = QHBoxLayout()
        cab.addWidget(etiqueta("Biblioteca", "tituloSeccion"))
        cab.addSpacing(10)
        self.lbl_cuenta = etiqueta("", "stat")
        cab.addWidget(self.lbl_cuenta)
        cab.addStretch()
        for texto, glifo, senal, tip in [
            ("  Carpetas", I_CARPETA, self.administrar_carpetas, "Elegir qué carpetas de tu PC forman la biblioteca"),
            ("  Escanear", I_REINTENTAR, self.escanear, "Buscar canciones nuevas o cambiadas en tus carpetas"),
            ("  MusicBrainz", I_ETIQUETA, None, "Completar álbum, año, pista, género y portada "
                                                "de las canciones que todavía no tienen datos de MusicBrainz"),
        ]:
            b = QPushButton(texto)
            b.setObjectName("secundario")
            b.setIcon(icono(glifo, TEXTO, 14))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            if senal is not None:
                b.clicked.connect(senal.emit)
            else:
                b.clicked.connect(lambda: self.completar_mb.emit([c for c in self.db.canciones() if not c.mbid]))
                self.btn_mb = b
            cab.addWidget(b)
        lay.addLayout(cab)

        barra = QHBoxLayout()
        barra.setSpacing(8)
        self.pestanas = QButtonGroup(self)
        self._glifos = {self.INICIO: I_RAYO, 0: I_MUSICA, 1: I_DISCO, 2: I_PERSONA, 3: I_LISTA}
        for i, texto in [(self.INICIO, "INICIO"), (0, "CANCIONES"), (1, "ÁLBUMES"), (2, "ARTISTAS"), (3, "PLAYLISTS")]:
            glifo = self._glifos[i]
            b = QPushButton(f" {texto}")
            b.setObjectName("pestana")
            b.setIcon(icono(glifo, TENUE, 13))
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.pestanas.addButton(b, i)
            barra.addWidget(b)
        barra.addSpacing(10)
        self.lbl_estado = etiqueta("", "velocidad")
        self.lbl_estado.hide()
        barra.addWidget(self.lbl_estado)
        barra.addSpacing(6)
        self.buscar = QLineEdit()
        self.buscar.setObjectName("buscar")
        self.buscar.setPlaceholderText("Buscar por canción, artista o álbum…")
        self.buscar.textChanged.connect(self._buscar)
        barra.addWidget(self.buscar, 1)
        lay.addLayout(barra)

        self.vistas = QStackedWidget()
        self.vistas.addWidget(self._vista_canciones())
        self.vistas.addWidget(self._vista_albumes())
        self.vistas.addWidget(self._vista_artistas())
        self.vistas.addWidget(self._vista_playlists())
        self.vistas.addWidget(self._vista_inicio())
        lay.addWidget(self.vistas, 1)

        self.pestanas.idClicked.connect(self.ir_a)
        self.pestanas.button(self.INICIO).setChecked(True)
        self.vistas.setCurrentIndex(self.INICIO)
        self._timer_portadas = QTimer(self)
        self._timer_portadas.timeout.connect(self._cargar_portadas)

    # --- Vistas ---

    def _tabla(self, por_pista=False) -> TablaCanciones:
        t = TablaCanciones(por_pista)
        t.reproducir.connect(lambda i, t=t: self.reproducir.emit([c.ruta for c in t.orden_visible()],
                                                                 t.orden_visible().index(t.canciones[i])))
        t.menu.connect(lambda canciones, pos, t=t: self._menu(canciones, pos, t))
        return t

    def _vista_canciones(self) -> QWidget:
        self.tabla_todas = self._tabla()
        return self.tabla_todas

    def _vista_albumes(self) -> QWidget:
        self.albumes = QStackedWidget()
        self.rejilla = QListWidget()
        self.rejilla.setObjectName("rejilla")
        self.rejilla.setViewMode(QListView.IconMode)
        self.rejilla.setResizeMode(QListView.Adjust)
        self.rejilla.setMovement(QListView.Static)
        self.rejilla.setIconSize(QSize(170, 170))
        self.rejilla.setGridSize(QSize(200, 250))
        self.rejilla.setSpacing(6)
        self.rejilla.setWordWrap(True)
        self.rejilla.setUniformItemSizes(True)
        self.rejilla.setCursor(Qt.PointingHandCursor)
        self.rejilla.itemClicked.connect(lambda it: self.abrir_album(it.data(Qt.UserRole)))
        self.albumes.addWidget(self.rejilla)

        detalle = QWidget()
        ld = QVBoxLayout(detalle)
        ld.setContentsMargins(0, 0, 0, 0)
        ld.setSpacing(16)
        cab = QHBoxLayout()
        cab.setSpacing(22)
        self.det_portada = QLabel()
        self.det_portada.setObjectName("vpPortada")
        self.det_portada.setFixedSize(180, 180)
        self.det_portada.setAlignment(Qt.AlignCenter)
        cab.addWidget(self.det_portada)
        info = QVBoxLayout()
        info.addStretch()
        info.addWidget(etiqueta("ÁLBUM", "vpSobre"))
        self.det_titulo = QLabel()
        self.det_titulo.setObjectName("vpTitulo")
        self.det_titulo.setWordWrap(True)
        self.det_info = etiqueta("", "vpAlbum")
        info.addWidget(self.det_titulo)
        info.addWidget(self.det_info)
        info.addSpacing(8)
        botones = QHBoxLayout()
        botones.setSpacing(10)
        volver = QPushButton("  Álbumes")
        volver.setObjectName("secundario")
        volver.setIcon(icono(I_ATRAS, TEXTO, 14))
        volver.clicked.connect(lambda: self.albumes.setCurrentIndex(0))
        play = QPushButton("  Reproducir")
        play.setObjectName("analizar")
        play.setIcon(icono(I_PLAY, CIAN, 14))
        play.clicked.connect(lambda: self._reproducir_tabla(self.tabla_album))
        mezcla = QPushButton("  Aleatorio")
        mezcla.setObjectName("secundario")
        mezcla.setIcon(icono(I_ALEATORIO, TEXTO, 14))
        mezcla.clicked.connect(lambda: self.reproducir_aleatorio.emit([c.ruta for c in self.tabla_album.canciones]))
        for b in (volver, play, mezcla):
            b.setCursor(Qt.PointingHandCursor)
            botones.addWidget(b)
        botones.addStretch()
        info.addLayout(botones)
        info.addStretch()
        cab.addLayout(info, 1)
        ld.addLayout(cab)
        self.tabla_album = self._tabla(por_pista=True)
        ld.addWidget(self.tabla_album, 1)
        self.albumes.addWidget(detalle)
        return self.albumes

    def _vista_artistas(self) -> QWidget:
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(16)
        self.lista_artistas = QListWidget()
        self.lista_artistas.setObjectName("cola")
        self.lista_artistas.setFixedWidth(280)
        self.lista_artistas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista_artistas.setTextElideMode(Qt.ElideRight)
        self.lista_artistas.currentItemChanged.connect(
            lambda it, _p: it and self.tabla_artista.poner(self.db.canciones_de_artista(it.data(Qt.UserRole))))
        l.addWidget(self.lista_artistas)
        self.tabla_artista = self._tabla()
        l.addWidget(self.tabla_artista, 1)
        return w

    def _vista_playlists(self) -> QWidget:
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(16)
        izq = QVBoxLayout()
        izq.setSpacing(8)
        nueva = QPushButton("  Nueva playlist")
        nueva.setObjectName("analizar")
        nueva.setIcon(icono(I_AGREGAR, CIAN, 14))
        nueva.setCursor(Qt.PointingHandCursor)
        nueva.clicked.connect(lambda: self.nueva_playlist())
        izq.addWidget(nueva)
        self.lista_playlists = QListWidget()
        self.lista_playlists.setObjectName("cola")
        self.lista_playlists.setFixedWidth(280)
        self.lista_playlists.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lista_playlists.setTextElideMode(Qt.ElideRight)
        self.lista_playlists.currentItemChanged.connect(lambda it, _p: self._abrir_playlist())
        izq.addWidget(self.lista_playlists, 1)
        l.addLayout(izq)

        der = QVBoxLayout()
        der.setSpacing(12)
        cab = QHBoxLayout()
        cab.setSpacing(10)
        self.pl_titulo = etiqueta("Elige o crea una playlist", "tituloSeccion")
        cab.addWidget(self.pl_titulo)
        cab.addStretch()
        self.pl_botones = []
        for texto, glifo, accion in [("  Reproducir", I_PLAY, lambda: self._reproducir_tabla(self.tabla_playlist)),
                                     ("  Aleatorio", I_ALEATORIO, lambda: self.reproducir_aleatorio.emit(
                                         [c.ruta for c in self.tabla_playlist.canciones])),
                                     ("  Renombrar", I_EDITAR, self._renombrar_playlist),
                                     ("  Eliminar", I_BORRAR, self._borrar_playlist)]:
            b = QPushButton(texto)
            b.setObjectName("analizar" if glifo == I_PLAY else "secundario")
            b.setIcon(icono(glifo, CIAN if glifo == I_PLAY else TEXTO, 14))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(accion)
            self.pl_botones.append(b)
            cab.addWidget(b)
        der.addLayout(cab)
        self.tabla_playlist = self._tabla()
        der.addWidget(self.tabla_playlist, 1)
        ayuda = etiqueta("Para agregar canciones: clic derecho sobre cualquier canción → Agregar a playlist.",
                         "fuenteLetra")
        der.addWidget(ayuda)
        l.addLayout(der, 1)
        return w

    # --- Navegación y datos ---

    def ir_a(self, i: int):
        self.pestanas.button(i).setChecked(True)
        for j, glifo in self._glifos.items():
            self.pestanas.button(j).setIcon(icono(glifo, CIAN if j == i else TENUE, 13))
        self.vistas.setCurrentIndex(i)
        self.refrescar()

    def refrescar(self):
        total = self.db.total()
        n_alb = len(self.db.albumes())
        self.lbl_cuenta.setText(f"{total} canciones · {n_alb} álbumes · {len(self.db.playlists())} playlists")
        i = self.vistas.currentIndex()
        if i == 0:
            self.tabla_todas.poner(self.db.canciones(self.buscar.text().strip()))
        elif i == 1:
            if self.albumes.currentIndex() == 1 and self.album_abierto:
                self.abrir_album(self.album_abierto)
            self._llenar_albumes()
        elif i == 2:
            self._llenar_artistas()
        elif i == 3:
            self._llenar_playlists()
        else:
            self._llenar_inicio_local()

    # --- Inicio: recomendaciones y lo que más escuchas ---

    def _vista_inicio(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.viewport().setObjectName("fondoLista")
        cont = QWidget()
        cont.setObjectName("fondoLista")
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(6)
        cab = QHBoxLayout()
        cab.addWidget(etiqueta("Basado en lo que escuchas y descargas · recomendaciones de YouTube Music", "stat"))
        cab.addStretch()
        self.btn_recs = QPushButton("  Actualizar recomendaciones")
        self.btn_recs.setObjectName("secundario")
        self.btn_recs.setIcon(icono(I_REINTENTAR, TEXTO, 14))
        self.btn_recs.setCursor(Qt.PointingHandCursor)
        self.btn_recs.clicked.connect(self.actualizar_recomendaciones.emit)
        cab.addWidget(self.btn_recs)
        lay.addLayout(cab)
        self.cont_recs = QVBoxLayout()
        self.cont_recs.setSpacing(6)
        lay.addLayout(self.cont_recs)
        self.cont_local = QVBoxLayout()
        self.cont_local.setSpacing(6)
        lay.addLayout(self.cont_local)
        lay.addStretch()
        scroll.setWidget(cont)
        self.poner_recomendaciones(None, "Cargando recomendaciones…")
        return scroll

    @staticmethod
    def _vaciar(layout: QVBoxLayout):
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _titulo_seccion(self, layout: QVBoxLayout, texto: str):
        l = etiqueta(texto, "seccionInicio")
        layout.addWidget(l)

    def poner_recomendaciones(self, secciones: list | None, mensaje: str = ""):
        self._vaciar(self.cont_recs)
        if mensaje:
            aviso = etiqueta(mensaje, "vacio")
            aviso.setMinimumHeight(90)
            aviso.setAlignment(Qt.AlignCenter)
            self.cont_recs.addWidget(aviso)
        for s in secciones or []:
            tira = TiraTarjetas(redondas=bool(s.artistas))
            for c in s.canciones:
                it = tira.agregar(f"{c.titulo}\n{c.artista}", ("online", c))
                self.imagenes.pedir(c.miniatura, lambda pm, it=it, t=tira: it.setIcon(QIcon(t.preparar(pm))))
            for a in s.artistas:
                it = tira.agregar(a["nombre"], ("artista", a))
                self.imagenes.pedir(a.get("miniatura"), lambda pm, it=it, t=tira: it.setIcon(QIcon(t.preparar(pm))))
            tira.activada.connect(self._tarjeta)
            self._titulo_seccion(self.cont_recs, s.titulo)
            self.cont_recs.addWidget(tira)

    def _llenar_inicio_local(self):
        self._vaciar(self.cont_local)
        for titulo, canciones in [("Lo que más escuchas", [c for c, _n in self.db.mas_escuchadas()]),
                                  ("Escuchado recientemente", self.db.recientes())]:
            if not canciones:
                continue
            tira = TiraTarjetas()
            for c in canciones:
                tira.agregar(f"{c.titulo}\n{c.artista}", ("local", c, canciones), portada_incrustada(str(c.ruta)))
            tira.activada.connect(self._tarjeta)
            self._titulo_seccion(self.cont_local, titulo)
            self.cont_local.addWidget(tira)

    def _tarjeta(self, dato, pos):
        tipo = dato[0]
        if tipo == "local":
            _t, c, lista = dato
            self.reproducir.emit([x.ruta for x in lista], lista.index(c))
        elif tipo == "artista":
            self.buscar_en_linea.emit(dato[1]["nombre"])
        else:
            c = dato[1]
            menu = QMenu(self)
            menu.addAction(icono(I_PLAY, CIAN, 14), "Escuchar vista previa", lambda: self.previa.emit(c))
            menu.addAction(icono(I_DESCARGA, TEXTO, 14), "Descargar", lambda: self.descargar.emit([c]))
            menu.addSeparator()
            principal = biblioteca.artista_principal(c.artista)
            menu.addAction(icono(I_BUSCAR, TEXTO, 14), f"Buscar más de {principal}",
                           lambda: self.buscar_en_linea.emit(principal))
            menu.exec(pos)

    def _buscar(self, _texto):
        if self.vistas.currentIndex() != 0:
            self.ir_a(0)
        else:
            self.tabla_todas.poner(self.db.canciones(self.buscar.text().strip()))

    def _llenar_albumes(self):
        self._timer_portadas.stop()
        self.rejilla.clear()
        self._portadas_pendientes = []
        vacia = icono(I_DISCO, TENUE, 64).pixmap(64, 64)
        for a in self.db.albumes():
            it = QListWidgetItem(QIcon(self._marco(vacia)), f"{a.nombre}\n{a.artista}" + (f" · {a.anio}" if a.anio else ""))
            it.setData(Qt.UserRole, a)
            it.setToolTip(f"{a.nombre} — {a.artista}\n{a.canciones} canciones")
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.rejilla.addItem(it)
            self._portadas_pendientes.append((it, a.ruta_portada))
        self._timer_portadas.start(15)

    @staticmethod
    def _marco(pm: QPixmap) -> QPixmap:
        """Centra un icono chico en un cuadro del tamaño de la portada."""
        lienzo = QPixmap(340, 340)
        lienzo.fill(QColor(TARJETA))
        p = QPainter(lienzo)
        p.drawPixmap((340 - pm.width()) // 2, (340 - pm.height()) // 2, pm)
        p.end()
        return redondear(lienzo, 170, 10)

    def _cargar_portadas(self):
        # De a poco para no congelar la ventana con bibliotecas grandes
        for _ in range(6):
            if not self._portadas_pendientes:
                self._timer_portadas.stop()
                return
            it, ruta = self._portadas_pendientes.pop(0)
            pm = portada_incrustada(str(ruta))
            if pm:
                try:
                    it.setIcon(QIcon(redondear(pm, 170, 10)))
                except RuntimeError:
                    pass

    def abrir_album(self, album: biblioteca.Album):
        self.album_abierto = album
        canciones = self.db.canciones_de_album(album)
        self.tabla_album.poner(canciones)
        self.det_titulo.setText(album.nombre)
        duracion = sum(c.duracion or 0 for c in canciones)
        partes = [album.artista, album.anio, f"{len(canciones)} canciones", f"{int(duracion // 60)} min"]
        self.det_info.setText("  ·  ".join(p for p in partes if p))
        pm = portada_incrustada(str(album.ruta_portada))
        self.det_portada.setPixmap(redondear(pm, 180, 12) if pm else icono(I_DISCO, TENUE, 64).pixmap(64, 64))
        self.albumes.setCurrentIndex(1)

    def _llenar_artistas(self):
        actual = self.lista_artistas.currentItem().data(Qt.UserRole) if self.lista_artistas.currentItem() else None
        self.lista_artistas.blockSignals(True)
        self.lista_artistas.clear()
        for nombre, n in self.db.artistas():
            it = QListWidgetItem(icono(I_PERSONA, TENUE, 16), f"  {nombre}   ·   {n}")
            it.setData(Qt.UserRole, nombre)
            self.lista_artistas.addItem(it)
            if nombre == actual:
                self.lista_artistas.setCurrentItem(it)
        self.lista_artistas.blockSignals(False)
        if not self.lista_artistas.currentItem() and self.lista_artistas.count():
            self.lista_artistas.setCurrentRow(0)
        elif self.lista_artistas.currentItem():
            self.tabla_artista.poner(self.db.canciones_de_artista(self.lista_artistas.currentItem().data(Qt.UserRole)))

    def _llenar_playlists(self, seleccionar: int | None = None):
        actual = seleccionar or self._playlist_actual()
        self.lista_playlists.blockSignals(True)
        self.lista_playlists.clear()
        for pid, nombre, n in self.db.playlists():
            it = QListWidgetItem(icono(I_LISTA, TENUE, 16), f"  {nombre}   ·   {n}")
            it.setData(Qt.UserRole, pid)
            self.lista_playlists.addItem(it)
            if pid == actual:
                self.lista_playlists.setCurrentItem(it)
        self.lista_playlists.blockSignals(False)
        if not self.lista_playlists.currentItem() and self.lista_playlists.count():
            self.lista_playlists.setCurrentRow(0)
        self._abrir_playlist()

    def _playlist_actual(self) -> int | None:
        it = self.lista_playlists.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _abrir_playlist(self):
        pid = self._playlist_actual()
        for b in self.pl_botones:
            b.setEnabled(pid is not None)
        if pid is None:
            self.pl_titulo.setText("Elige o crea una playlist")
            self.tabla_playlist.poner([])
            return
        nombre = next((n for i, n, _ in self.db.playlists() if i == pid), "")
        self.pl_titulo.setText(nombre)
        self.tabla_playlist.poner(self.db.canciones_de_playlist(pid))

    def nueva_playlist(self, canciones: list[biblioteca.Cancion] | None = None) -> int | None:
        nombre, ok = QInputDialog.getText(self, "Nueva playlist", "Nombre de la playlist:")
        if not ok or not nombre.strip():
            return None
        try:
            pid = self.db.crear_playlist(nombre)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, NOMBRE_APP, f"Ya existe una playlist llamada “{nombre.strip()}”.")
            return None
        if canciones:
            self.db.agregar_a_playlist(pid, [c.id for c in canciones])
        if self.vistas.currentIndex() == 3:
            self._llenar_playlists(pid)
        self.refrescar()
        return pid

    def _renombrar_playlist(self):
        pid = self._playlist_actual()
        if pid is None:
            return
        nombre, ok = QInputDialog.getText(self, "Renombrar playlist", "Nuevo nombre:", text=self.pl_titulo.text())
        if ok and nombre.strip():
            try:
                self.db.renombrar_playlist(pid, nombre)
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, NOMBRE_APP, "Ya existe una playlist con ese nombre.")
            self._llenar_playlists(pid)

    def _borrar_playlist(self):
        pid = self._playlist_actual()
        if pid is None:
            return
        r = QMessageBox.question(self, NOMBRE_APP, f"¿Eliminar la playlist “{self.pl_titulo.text()}”?\n"
                                                   "Las canciones no se borran de tu PC.")
        if r == QMessageBox.Yes:
            self.db.borrar_playlist(pid)
            self._llenar_playlists()
            self.refrescar()

    def _reproducir_tabla(self, tabla: TablaCanciones):
        canciones = tabla.orden_visible()
        if canciones:
            self.reproducir.emit([c.ruta for c in canciones], 0)

    def _menu(self, canciones: list[biblioteca.Cancion], pos, tabla: TablaCanciones):
        menu = QMenu(self)
        una = canciones[0]
        orden = tabla.orden_visible()
        menu.addAction(icono(I_PLAY, CIAN, 14), "Reproducir",
                       lambda: self.reproducir.emit([c.ruta for c in orden], orden.index(una)))
        sub = menu.addMenu(icono(I_LISTA, TEXTO, 14), "Agregar a playlist")
        sub.addAction(icono(I_AGREGAR, CIAN, 14), "Nueva playlist…", lambda: self.nueva_playlist(canciones))
        listas = self.db.playlists()
        if listas:
            sub.addSeparator()
        for pid, nombre, _n in listas:
            sub.addAction(nombre, lambda pid=pid: (self.db.agregar_a_playlist(pid, [c.id for c in canciones]),
                                                   self.refrescar()))
        if tabla is self.tabla_playlist and self._playlist_actual() is not None:
            pid = self._playlist_actual()
            menu.addAction(icono(I_CERRAR, TENUE, 12), "Quitar de la playlist",
                           lambda: (self.db.quitar_de_playlist(pid, [c.id for c in canciones]), self.refrescar()))
            if len(canciones) == 1:
                menu.addAction(icono(I_ARRIBA, TEXTO, 12), "Subir",
                               lambda: (self.db.mover_en_playlist(pid, una.id, -1), self._abrir_playlist()))
                menu.addAction(icono(I_ABAJO, TEXTO, 12), "Bajar",
                               lambda: (self.db.mover_en_playlist(pid, una.id, 1), self._abrir_playlist()))
        menu.addSeparator()
        menu.addAction(icono(I_ETIQUETA, TEXTO, 14), "Completar con MusicBrainz",
                       lambda: self.completar_mb.emit(canciones))
        menu.addAction(icono(I_CARPETA, TEXTO, 14), "Mostrar en carpeta", lambda: abrir_en_explorador(una.ruta))
        menu.exec(pos)

    def marcar(self, ruta: Path | None):
        self.sonando = ruta
        for t in (self.tabla_todas, self.tabla_album, self.tabla_artista, self.tabla_playlist):
            t.marcar(ruta)

    def estado(self, texto: str):
        self.lbl_estado.setText(texto)
        self.lbl_estado.setVisible(bool(texto))

    def orden_actual(self) -> list[Path]:
        return [c.ruta for c in self.tabla_todas.orden_visible()] or [c.ruta for c in self.db.canciones()]


# ---------- Explorar: búsqueda en línea y recomendaciones ----------

class TiraTarjetas(QListWidget):
    """Fila horizontal de tarjetas con portada (canciones, álbumes o artistas)."""

    activada = Signal(object, object)  # dato de la tarjeta, posición global del clic

    def __init__(self, redondas: bool = False):
        super().__init__()
        self.setObjectName("tira")
        self.redondas = redondas
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListView.Static)
        self.setIconSize(QSize(150, 150))
        self.setGridSize(QSize(176, 222))
        self.setFixedHeight(242)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideRight)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setCursor(Qt.PointingHandCursor)
        self.itemClicked.connect(lambda it: self.activada.emit(it.data(Qt.UserRole), QCursor.pos()))

    def wheelEvent(self, e):
        # La rueda del mouse desplaza la tira hacia los lados
        barra = self.horizontalScrollBar()
        barra.setValue(barra.value() - e.angleDelta().y())

    def agregar(self, texto: str, dato, pm: QPixmap | None = None) -> QListWidgetItem:
        it = QListWidgetItem(QIcon(self.preparar(pm)), texto)
        it.setData(Qt.UserRole, dato)
        it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
        it.setToolTip(texto.replace("\n", " — "))
        self.addItem(it)
        return it

    def preparar(self, pm: QPixmap | None) -> QPixmap:
        lado = 150
        if pm is None or pm.isNull():
            lienzo = QPixmap(lado * 2, lado * 2)
            lienzo.fill(QColor(TARJETA))
            p = QPainter(lienzo)
            glifo = icono(I_PERSONA if self.redondas else I_MUSICA, TENUE, 56).pixmap(56, 56)
            p.drawPixmap(lado - 28, lado - 28, glifo)
            p.end()
            pm = lienzo
        return redondear(pm, lado, lado // 2 if self.redondas else 10)


class FilaResultado(QFrame):
    """Un resultado de la búsqueda: canción (vista previa y descargar) o álbum (descargar completo)."""

    previa = Signal(object)
    descargar = Signal(object)

    def __init__(self, dato, imagenes: "Imagenes", existente: biblioteca.Cancion | None = None):
        super().__init__()
        self.setObjectName("fila")
        self.dato = dato
        es_album = isinstance(dato, explorar.ResultadoAlbum)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(14)

        self.portada = QLabel()
        self.portada.setObjectName("portada")
        self.portada.setFixedSize(52, 52)
        self.portada.setAlignment(Qt.AlignCenter)
        self.portada.setPixmap(icono(I_DISCO if es_album else I_MUSICA, TENUE, 20).pixmap(20, 20))
        imagenes.pedir(dato.miniatura, lambda pm: self.portada.setPixmap(redondear(pm, 52, 6)))
        lay.addWidget(self.portada)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = LabelRecortado(dato.titulo)
        titulo.setObjectName("tituloCancion")
        if es_album:
            sub = " · ".join(p for p in (dato.tipo, dato.artista, dato.anio) if p)
        else:
            sub = " · ".join(p for p in (dato.artista, dato.album) if p)
        subtitulo = LabelRecortado(sub)
        subtitulo.setObjectName("artistaCancion")
        textos.addStretch()
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        textos.addStretch()
        lay.addLayout(textos, 1)

        if existente:
            chip = etiqueta("Ya la tienes", "chip")
            set_prop(chip, "tipo", "info")
            chip.setToolTip(str(existente.ruta))
            lay.addWidget(chip)
        if not es_album:
            duracion = etiqueta(fmt_tiempo(int((dato.duracion or 0) * 1000)), "tamano")
            duracion.setFixedWidth(52)
            lay.addWidget(duracion)
            self.btn_previa = QPushButton("  Escuchar")
            self.btn_previa.setObjectName("secundario")
            self.btn_previa.setIcon(icono(I_PLAY, CIAN, 13))
            self.btn_previa.setToolTip("Vista previa: se escucha sin agregarla a tu biblioteca")
            self.btn_previa.setCursor(Qt.PointingHandCursor)
            self.btn_previa.clicked.connect(lambda: self.previa.emit(self.dato))
            lay.addWidget(self.btn_previa)
        self.btn_descargar = QPushButton("  Descargar álbum" if es_album else "  Descargar")
        self.btn_descargar.setObjectName("analizar")
        self.btn_descargar.setIcon(icono(I_DESCARGA, CIAN, 14))
        self.btn_descargar.setCursor(Qt.PointingHandCursor)
        self.btn_descargar.clicked.connect(lambda: self.descargar.emit(self.dato))
        lay.addWidget(self.btn_descargar)
        self.setFixedHeight(70)

    def en_cola(self):
        self.btn_descargar.setText("  En la cola")
        self.btn_descargar.setEnabled(False)


class PaginaBuscar(QWidget):
    """Busca canciones y álbumes en YouTube Music."""

    previa = Signal(object)  # explorar.ResultadoCancion
    descargar = Signal(list)  # [explorar.ResultadoCancion]
    descargar_album = Signal(object)  # explorar.ResultadoAlbum
    _listo = Signal(str, str, list)  # consulta, tipo, resultados
    _error = Signal(str)

    def __init__(self, db: biblioteca.Biblioteca, imagenes: "Imagenes"):
        super().__init__()
        self.db = db
        self.imagenes = imagenes
        self.filas: list[FilaResultado] = []
        self._buscando = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 12)
        lay.setSpacing(14)

        cab = QHBoxLayout()
        cab.addWidget(etiqueta("Buscar música", "tituloSeccion"))
        cab.addSpacing(10)
        cab.addWidget(etiqueta("en YouTube Music", "stat"))
        cab.addStretch()
        self.lbl_estado = etiqueta("", "velocidad")
        self.lbl_estado.hide()
        cab.addWidget(self.lbl_estado)
        lay.addLayout(cab)

        barra = QHBoxLayout()
        barra.setSpacing(10)
        caja = QFrame()
        caja.setObjectName("cajaUrl")
        lc = QHBoxLayout(caja)
        lc.setContentsMargins(14, 2, 8, 2)
        lupa = QLabel()
        lupa.setPixmap(icono(I_BUSCAR, TENUE, 16).pixmap(16, 16))
        self.entrada = QLineEdit()
        self.entrada.setObjectName("url")
        self.entrada.setPlaceholderText("Canción, artista o álbum…")
        self.entrada.returnPressed.connect(self.buscar)
        lc.addWidget(lupa)
        lc.addWidget(self.entrada, 1)
        barra.addWidget(caja, 1)
        self.tipos = QButtonGroup(self)
        for i, (glifo, texto) in enumerate([(I_MUSICA, "CANCIONES"), (I_DISCO, "ÁLBUMES")]):
            b = QPushButton(f" {texto}")
            b.setObjectName("pestana")
            b.setIcon(icono(glifo, TENUE, 13))
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.tipos.addButton(b, i)
            barra.addWidget(b)
        self.tipos.button(0).setChecked(True)
        self.tipos.idClicked.connect(lambda _i: self.entrada.text().strip() and self.buscar())
        boton = QPushButton("  Buscar")
        boton.setObjectName("analizar")
        boton.setIcon(icono(I_BUSCAR, CIAN, 16))
        boton.setCursor(Qt.PointingHandCursor)
        boton.clicked.connect(self.buscar)
        barra.addWidget(boton)
        lay.addLayout(barra)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.viewport().setObjectName("fondoLista")
        cont = QWidget()
        cont.setObjectName("fondoLista")
        self.lista = QVBoxLayout(cont)
        self.lista.setContentsMargins(0, 0, 4, 0)
        self.lista.setSpacing(8)
        self.vacio = etiqueta("Escribe el nombre de una canción, un artista o un álbum y presiona Enter.\n\n"
                              "Puedes escuchar una vista previa antes de descargar.", "vacio")
        self.vacio.setAlignment(Qt.AlignCenter)
        self.vacio.setMinimumHeight(200)
        self.lista.addWidget(self.vacio)
        self.lista.addStretch()
        self.scroll.setWidget(cont)
        lay.addWidget(self.scroll, 1)

        self._listo.connect(self._mostrar)
        self._error.connect(self._fallo)

    def estado(self, texto: str):
        self.lbl_estado.setText(texto)
        self.lbl_estado.setVisible(bool(texto))

    def buscar(self, consulta: str | None = None):
        if consulta:
            self.entrada.setText(consulta)
        consulta = self.entrada.text().strip()
        if not consulta:
            self.entrada.setFocus()
            return
        tipo = "albumes" if self.tipos.checkedId() == 1 else "canciones"
        self._buscando = f"{tipo}:{consulta}"
        self.estado("Buscando…")

        def trabajo():
            try:
                res = explorar.buscar_albumes(consulta) if tipo == "albumes" else explorar.buscar_canciones(consulta)
                self._listo.emit(consulta, tipo, res)
            except Exception as e:
                self._error.emit(str(e))

        threading.Thread(target=trabajo, daemon=True).start()

    def _fallo(self, msg: str):
        self.estado("")
        QMessageBox.warning(self, NOMBRE_APP, f"No se pudo buscar en YouTube Music:\n\n{msg}")

    def _mostrar(self, consulta: str, tipo: str, resultados: list):
        if f"{tipo}:{consulta}" != self._buscando:
            return  # llegó una búsqueda vieja
        for f in self.filas:
            f.deleteLater()
        self.filas = []
        for r in resultados:
            existente = None if tipo == "albumes" else self.db.buscar_existente(r.artista, r.titulo, r.duracion)
            fila = FilaResultado(r, self.imagenes, existente)
            fila.previa.connect(self.previa.emit)
            fila.descargar.connect(lambda dato, fila=fila: self._descargar(dato, fila))
            self.filas.append(fila)
            self.lista.insertWidget(self.lista.count() - 1, fila)
        self.vacio.setText("Sin resultados." if not resultados else "")
        self.vacio.setVisible(not resultados)
        self.scroll.verticalScrollBar().setValue(0)
        self.estado(f"{len(resultados)} resultados")

    def _descargar(self, dato, fila: FilaResultado):
        if isinstance(dato, explorar.ResultadoAlbum):
            self.descargar_album.emit(dato)
        else:
            self.descargar.emit([dato])
            fila.en_cola()


# ---------- Ventana ----------

class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(NOMBRE_APP)
        self.setMinimumSize(1180, 720)
        pantalla = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1560, pantalla.width() - 40), min(960, pantalla.height() - 40))
        self.ajustes = QSettings("DescargadorPlaylists", "DescargadorPlaylists")
        self.imagenes = Imagenes(self)
        self.gestor = Gestor()
        self.gestor.estado.connect(self._estado_fila)
        self.gestor.resultado.connect(self._resultado_fila)
        self.gestor.terminado.connect(self._terminado)
        self.analizador: Analizador | None = None
        self.coleccion: nucleo.Coleccion | None = None
        self.filas: dict[int, FilaCancion] = {}
        self.velocidades: dict[int, float] = {}
        self.sig_fila = 0
        self.iniciar_al_analizar = False
        self.biblioteca: list[Path] = []
        self.indice_actual = -1
        self.repetir = 0  # 0 no, 1 toda la lista, 2 una canción
        self.db = biblioteca.Biblioteca()
        self.fondo = SenalesFondo()
        self.fondo.escaneo_progreso.connect(lambda n: self.pagina_bib.estado(f"Escaneando… {n} archivos"))
        self.fondo.escaneo_fin.connect(self._escaneo_fin)
        self.fondo.mb_progreso.connect(lambda i, n, t: self.pagina_bib.estado(f"MusicBrainz {i}/{n}: {t[:40]}"))
        self.fondo.mb_fin.connect(self._mb_fin)
        self.fondo.recs_listas.connect(self._recomendaciones_listas)
        self.fondo.recs_error.connect(self._recomendaciones_error)
        self.fondo.previa_lista.connect(self._reproducir_previa)
        self.fondo.previa_error.connect(self._previa_error)
        self.fondo.album_listo.connect(self._album_listo)
        self.fondo.album_error.connect(lambda m: QMessageBox.warning(self, NOMBRE_APP, f"No se pudo abrir el álbum:\n\n{m}"))
        self._escaneando = self._mb_activo = self._cerrando = False
        self._recs_cargando = self._previa_cargando = self._en_previa = self._contada = False
        self._recs_iniciales = False
        self._mb_al_descargar = True
        self.gestor.postproceso = self._postproceso_descarga
        self._timer_biblioteca = QTimer(self)
        self._timer_biblioteca.setSingleShot(True)
        self._timer_biblioteca.timeout.connect(self.cargar_biblioteca)

        # Vista 0: la app normal. Vista 1: el reproductor maximizado.
        self.vistas = QStackedWidget()
        self.setCentralWidget(self.vistas)
        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.vistas.addWidget(raiz)
        vertical = QVBoxLayout(raiz)
        vertical.setContentsMargins(0, 0, 0, 0)
        vertical.setSpacing(0)

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(0)
        cuerpo.addWidget(self._crear_lateral())
        self.paginas = QStackedWidget()
        self.paginas.addWidget(self._crear_pagina_cola())
        self.paginas.addWidget(self._crear_pagina_biblioteca())
        self.paginas.addWidget(self._crear_pagina_buscar())
        cuerpo.addWidget(self.paginas, 1)
        vertical.addLayout(cuerpo, 1)
        vertical.addWidget(self._crear_reproductor())
        self.vista_completa = self._crear_vista_completa()
        self.vistas.addWidget(self.vista_completa)
        self._atajos()

        self._actualizar_libre()
        self._refrescar_stats()
        # La carpeta de descargas siempre forma parte de la biblioteca
        self.db.agregar_carpeta(Path(self.carpeta))
        self.cargar_biblioteca()
        QTimer.singleShot(500, self.escanear)

    # ---------- Barra lateral ----------

    def _crear_lateral(self) -> QWidget:
        lateral = QFrame()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(270)
        lay = QVBoxLayout(lateral)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(8)

        marca = QHBoxLayout()
        logo = QLabel()
        logo.setObjectName("logo")
        logo.setFixedSize(44, 44)
        logo.setAlignment(Qt.AlignCenter)
        icono_app = recurso("icono.ico")
        if icono_app.exists():
            logo.setPixmap(redondear(QPixmap(str(icono_app)), 30, 7))
        textos = QVBoxLayout()
        textos.setSpacing(0)
        textos.addWidget(etiqueta(NOMBRE_APP, "marca"))
        textos.addWidget(etiqueta(f"v{VERSION} · motor yt-dlp", "marcaSub"))
        marca.addWidget(logo)
        marca.addSpacing(6)
        marca.addLayout(textos, 1)
        lay.addLayout(marca)
        lay.addSpacing(18)

        pegar = QPushButton("  Pegar URL")
        pegar.setObjectName("pegar")
        pegar.setIcon(icono(I_PEGAR, CIAN, 16))
        pegar.setCursor(Qt.PointingHandCursor)
        pegar.clicked.connect(self.pegar_url)
        lay.addWidget(pegar)
        lay.addSpacing(12)

        self.nav = QButtonGroup(self)
        # El id de cada botón es el índice de su página en self.paginas
        for i, glifo, texto in [(0, I_DESCARGA, "Cola de descarga"), (2, I_BUSCAR, "Buscar música"),
                                (1, I_BIBLIOTECA, "Biblioteca")]:
            b = QPushButton(f"   {texto}")
            b.setObjectName("nav")
            b.setIcon(icono(glifo, TEXTO, 16))
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.nav.addButton(b, i)
            lay.addWidget(b)
        self.nav.button(0).setChecked(True)
        self.nav.idClicked.connect(self._ir_a)
        sonando = QPushButton("   Reproduciendo")
        sonando.setObjectName("nav")
        sonando.setIcon(icono(I_EXPANDIR, TEXTO, 16))
        sonando.setCursor(Qt.PointingHandCursor)
        sonando.setToolTip("Reproductor en grande (F11)")
        sonando.clicked.connect(self.maximizar)
        lay.addWidget(sonando)

        lay.addStretch()
        herramientas = [("ffmpeg", nucleo.ffmpeg_disponible()), ("deno", bool(nucleo.ruta_herramienta("deno")))]
        estado = "   ".join(f"{'●' if ok else '○'} {n}" for n, ok in herramientas)
        lay.addWidget(etiqueta(estado, "estadoMotor"))
        return lateral

    def _ir_a(self, i: int):
        self.paginas.setCurrentIndex(i)
        if i == 1:
            self.cargar_biblioteca()
        elif i == 2:
            self.pagina_buscar.entrada.setFocus()

    def pegar_url(self):
        texto = QApplication.clipboard().text().strip()
        if texto:
            self.url.setText(texto)
            self.nav.button(0).click()
            self.analizar()

    # ---------- Página: cola ----------

    def _crear_pagina_cola(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(24, 22, 24, 12)
        lay.setSpacing(16)

        # URL + fuentes + analizar
        fila_url = QHBoxLayout()
        fila_url.setSpacing(14)
        self.caja_url = QFrame()
        self.caja_url.setObjectName("cajaUrl")
        lu = QHBoxLayout(self.caja_url)
        lu.setContentsMargins(14, 2, 8, 2)
        icono_link = QLabel()
        icono_link.setPixmap(icono(I_LINK, TENUE, 16).pixmap(16, 16))
        self.url = QLineEdit()
        self.url.setObjectName("url")
        self.url.setPlaceholderText("Pega el link de una playlist, álbum o canción…")
        self.url.textChanged.connect(self._url_cambio)
        self.url.returnPressed.connect(self.analizar)
        limpiar = boton_icono(I_CERRAR, "Borrar", TENUE, 12)
        limpiar.clicked.connect(self.url.clear)
        lu.addWidget(icono_link)
        lu.addWidget(self.url, 1)
        lu.addWidget(limpiar)
        fila_url.addWidget(self.caja_url, 1)

        fuentes = QFrame()
        fuentes.setObjectName("fuentes")
        lf = QHBoxLayout(fuentes)
        lf.setContentsMargins(10, 8, 10, 8)
        lf.setSpacing(6)
        self.chips_fuente = {}
        for clave in ("spotify", "ytmusic", "youtube", "soundcloud"):
            c = QLabel(nucleo.FUENTES[clave])
            c.setObjectName("fuente")
            self.chips_fuente[clave] = c
            lf.addWidget(c)
        fila_url.addWidget(fuentes)

        self.btn_analizar = QPushButton("  Analizar playlist")
        self.btn_analizar.setObjectName("analizar")
        self.btn_analizar.setIcon(icono(I_BUSCAR, CIAN, 16))
        self.btn_analizar.setCursor(Qt.PointingHandCursor)
        self.btn_analizar.clicked.connect(self.analizar)
        fila_url.addWidget(self.btn_analizar)
        lay.addLayout(fila_url)

        # Tarjetas de configuración
        fila_cfg = QHBoxLayout()
        fila_cfg.setSpacing(14)
        fila_cfg.addWidget(self._tarjeta_destino(), 6)
        fila_cfg.addWidget(self._tarjeta_formato(), 3)
        fila_cfg.addWidget(self._tarjeta_hilos(), 0)
        self.btn_iniciar = QPushButton("  Iniciar descarga")
        self.btn_iniciar.setObjectName("iniciar")
        self.btn_iniciar.setIcon(icono(I_RAYO, "#04121a", 18))
        self.btn_iniciar.setIconSize(QSize(18, 18))
        self.btn_iniciar.setCursor(Qt.PointingHandCursor)
        self.btn_iniciar.setMinimumWidth(220)
        self.btn_iniciar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.btn_iniciar.clicked.connect(self.iniciar)
        fila_cfg.addWidget(self.btn_iniciar)
        lay.addLayout(fila_cfg)

        sep = QFrame()
        sep.setObjectName("separador")
        lay.addWidget(sep)

        # Monitor
        monitor = QHBoxLayout()
        monitor.setSpacing(14)
        self.punto = QLabel()
        self.punto.setObjectName("punto")
        self.punto.setFixedSize(12, 12)
        monitor.addWidget(self.punto)
        monitor.addWidget(etiqueta("Monitor de descargas", "tituloSeccion"))
        monitor.addSpacing(8)
        self.stats = etiqueta("", "stat")
        self.stats.setTextFormat(Qt.RichText)
        monitor.addWidget(self.stats)
        self.lbl_velocidad = etiqueta("Velocidad: 0 B/s", "velocidad")
        monitor.addWidget(self.lbl_velocidad)
        monitor.addStretch()
        lay.addLayout(monitor)

        acciones = QHBoxLayout()
        acciones.setSpacing(10)
        self.btn_reintentar = QPushButton("  Reintentar fallidos")
        self.btn_reintentar.setObjectName("reintentarTodos")
        self.btn_reintentar.setIcon(icono(I_REINTENTAR, "#fca5a5", 14))
        self.btn_reintentar.clicked.connect(self.reintentar_fallidos)
        self.btn_pausa = QPushButton("  Pausar todo")
        self.btn_pausa.setObjectName("secundario")
        self.btn_pausa.setIcon(icono(I_PAUSA, TEXTO, 14))
        self.btn_pausa.setCheckable(True)
        self.btn_pausa.toggled.connect(self._pausar)
        self.btn_limpiar = QPushButton("  Limpiar completados")
        self.btn_limpiar.setObjectName("secundario")
        self.btn_limpiar.setIcon(icono(I_LIMPIAR, TEXTO, 14))
        self.btn_limpiar.clicked.connect(self.limpiar_completados)
        for b in (self.btn_reintentar, self.btn_pausa, self.btn_limpiar):
            b.setCursor(Qt.PointingHandCursor)
            acciones.addWidget(b)
        acciones.addStretch()
        lay.addLayout(acciones)

        # Tabla
        cabecera = QFrame()
        cabecera.setObjectName("cabecera")
        lc = QHBoxLayout(cabecera)
        lc.setContentsMargins(17, 4, 15, 4)
        lc.setSpacing(ESPACIO)
        for texto, ancho, alin in [("#", C_NUM, Qt.AlignCenter), ("", C_PORTADA, Qt.AlignLeft),
                                   ("TÍTULO Y ARTISTA", None, Qt.AlignLeft), ("FORMATO", C_FORMATO, Qt.AlignLeft),
                                   ("TAMAÑO", C_TAMANO, Qt.AlignLeft), ("PROGRESO", C_PROGRESO, Qt.AlignLeft),
                                   ("ESTADO", C_ESTADO, Qt.AlignRight), ("ACCIÓN", C_ACCION, Qt.AlignCenter)]:
            l = QLabel(texto)
            l.setAlignment(alin)
            if ancho:
                l.setFixedWidth(ancho)
                lc.addWidget(l)
            else:
                lc.addWidget(l, 1)
        lay.addWidget(cabecera)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.viewport().setObjectName("fondoLista")
        contenedor = QWidget()
        contenedor.setObjectName("fondoLista")
        self.lista_filas = QVBoxLayout(contenedor)
        self.lista_filas.setContentsMargins(0, 0, 4, 0)
        self.lista_filas.setSpacing(8)
        self.vacio = etiqueta("Pega un link de YouTube, YT Music, Spotify o SoundCloud y presiona “Analizar playlist”.",
                              "vacio")
        self.vacio.setAlignment(Qt.AlignCenter)
        self.vacio.setMinimumHeight(160)
        self.lista_filas.addWidget(self.vacio)
        self.lista_filas.addStretch()
        self.scroll.setWidget(contenedor)
        lay.addWidget(self.scroll, 1)
        return pagina

    def _tarjeta(self) -> tuple[QFrame, QHBoxLayout]:
        t = QFrame()
        t.setObjectName("tarjeta")
        l = QHBoxLayout(t)
        l.setContentsMargins(16, 12, 16, 12)
        l.setSpacing(12)
        return t, l

    def _tarjeta_destino(self) -> QWidget:
        t, l = self._tarjeta()
        ic = QLabel()
        ic.setPixmap(icono(I_CARPETA, CIAN, 22).pixmap(22, 22))
        l.addWidget(ic)

        textos = QVBoxLayout()
        textos.setSpacing(6)
        arriba = QHBoxLayout()
        arriba.addWidget(etiqueta("DESTINO"))
        arriba.addStretch()
        self.lbl_libre = etiqueta("", "libre")
        arriba.addWidget(self.lbl_libre)
        textos.addLayout(arriba)

        medio = QHBoxLayout()
        musica = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
        self.carpeta = self.ajustes.value("carpeta", str(Path(musica) / "WaveDrop"))
        self.lbl_carpeta = LabelRecortado(self.carpeta, Qt.ElideMiddle)
        self.lbl_carpeta.setObjectName("valorMono")
        self.lbl_carpeta.setToolTip(self.carpeta)
        examinar = QPushButton("Examinar…")
        examinar.setObjectName("examinar")
        examinar.setCursor(Qt.PointingHandCursor)
        examinar.clicked.connect(self.elegir_carpeta)
        medio.addWidget(self.lbl_carpeta, 1)
        medio.addWidget(examinar)
        textos.addLayout(medio)

        self.por_artista = QCheckBox("Separar en carpetas por artista")
        self.por_artista.setChecked(self.ajustes.value("por_artista", True, type=bool))
        textos.addWidget(self.por_artista)
        l.addLayout(textos, 1)
        return t

    def _tarjeta_formato(self) -> QWidget:
        t, l = self._tarjeta()
        v = QVBoxLayout()
        v.setSpacing(8)
        v.addWidget(etiqueta("FORMATO Y CALIDAD"))
        self.formato = QComboBox()
        self.formato.addItems([f.etiqueta for f in nucleo.FORMATOS])
        self.formato.setCurrentIndex(min(self.ajustes.value("formato", 0, type=int), len(nucleo.FORMATOS) - 1))
        self.formato.setCursor(Qt.PointingHandCursor)
        self.formato.currentIndexChanged.connect(self._formato_cambio)
        v.addWidget(self.formato)
        self.usar_mb = QCheckBox("Completar datos con MusicBrainz")
        self.usar_mb.setToolTip("Al terminar cada descarga busca álbum, año, número de pista, género y portada")
        self.usar_mb.setChecked(self.ajustes.value("musicbrainz", True, type=bool))
        v.addWidget(self.usar_mb)
        l.addLayout(v, 1)
        return t

    def _tarjeta_hilos(self) -> QWidget:
        t, l = self._tarjeta()
        v = QVBoxLayout()
        v.setSpacing(8)
        v.addWidget(etiqueta("DESCARGAS SIMULTÁNEAS"))
        segmentos = QHBoxLayout()
        segmentos.setSpacing(6)
        self.hilos = QButtonGroup(self)
        guardado = self.ajustes.value("hilos", 3, type=int)
        for n in range(1, 5):
            b = QPushButton(str(n))
            b.setObjectName("segmento")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(n == guardado)
            self.hilos.addButton(b, n)
            segmentos.addWidget(b)
        v.addLayout(segmentos)
        l.addLayout(v, 1)
        return t

    # ---------- Configuración ----------

    def elegir_carpeta(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Carpeta de descarga", self.carpeta)
        if carpeta:
            self.carpeta = str(Path(carpeta))
            self.lbl_carpeta.setText(self.carpeta)
            self.lbl_carpeta.setToolTip(self.carpeta)
            self.lbl_carpeta.update()
            self._actualizar_libre()
            self._guardar_ajustes()
            self.db.agregar_carpeta(Path(self.carpeta))
            self.escanear()

    def _actualizar_libre(self):
        ruta = Path(self.carpeta)
        while not ruta.exists() and ruta.parent != ruta:
            ruta = ruta.parent
        try:
            self.lbl_libre.setText(f"{fmt_bytes(shutil.disk_usage(ruta).free)} libres")
        except OSError:
            self.lbl_libre.setText("")

    def _formato_actual(self) -> nucleo.Formato:
        return nucleo.FORMATOS[self.formato.currentIndex()]

    def _formato_cambio(self):
        for f in self.filas.values():
            if f.estado in (ESPERA, FALLO, CANCELADA):
                f.formato.setText(self._formato_actual().corto)

    def _guardar_ajustes(self):
        self.ajustes.setValue("carpeta", self.carpeta)
        self.ajustes.setValue("formato", self.formato.currentIndex())
        self.ajustes.setValue("hilos", self.hilos.checkedId())
        self.ajustes.setValue("por_artista", self.por_artista.isChecked())
        self.ajustes.setValue("musicbrainz", self.usar_mb.isChecked())

    def _url_cambio(self, texto: str):
        fuente = nucleo.detectar_fuente(texto) if texto.strip().startswith("http") else ""
        for clave, chip in self.chips_fuente.items():
            set_prop(chip, "activa", clave if clave == fuente else "")

    # ---------- Analizar y descargar ----------

    def _validar(self) -> bool:
        if not nucleo.ffmpeg_disponible():
            QMessageBox.critical(self, NOMBRE_APP, "No se encontró ffmpeg, que hace falta para convertir el audio.\n"
                                 "Reinstala la aplicación o instala ffmpeg con: winget install ffmpeg")
            return False
        return True

    def analizar(self):
        url = self.url.text().strip()
        if not url:
            self.url.setFocus()
            return
        if self.analizador or self.gestor.activo:
            return
        self.btn_analizar.setEnabled(False)
        self.btn_analizar.setText("  Analizando…")
        self.analizador = Analizador(url)
        self.analizador.listo.connect(self._analizado)
        self.analizador.fallo.connect(self._fallo_analisis)
        self.analizador.finished.connect(self._fin_analisis)
        self.analizador.start()
        print(f"Analizando: {url}", flush=True)

    def _fin_analisis(self):
        self.analizador = None
        self.btn_analizar.setEnabled(True)
        self.btn_analizar.setText("  Analizar playlist")
        self._refrescar_stats()

    def _fallo_analisis(self, msg: str):
        print(f"Falló el análisis: {msg}", flush=True)
        self.iniciar_al_analizar = False
        QMessageBox.critical(self, NOMBRE_APP, f"No se pudo leer el link:\n\n{msg}")

    def _analizado(self, col: nucleo.Coleccion):
        print(f"Analizado: {col.titulo} ({col.fuente}), {len(col.entradas)} canciones", flush=True)
        self.coleccion = col
        for f in self.filas.values():
            f.deleteLater()
        self.filas.clear()
        self.velocidades.clear()
        formato = self._formato_actual().corto
        for e in col.entradas:
            fila = FilaCancion(self.sig_fila, e, formato, self.imagenes)
            fila.accion.connect(self._accion_fila)
            self.filas[self.sig_fila] = fila
            self.lista_filas.insertWidget(self.lista_filas.count() - 1, fila)
            self.sig_fila += 1
            # ¿Ya la tienes en alguna carpeta de la biblioteca?
            existente = self.db.buscar_existente(e.artista, e.titulo, e.duracion)
            if existente:
                fila.actualizar(EXISTE, 0, 0, 0, str(existente.ruta))
        self.vacio.setVisible(not self.filas)
        self._refrescar_stats()
        if not col.entradas:
            QMessageBox.information(self, NOMBRE_APP, "No encontré canciones en ese link.")
        if self.iniciar_al_analizar:
            self.iniciar_al_analizar = False
            QTimer.singleShot(0, self.iniciar)

    def iniciar(self):
        if not self._validar():
            return
        if not self.coleccion or not any(f.estado == ESPERA for f in self.filas.values()):
            if self.url.text().strip() and not self.analizador:
                self.iniciar_al_analizar = True
                self.analizar()
            return
        self._guardar_ajustes()
        pendientes = [(i, f.entrada) for i, f in self.filas.items() if f.estado == ESPERA]
        for i, _ in pendientes:
            self.filas[i].formato.setText(self._formato_actual().corto)
        self._encolar(pendientes)

    def _encolar(self, filas):
        if not filas:
            return
        if self.gestor.activo:
            descargador = self.gestor.descargador
        else:
            descargador = nucleo.Descargador(self.carpeta, self._formato_actual(), not self.por_artista.isChecked(),
                                             self.coleccion.titulo if self.coleccion else "Descargas")
            self._mb_al_descargar = self.usar_mb.isChecked()  # los hilos leen esto, no el checkbox
        self.gestor.encolar(descargador, filas, self.hilos.checkedId())
        self._refrescar_stats()

    def reintentar_fallidos(self):
        if self._validar():
            self._encolar([(i, f.entrada) for i, f in self.filas.items() if f.estado in (FALLO, CANCELADA)])

    def _accion_fila(self, fila: int, tipo: str):
        f = self.filas.get(fila)
        if not f:
            return
        if tipo == "cancelar":
            if f.estado == ESPERA:
                f.actualizar(CANCELADA, 0, 0, 0, "")
                self._refrescar_stats()
            else:
                self.gestor.cancelar(fila)
        elif tipo == "reintentar" and self._validar():
            self._encolar([(fila, f.entrada)])
        elif tipo == "reproducir" and f.ruta:
            self.reproducir_ruta(Path(f.ruta))
        elif tipo == "carpeta" and f.ruta:
            abrir_en_explorador(Path(f.ruta))
        elif tipo == "copiar":
            QApplication.clipboard().setText(f.entrada.url)
        elif tipo == "copiar_error":
            QApplication.clipboard().setText(f.detalle)
        elif tipo == "forzar":
            f.ruta = None
            f.actualizar(ESPERA, 0, 0, 0, "")
            self._refrescar_stats()

    def _pausar(self, pausa: bool):
        self.gestor.pausar(pausa)
        self.btn_pausa.setText("  Reanudar" if pausa else "  Pausar todo")
        self.btn_pausa.setIcon(icono(I_PLAY if pausa else I_PAUSA, TEXTO, 14))

    def limpiar_completados(self):
        for i in [i for i, f in self.filas.items() if f.estado in (LISTO, YA)]:
            self.filas.pop(i).deleteLater()
        self.vacio.setVisible(not self.filas)
        self._refrescar_stats()

    def _estado_fila(self, fila, estado, pct, vel, eta, detalle):
        f = self.filas.get(fila)
        if f is None:
            return
        cambio = f.estado != estado
        f.actualizar(estado, pct, vel, eta, detalle)
        if estado == DESCARGANDO:
            self.velocidades[fila] = vel
        else:
            self.velocidades.pop(fila, None)
        if cambio and estado in ACTIVOS:
            self.scroll.ensureWidgetVisible(f, 0, 80)
        if cambio or estado == DESCARGANDO:
            self._refrescar_stats()

    def _resultado_fila(self, fila, res: nucleo.Resultado):
        f = self.filas.get(fila)
        if f:
            f.poner_resultado(res)
        self._timer_biblioteca.start(1200)  # refrescar la biblioteca una vez, no por cada canción

    def _terminado(self):
        if self.btn_pausa.isChecked():
            self.btn_pausa.setChecked(False)
        self._refrescar_stats()
        fallidas = sum(f.estado == FALLO for f in self.filas.values())
        if fallidas:
            QMessageBox.warning(self, NOMBRE_APP, f"Terminó, pero {fallidas} canción(es) fallaron.\n"
                                "Están marcadas en rojo; pasa el mouse encima para ver el motivo.")

    def _refrescar_stats(self):
        estados = [f.estado for f in self.filas.values()]
        total = len(estados)
        completas = sum(e in (LISTO, YA) for e in estados)
        errores = estados.count(FALLO)
        en_cola = sum(e in (COLA, ESPERA) for e in estados)
        activas = sum(e in ACTIVOS for e in estados)
        ya_tienes = estados.count(EXISTE)
        sep = f'<span style="color:{BORDE_FUERTE}">&nbsp;&nbsp;•&nbsp;&nbsp;</span>'
        partes = [
            f'<b style="color:{TEXTO}">{total}</b> detectadas',
            f'<b style="color:{CIAN}">{completas}</b> <span style="color:{CIAN}">completadas</span>',
            f'<b style="color:{ROJO}">{errores}</b> <span style="color:{ROJO}">con error</span>',
            f'<b style="color:{TEXTO}">{en_cola}</b> en cola',
        ]
        if ya_tienes:
            partes.append(f'<b style="color:#93c5fd">{ya_tienes}</b> <span style="color:#93c5fd">ya las tienes</span>')
        self.stats.setText(sep.join(partes))
        total_vel = sum(self.velocidades.values())
        self.lbl_velocidad.setText(f"Velocidad: {fmt_bytes(total_vel)}/s" if total_vel else "Velocidad: —")
        set_prop(self.punto, "activo", activas > 0 or self.analizador is not None)

        espera = estados.count(ESPERA)
        ocupado = self.gestor.activo
        self.btn_iniciar.setText(f"  Iniciar descarga ({espera})" if espera else
                                 "  Descargando…" if ocupado else "  Iniciar descarga")
        self.btn_iniciar.setEnabled(bool(espera) or (not ocupado and bool(self.url.text().strip())))
        self.btn_analizar.setEnabled(not ocupado and self.analizador is None)
        self.btn_reintentar.setEnabled(any(e in (FALLO, CANCELADA) for e in estados))
        self.btn_pausa.setEnabled(ocupado)
        self.btn_limpiar.setEnabled(completas > 0)
        self.formato.setEnabled(not ocupado)
        self.por_artista.setEnabled(not ocupado)
        for b in self.hilos.buttons():
            b.setEnabled(not ocupado)

    # ---------- Página: biblioteca ----------

    def _crear_pagina_biblioteca(self) -> QWidget:
        self.pagina_bib = PaginaBiblioteca(self.db, self.imagenes)
        self.pagina_bib.previa.connect(self.vista_previa)
        self.pagina_bib.descargar.connect(self.descargar_resultados)
        self.pagina_bib.buscar_en_linea.connect(self.buscar_en_linea)
        self.pagina_bib.actualizar_recomendaciones.connect(lambda: self.cargar_recomendaciones(forzar=True))
        self.pagina_bib.reproducir.connect(self._reproducir_lista)
        self.pagina_bib.reproducir_aleatorio.connect(self._reproducir_aleatorio)
        self.pagina_bib.completar_mb.connect(self.completar_musicbrainz)
        self.pagina_bib.administrar_carpetas.connect(self._dialogo_carpetas)
        self.pagina_bib.escanear.connect(self.escanear)
        return self.pagina_bib

    def cargar_biblioteca(self):
        self.pagina_bib.refrescar()

    def _marcar_actual(self):
        actual = self.biblioteca[self.indice_actual] if 0 <= self.indice_actual < len(self.biblioteca) else None
        self.pagina_bib.marcar(actual)

    def _reproducir_lista(self, rutas: list, i: int):
        self.biblioteca = list(rutas)
        self._reproducir_indice(i)

    def _reproducir_aleatorio(self, rutas: list):
        if not rutas:
            return
        if not self.aleatorio:
            self._alternar_aleatorio()
        self.biblioteca = list(rutas)
        self._reproducir_indice(random.randrange(len(rutas)))

    def _dialogo_carpetas(self):
        d = DialogoCarpetas(self.db, self.carpeta, self)
        d.exec()
        if d.cambio:
            self.escanear()

    def escanear(self):
        if self._escaneando:
            return
        self._escaneando = True
        self.pagina_bib.estado("Escaneando carpetas…")

        def trabajo():
            nuevas = quitadas = 0
            try:
                nuevas, quitadas = self.db.escanear(self.fondo.escaneo_progreso.emit, lambda: self._cerrando)
            except Exception:
                print("Escaneo falló:\n" + traceback.format_exc(), flush=True)
            self.fondo.escaneo_fin.emit(nuevas, quitadas)

        threading.Thread(target=trabajo, daemon=True).start()

    def _escaneo_fin(self, nuevas: int, quitadas: int):
        self._escaneando = False
        partes = [f"{nuevas} nuevas"] if nuevas else []
        if quitadas:
            partes.append(f"{quitadas} ya no existen")
        self._estado_temporal("Escaneo listo" + (": " + ", ".join(partes) if partes else ""))
        self.cargar_biblioteca()
        if not self._recs_iniciales:  # la primera vez, con la biblioteca ya leída
            self._recs_iniciales = True
            self.cargar_recomendaciones()

    def completar_musicbrainz(self, canciones: list):
        if self._mb_activo:
            QMessageBox.information(self, NOMBRE_APP, "Ya se están completando datos con MusicBrainz, espera a que termine.")
            return
        if not canciones:
            QMessageBox.information(self, NOMBRE_APP, "Todas tus canciones ya tienen datos de MusicBrainz.")
            return
        self._mb_activo = True

        def trabajo():
            ok = sin = 0
            for i, c in enumerate(canciones, start=1):
                if self._cerrando:
                    break
                self.fondo.mb_progreso.emit(i, len(canciones), c.titulo)
                try:
                    if musicbrainz.completar(c.ruta, c.titulo, c.artista, c.duracion, c.album):
                        self.db.indexar(c.ruta)
                        ok += 1
                    else:
                        sin += 1
                except Exception as e:
                    print(f"MusicBrainz falló con {c.ruta}: {e}", flush=True)
                    sin += 1
            self.fondo.mb_fin.emit(ok, sin)

        threading.Thread(target=trabajo, daemon=True).start()

    def _mb_fin(self, ok: int, sin: int):
        self._mb_activo = False
        self._estado_temporal(f"MusicBrainz: {ok} completadas" + (f", {sin} sin coincidencia" if sin else ""))
        self.cargar_biblioteca()

    def _estado_temporal(self, texto: str, ms: int = 7000):
        self.pagina_bib.estado(texto)
        QTimer.singleShot(ms, lambda: self.pagina_bib.lbl_estado.text() == texto and self.pagina_bib.estado(""))

    def _postproceso_descarga(self, res: nucleo.Resultado):
        """Corre en el hilo de descarga: completa con MusicBrainz y agrega la canción a la biblioteca."""
        ruta = Path(res.ruta)
        if self._mb_al_descargar:
            datos = biblioteca.leer_archivo(ruta)
            try:
                musicbrainz.completar(ruta, datos["titulo"], datos["artista"], datos["duracion"], datos["album"])
            except Exception as e:
                print(f"MusicBrainz falló con {ruta}: {e}", flush=True)
        self.db.indexar(ruta)
        c = self.db.cancion_por_ruta(ruta)
        if c:
            res.titulo, res.artista = c.titulo, c.artista
            self.db.registrar("descarga", ruta, c.artista, c.titulo)

    # ---------- Página: buscar música y recomendaciones ----------

    def _crear_pagina_buscar(self) -> QWidget:
        self.pagina_buscar = PaginaBuscar(self.db, self.imagenes)
        self.pagina_buscar.previa.connect(self.vista_previa)
        self.pagina_buscar.descargar.connect(self.descargar_resultados)
        self.pagina_buscar.descargar_album.connect(self.descargar_album)
        return self.pagina_buscar

    def buscar_en_linea(self, consulta: str):
        self.nav.button(2).click()
        self.pagina_buscar.tipos.button(0).setChecked(True)
        self.pagina_buscar.buscar(consulta)

    def descargar_resultados(self, resultados: list):
        """Agrega canciones de YouTube Music a la cola (sin borrar lo que ya hay) y empieza a bajarlas."""
        if not resultados or not self._validar():
            return
        formato = self._formato_actual().corto
        nuevas = []
        for r in resultados:
            entrada = explorar.a_entrada(r, len(self.filas) + 1)
            fila = FilaCancion(self.sig_fila, entrada, formato, self.imagenes)
            fila.accion.connect(self._accion_fila)
            self.filas[self.sig_fila] = fila
            self.lista_filas.insertWidget(self.lista_filas.count() - 1, fila)
            nuevas.append((self.sig_fila, entrada))
            self.sig_fila += 1
        self.vacio.setVisible(False)
        self._encolar(nuevas)
        n = len(nuevas)
        texto = f"“{resultados[0].titulo}” se agregó a la cola" if n == 1 else f"{n} canciones agregadas a la cola"
        self.pagina_buscar.estado(texto)
        self._estado_temporal(texto, 5000)

    def descargar_album(self, album: explorar.ResultadoAlbum):
        self.pagina_buscar.estado(f"Abriendo “{album.titulo}”…")

        def trabajo():
            try:
                self.fondo.album_listo.emit(explorar.url_album(album.browse_id))
            except Exception as e:
                self.fondo.album_error.emit(str(e))

        threading.Thread(target=trabajo, daemon=True).start()

    def _album_listo(self, url: str):
        # El álbum pasa por la cola normal: se analiza y se marcan las canciones que ya tienes
        self.pagina_buscar.estado("")
        if self.gestor.activo:
            QMessageBox.information(self, NOMBRE_APP, "Espera a que terminen las descargas actuales para analizar el álbum.")
            return
        self.url.setText(url)
        self.nav.button(0).click()
        self.analizar()

    def vista_previa(self, r: explorar.ResultadoCancion):
        if self._previa_cargando:
            return
        self._previa_cargando = True
        texto = f"Cargando vista previa de “{r.titulo}”…"
        self.pagina_buscar.estado(texto)
        self.pagina_bib.estado(texto)

        def trabajo():
            try:
                self.fondo.previa_lista.emit(r, str(explorar.previa(r.video_id)))
            except Exception as e:
                self.fondo.previa_error.emit(str(e))

        threading.Thread(target=trabajo, daemon=True).start()

    def _previa_error(self, msg: str):
        self._previa_cargando = False
        self.pagina_buscar.estado("")
        self.pagina_bib.estado("")
        QMessageBox.warning(self, NOMBRE_APP, f"No se pudo cargar la vista previa:\n\n{msg}")

    def _reproducir_previa(self, r: explorar.ResultadoCancion, ruta: str):
        """Toca el audio de la caché sin agregarlo a la biblioteca ni a la cola de reproducción."""
        self._previa_cargando = False
        self.pagina_buscar.estado("")
        self.pagina_bib.estado("")
        self._en_previa = True
        self._contada = True  # las vistas previas no cuentan en el historial
        self.player.setSource(QUrl.fromLocalFile(ruta))
        self.player.play()
        for l in self.w_titulo:
            l.setText(r.titulo)
            l.update()
        for l in self.w_artista:
            l.setText(r.artista)
            l.update()
        self.vp_album.setText(r.album)
        self.vp_album.setVisible(bool(r.album))
        for c in self.w_chip:
            c.setText("VISTA PREVIA · YouTube Music")
            c.show()
        self._poner_portadas(None)
        self.imagenes.pedir(r.miniatura, self._poner_portadas)
        for o in self.w_ondas:
            o.semilla(r.video_id)
        self.pagina_bib.marcar(None)
        self._cargar_letra(Path(ruta), {"titulo": r.titulo, "artista": r.artista, "album": r.album})
        self.setWindowTitle(f"{r.titulo} (vista previa) · {NOMBRE_APP}")

    def cargar_recomendaciones(self, forzar: bool = False):
        if self._recs_cargando:
            return
        if not forzar:
            guardadas = explorar.recomendaciones_guardadas()
            if guardadas is not None:
                self._recomendaciones_listas(guardadas)
                return
        if self.db.total() == 0 and not self.db.semillas(1):
            self.pagina_bib.poner_recomendaciones(
                [], "Descarga o escucha algunas canciones y aquí aparecerán recomendaciones para ti.")
            return
        self._recs_cargando = True
        self.pagina_bib.btn_recs.setEnabled(False)
        self.pagina_bib.poner_recomendaciones(None, "Buscando recomendaciones en YouTube Music…")

        def trabajo():
            try:
                self.fondo.recs_listas.emit(explorar.recomendaciones(self.db))
            except Exception as e:
                print("Recomendaciones fallaron:\n" + traceback.format_exc(), flush=True)
                self.fondo.recs_error.emit(str(e))

        threading.Thread(target=trabajo, daemon=True).start()

    def _recomendaciones_listas(self, secciones: list):
        self._recs_cargando = False
        self.pagina_bib.btn_recs.setEnabled(True)
        self.pagina_bib.poner_recomendaciones(
            secciones, "" if secciones else "No encontré recomendaciones nuevas. Escucha o descarga más música.")

    def _recomendaciones_error(self, msg: str):
        self._recs_cargando = False
        self.pagina_bib.btn_recs.setEnabled(True)
        print(f"Recomendaciones: {msg}", flush=True)
        self.pagina_bib.poner_recomendaciones([], "No se pudieron cargar las recomendaciones.\n¿Hay conexión a internet?")

    # ---------- Reproductor ----------
    # La barra de abajo y la vista maximizada comparten el mismo QMediaPlayer; los widgets que
    # existen en las dos se guardan en listas (w_*) para actualizarlos juntos.

    def _crear_motor(self):
        self.player = QMediaPlayer(self)
        self.salida = QAudioOutput(self)
        self.player.setAudioOutput(self.salida)
        self.salida.setVolume(self.ajustes.value("volumen", 0.78, type=float))
        self.player.positionChanged.connect(self._posicion)
        self.player.durationChanged.connect(self._posicion)
        self.player.playbackStateChanged.connect(self._icono_play)
        self.player.mediaStatusChanged.connect(self._estado_media)
        self.cargador_letra = CargadorLetra(self)
        self.cargador_letra.lista.connect(self._letra_lista)
        self.aleatorio = False
        self.w_play, self.w_ondas, self.w_pos, self.w_dur = [], [], [], []
        self.w_aleatorio, self.w_repetir = [], []
        self.w_volumen, self.w_mute, self.w_vol_lbl = [], [], []
        self.w_titulo, self.w_artista, self.w_chip = [], [], []

    def _controles(self, grande: bool) -> QHBoxLayout:
        px = 22 if grande else 18
        fila = QHBoxLayout()
        fila.setSpacing(24 if grande else 14)
        aleatorio = boton_icono(I_ALEATORIO, "Aleatorio", TENUE, px)
        aleatorio.clicked.connect(self._alternar_aleatorio)
        anterior = boton_icono(I_ANTERIOR, "Anterior (Ctrl+←)", TEXTO, px)
        anterior.clicked.connect(self.anterior)
        play = boton_icono(I_PLAY, "Reproducir / pausar (Espacio)", "#04121a",
                           30 if grande else 22, "playXL" if grande else "playGrande")
        play.setFixedSize(*((76, 76) if grande else (56, 56)))
        play.clicked.connect(self.play_pausa)
        siguiente = boton_icono(I_SIGUIENTE, "Siguiente (Ctrl+→)", TEXTO, px)
        siguiente.clicked.connect(lambda: self.siguiente(manual=True))
        repetir = boton_icono(I_REPETIR, "Repetir: no", TENUE, px)
        repetir.clicked.connect(self._ciclar_repetir)
        self.w_play.append(play)
        self.w_aleatorio.append(aleatorio)
        self.w_repetir.append(repetir)
        fila.addStretch()
        for w in (aleatorio, anterior, play, siguiente, repetir):
            fila.addWidget(w)
        fila.addStretch()
        return fila

    def _linea_tiempo(self, grande: bool) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(12)
        pos = etiqueta("0:00", "rpTiempo")
        dur = etiqueta("0:00", "rpTiempo")
        onda = Onda(110 if grande else 64)
        onda.setMinimumHeight(64 if grande else 34)
        onda.buscar.connect(lambda f: self.player.setPosition(int(f * self.player.duration())))
        onda.saltar.connect(self._saltar)
        self.w_pos.append(pos)
        self.w_dur.append(dur)
        self.w_ondas.append(onda)
        fila.addWidget(pos)
        fila.addWidget(onda, 1)
        fila.addWidget(dur)
        return fila

    def _control_volumen(self, ancho: int) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(8)
        mute = boton_icono(I_VOLUMEN, "Silenciar (Ctrl+M)", TEXTO, 18)
        mute.clicked.connect(self._alternar_mute)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(int(self.salida.volume() * 100))
        slider.setFixedWidth(ancho)
        slider.setCursor(Qt.PointingHandCursor)
        slider.setToolTip("Volumen (Ctrl+↑ / Ctrl+↓)")
        slider.valueChanged.connect(self._volumen)
        lbl = etiqueta(f"{slider.value()}%", "rpTiempo")
        lbl.setFixedWidth(38)
        self.w_mute.append(mute)
        self.w_volumen.append(slider)
        self.w_vol_lbl.append(lbl)
        fila.addWidget(mute)
        fila.addWidget(slider)
        fila.addWidget(lbl)
        return fila

    def _crear_reproductor(self) -> QWidget:
        self._crear_motor()
        barra = QFrame()
        barra.setObjectName("reproductor")
        barra.setFixedHeight(104)
        lay = QHBoxLayout(barra)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(18)

        # Izquierda: portada (clic = maximizar) y datos
        izq = QHBoxLayout()
        izq.setSpacing(14)
        self.rp_portada = PortadaClic(64, 8, I_EXPANDIR)
        self.rp_portada.setToolTip("Ver en grande (F11)")
        self.rp_portada.clicked.connect(self.maximizar)
        datos = QVBoxLayout()
        datos.setSpacing(2)
        titulo = LabelRecortado("Nada sonando")
        titulo.setObjectName("rpTitulo")
        artista = LabelRecortado("Elige una canción en la Biblioteca")
        artista.setObjectName("rpArtista")
        chip = etiqueta("", "rpChip")
        chip.hide()
        self.w_titulo.append(titulo)
        self.w_artista.append(artista)
        self.w_chip.append(chip)
        datos.addStretch()
        datos.addWidget(titulo)
        datos.addWidget(artista)
        datos.addWidget(chip, 0, Qt.AlignLeft)
        datos.addStretch()
        izq.addWidget(self.rp_portada)
        izq.addLayout(datos, 1)
        cont_izq = QWidget()
        cont_izq.setLayout(izq)
        cont_izq.setFixedWidth(330)
        lay.addWidget(cont_izq)

        # Centro: controles y onda
        centro = QVBoxLayout()
        centro.setSpacing(4)
        centro.addLayout(self._controles(False))
        centro.addLayout(self._linea_tiempo(False))
        lay.addLayout(centro, 1)

        # Derecha: volumen, carpeta y maximizar
        der = QHBoxLayout()
        der.setSpacing(6)
        der.addStretch()
        der.addLayout(self._control_volumen(100))
        der.addSpacing(8)
        letra = boton_icono(I_LETRA, "Ver letra (Ctrl+L)", TEXTO, 18)
        letra.clicked.connect(self.ver_letra)
        carpeta = boton_icono(I_CARPETA, "Mostrar en la carpeta", TEXTO, 18)
        carpeta.clicked.connect(self._abrir_actual)
        expandir = boton_icono(I_EXPANDIR, "Ver en grande (F11)", TEXTO, 18)
        expandir.clicked.connect(self.maximizar)
        der.addWidget(letra)
        der.addWidget(carpeta)
        der.addWidget(expandir)
        cont_der = QWidget()
        cont_der.setLayout(der)
        cont_der.setFixedWidth(330)
        lay.addWidget(cont_der)
        return barra

    def _crear_vista_completa(self) -> QWidget:
        vista = VistaReproduccion()
        lay = QVBoxLayout(vista)
        lay.setContentsMargins(44, 26, 44, 30)
        lay.setSpacing(18)

        arriba = QHBoxLayout()
        volver = QPushButton("  Volver")
        volver.setObjectName("secundario")
        volver.setIcon(icono(I_CONTRAER, TEXTO, 14))
        volver.setCursor(Qt.PointingHandCursor)
        volver.setToolTip("Volver a la app (Esc)")
        volver.clicked.connect(self.minimizar)
        arriba.addWidget(volver)
        arriba.addStretch()
        arriba.addWidget(etiqueta("REPRODUCIENDO DESDE TU BIBLIOTECA"))
        arriba.addStretch()
        carpeta = QPushButton("  Mostrar en carpeta")
        carpeta.setObjectName("secundario")
        carpeta.setIcon(icono(I_CARPETA, TEXTO, 14))
        carpeta.setCursor(Qt.PointingHandCursor)
        carpeta.clicked.connect(self._abrir_actual)
        arriba.addWidget(carpeta)
        lay.addLayout(arriba)

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(48)
        self.vp_portada = PortadaClic(360, 16, I_CONTRAER)
        self.vp_portada.setObjectName("vpPortada")
        self.vp_portada.setToolTip("Volver (Esc)")
        self.vp_portada.clicked.connect(self.minimizar)
        cuerpo.addWidget(self.vp_portada, 0, Qt.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(10)
        info.addStretch()
        info.addWidget(etiqueta("AHORA SUENA", "vpSobre"))
        titulo = QLabel("Nada sonando")
        titulo.setObjectName("vpTitulo")
        titulo.setWordWrap(True)
        artista = LabelRecortado("Elige una canción en la Biblioteca")
        artista.setObjectName("vpArtista")
        self.vp_album = LabelRecortado("")
        self.vp_album.setObjectName("vpAlbum")
        chip = etiqueta("", "rpChip")
        chip.hide()
        self.w_titulo.append(titulo)
        self.w_artista.append(artista)
        self.w_chip.append(chip)
        info.addWidget(titulo)
        info.addWidget(artista)
        info.addWidget(self.vp_album)
        info.addWidget(chip, 0, Qt.AlignLeft)
        info.addSpacing(26)
        info.addLayout(self._linea_tiempo(True))
        info.addSpacing(6)
        info.addLayout(self._controles(True))
        info.addSpacing(6)
        vol = QHBoxLayout()
        vol.addStretch()
        vol.addLayout(self._control_volumen(160))
        vol.addStretch()
        info.addLayout(vol)
        info.addStretch()
        cuerpo.addLayout(info, 1)

        # Columna derecha: pestañas Letra / A continuación
        lado = QWidget()
        lado.setFixedWidth(420)
        lado_lay = QVBoxLayout(lado)
        lado_lay.setContentsMargins(0, 0, 0, 0)
        lado_lay.setSpacing(12)
        pestanas = QHBoxLayout()
        pestanas.setSpacing(8)
        self.pestanas = QButtonGroup(self)
        for i, (glifo, texto) in enumerate([(I_LETRA, "LETRA"), (I_MUSICA, "A CONTINUACIÓN")]):
            b = QPushButton(f" {texto}")
            b.setObjectName("pestana")
            b.setIcon(icono(glifo, TENUE, 13))
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.pestanas.addButton(b, i)
            pestanas.addWidget(b)
        pestanas.addStretch()
        self.vp_letra_fuente = etiqueta("", "fuenteLetra")
        lado_lay.addLayout(pestanas)

        self.vp_lado = QStackedWidget()
        self.vp_letra = PanelLetra()
        self.vp_letra.buscar.connect(self.player.setPosition)
        self.vp_lado.addWidget(self.vp_letra)

        cola_w = QWidget()
        cola = QVBoxLayout(cola_w)
        cola.setContentsMargins(0, 0, 0, 0)
        cola.setSpacing(10)
        self.vp_cola_titulo = etiqueta("A CONTINUACIÓN")
        cola.addWidget(self.vp_cola_titulo)
        self.vp_cola = QListWidget()
        self.vp_cola.setObjectName("cola")
        self.vp_cola.setIconSize(QSize(16, 16))
        self.vp_cola.setCursor(Qt.PointingHandCursor)
        self.vp_cola.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.vp_cola.setTextElideMode(Qt.ElideRight)
        self.vp_cola.itemClicked.connect(lambda it: self._reproducir_indice(it.data(Qt.UserRole)))
        cola.addWidget(self.vp_cola, 1)
        self.vp_lado.addWidget(cola_w)
        lado_lay.addWidget(self.vp_lado, 1)
        lado_lay.addWidget(self.vp_letra_fuente, 0, Qt.AlignRight)
        cuerpo.addWidget(lado)
        lay.addLayout(cuerpo, 1)

        self.pestanas.idClicked.connect(self._pestana)
        self._pestana(self.ajustes.value("pestana", 0, type=int))
        self._poner_portadas(None)
        return vista

    def _pestana(self, i: int):
        self.pestanas.button(i).setChecked(True)
        self.vp_lado.setCurrentIndex(i)
        self.vp_letra_fuente.setVisible(i == 0)
        for j, glifo in enumerate((I_LETRA, I_MUSICA)):
            self.pestanas.button(j).setIcon(icono(glifo, CIAN if j == i else TENUE, 13))
        self.ajustes.setValue("pestana", i)

    def ver_letra(self):
        self._pestana(0)
        self.maximizar()

    def _cargar_letra(self, ruta: Path, meta: dict):
        self._letra_ruta = str(ruta)
        self.vp_letra.poner(None, "Buscando letra…")
        self.vp_letra_fuente.setText("")
        self.cargador_letra.pedir(ruta, meta)

    def _letra_lista(self, ruta: str, res):
        if ruta != getattr(self, "_letra_ruta", None):
            return  # ya cambió de canción
        if isinstance(res, Exception):
            print(f"Letra: error al buscar ({res})", flush=True)
            self.vp_letra.poner(None, "No se pudo buscar la letra.\n¿Hay conexión a internet?")
        elif res.tipo == "instrumental":
            self.vp_letra.poner(None, "♪\nCanción instrumental")
        elif res.tipo == "ninguna":
            self.vp_letra.poner(None, "No encontré la letra de esta canción.\n\n"
                                      "Puedes poner un archivo .lrc con el mismo nombre que la canción.")
        else:
            self.vp_letra.poner(res)
            origen = "archivo .lrc" if res.fuente == "archivo" else "LRCLIB"
            self.vp_letra_fuente.setText(f"{'sincronizada' if res.tipo == 'sincronizada' else 'sin tiempos'} · {origen}")
            self.vp_letra.posicion(self.player.position())

    # --- Cambiar de vista ---

    def maximizar(self):
        if self.vistas.currentIndex() == 1:
            return
        self._llenar_cola()
        self.vistas.setCurrentIndex(1)
        efecto = QGraphicsOpacityEffect(self.vista_completa)
        self.vista_completa.setGraphicsEffect(efecto)
        self._animacion = QPropertyAnimation(efecto, b"opacity", self)
        self._animacion.setDuration(220)
        self._animacion.setStartValue(0.0)
        self._animacion.setEndValue(1.0)
        self._animacion.setEasingCurve(QEasingCurve.OutCubic)
        self._animacion.finished.connect(lambda: self.vista_completa.setGraphicsEffect(None))
        self._animacion.start()

    def minimizar(self):
        self.vistas.setCurrentIndex(0)

    def _alternar_vista(self):
        if self.vistas.currentIndex() == 1:
            self.minimizar()
        else:
            self.maximizar()

    def _atajos(self):
        atajos = [
            ("Space", self.play_pausa), ("Ctrl+Right", lambda: self.siguiente(manual=True)),
            ("Ctrl+Left", self.anterior), ("Shift+Right", lambda: self._saltar(5000)),
            ("Shift+Left", lambda: self._saltar(-5000)), ("Ctrl+Up", lambda: self._volumen_delta(5)),
            ("Ctrl+Down", lambda: self._volumen_delta(-5)), ("Ctrl+M", self._alternar_mute),
            ("F11", self._alternar_vista), ("Escape", self.minimizar), ("Ctrl+L", self.ver_letra),
            (QKeySequence(Qt.Key_MediaTogglePlayPause), self.play_pausa),
            (QKeySequence(Qt.Key_MediaPlay), self.play_pausa),
            (QKeySequence(Qt.Key_MediaNext), lambda: self.siguiente(manual=True)),
            (QKeySequence(Qt.Key_MediaPrevious), self.anterior),
        ]
        self._lista_atajos = []
        for tecla, funcion in atajos:
            atajo = QShortcut(QKeySequence(tecla), self)
            atajo.activated.connect(funcion)
            self._lista_atajos.append(atajo)

    # --- Reproducción ---

    def reproducir_ruta(self, ruta: Path):
        # self.biblioteca es la cola de reproducción; si la canción no está, se usa toda la biblioteca
        if ruta not in self.biblioteca:
            self.biblioteca = self.pagina_bib.orden_actual()
            if ruta not in self.biblioteca:
                self.biblioteca.append(ruta)
        self._reproducir_indice(self.biblioteca.index(ruta))

    def _reproducir_indice(self, i: int):
        if not self.biblioteca:
            return
        self.indice_actual = i % len(self.biblioteca)
        ruta = self.biblioteca[self.indice_actual]
        self._en_previa = False
        self._contada = False
        self.player.setSource(QUrl.fromLocalFile(str(ruta)))
        self.player.play()

        meta = metadatos(ruta, self.carpeta)
        tamano = ruta.stat().st_size if ruta.exists() else 0
        for l in self.w_titulo:
            l.setText(meta["titulo"])
            l.update()
        for l in self.w_artista:
            l.setText(meta["artista"])
            l.update()
        self.vp_album.setText(meta["album"])
        self.vp_album.setVisible(bool(meta["album"]))
        for c in self.w_chip:
            c.setText(f"{ruta.suffix[1:].upper()} · {fmt_bytes(tamano)}")
            c.show()
        self._poner_portadas(portada_incrustada(str(ruta)))
        for o in self.w_ondas:
            o.semilla(str(ruta))
        self._marcar_actual()
        self._llenar_cola()
        self._cargar_letra(ruta, meta)
        self.setWindowTitle(f"{meta['titulo']} · {NOMBRE_APP}")

    def _poner_portadas(self, pm: QPixmap | None):
        if pm:
            self.rp_portada.setPixmap(redondear(pm, 64, 8))
            self.vp_portada.setPixmap(redondear(pm, 360, 16))
        else:
            self.rp_portada.setPixmap(icono(I_MUSICA, TENUE, 26).pixmap(26, 26))
            self.vp_portada.setPixmap(icono(I_MUSICA, TENUE, 120).pixmap(120, 120))
        self.vista_completa.poner_portada(pm) if hasattr(self, "vista_completa") else None

    def _llenar_cola(self):
        if not hasattr(self, "vp_cola"):
            return
        self.vp_cola.clear()
        n = len(self.biblioteca)
        self.vp_cola_titulo.setText("A CONTINUACIÓN · ALEATORIO" if self.aleatorio else "A CONTINUACIÓN")
        if n == 0:
            return
        inicio = self.indice_actual if self.indice_actual >= 0 else -1
        for k in range(1, min(n, 21)):
            idx = (inicio + k) % n
            if idx == self.indice_actual:
                break
            meta = metadatos(self.biblioteca[idx], self.carpeta)
            item = QListWidgetItem(icono(I_MUSICA, TENUE, 16), f"  {meta['titulo']}\n  {meta['artista']}")
            item.setData(Qt.UserRole, idx)
            item.setToolTip(f"{meta['titulo']} — {meta['artista']}")
            self.vp_cola.addItem(item)

    def play_pausa(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        elif self.player.source().isEmpty():
            if not self.biblioteca:
                self.biblioteca = self.pagina_bib.orden_actual()
            self._reproducir_indice(max(self.indice_actual, 0))
        else:
            self.player.play()

    def siguiente(self, manual=False):
        if not self.biblioteca:
            return
        if self.aleatorio and len(self.biblioteca) > 1:
            opciones = [i for i in range(len(self.biblioteca)) if i != self.indice_actual]
            self._reproducir_indice(random.choice(opciones))
        elif manual or self.repetir == 1 or self.indice_actual + 1 < len(self.biblioteca):
            self._reproducir_indice(self.indice_actual + 1)

    def anterior(self):
        # Como en cualquier reproductor: si ya avanzó, regresa al inicio de la canción
        if self.player.position() > 3000 or not self.biblioteca:
            self.player.setPosition(0)
        else:
            self._reproducir_indice(self.indice_actual - 1)

    def _saltar(self, ms: int):
        if not self.player.source().isEmpty():
            self.player.setPosition(min(max(self.player.position() + ms, 0), self.player.duration()))

    def _estado_media(self, estado):
        if estado == QMediaPlayer.EndOfMedia:
            if self._en_previa:
                return  # una vista previa no avanza a la siguiente canción
            if self.repetir == 2:
                self.player.setPosition(0)
                self.player.play()
            else:
                self.siguiente()

    def _alternar_aleatorio(self):
        self.aleatorio = not self.aleatorio
        for b in self.w_aleatorio:
            px = b.iconSize().width()
            b.setIcon(icono(I_ALEATORIO, CIAN if self.aleatorio else TENUE, px))
            b.setToolTip(f"Aleatorio: {'sí' if self.aleatorio else 'no'}")
            set_prop(b, "activo", self.aleatorio)
        self._llenar_cola()

    def _ciclar_repetir(self):
        self.repetir = (self.repetir + 1) % 3
        glifo = I_REPETIR_UNA if self.repetir == 2 else I_REPETIR
        for b in self.w_repetir:
            b.setIcon(icono(glifo, CIAN if self.repetir else TENUE, b.iconSize().width()))
            b.setToolTip(["Repetir: no", "Repetir: toda la lista", "Repetir: esta canción"][self.repetir])
            set_prop(b, "activo", self.repetir > 0)

    def _posicion(self, *_):
        pos, dur = self.player.position(), self.player.duration()
        # Cuenta como "escuchada" a los 30 s (o a la mitad si es más corta): alimenta las recomendaciones
        if not self._contada and dur and pos >= min(30000, dur / 2) and 0 <= self.indice_actual < len(self.biblioteca):
            self._contada = True
            ruta = self.biblioteca[self.indice_actual]
            c = self.db.cancion_por_ruta(ruta)
            self.db.registrar("reproduccion", ruta, c.artista if c else "", c.titulo if c else ruta.stem)
        for l in self.w_pos:
            l.setText(fmt_tiempo(pos))
        for l in self.w_dur:
            l.setText(fmt_tiempo(dur))
        for o in self.w_ondas:
            o.duracion_ms = dur
            o.poner(pos / dur if dur else 0)
        if hasattr(self, "vp_letra"):
            self.vp_letra.posicion(pos)

    def _icono_play(self, estado):
        sonando = estado == QMediaPlayer.PlayingState
        for b in self.w_play:
            b.setIcon(icono(I_PAUSA if sonando else I_PLAY, "#04121a", b.iconSize().width()))

    def _volumen(self, valor: int):
        self.salida.setVolume(valor / 100)
        for s in self.w_volumen:
            if s.value() != valor:
                s.blockSignals(True)
                s.setValue(valor)
                s.blockSignals(False)
        for l in self.w_vol_lbl:
            l.setText(f"{valor}%")
        self.ajustes.setValue("volumen", valor / 100)
        if valor and self.salida.isMuted():
            self._alternar_mute()

    def _volumen_delta(self, delta: int):
        self._volumen(min(max(self.w_volumen[0].value() + delta, 0), 100))

    def _alternar_mute(self):
        silencio = not self.salida.isMuted()
        self.salida.setMuted(silencio)
        for b in self.w_mute:
            b.setIcon(icono(I_SILENCIO if silencio else I_VOLUMEN, TENUE if silencio else TEXTO, 18))
            b.setToolTip("Quitar silencio (Ctrl+M)" if silencio else "Silenciar (Ctrl+M)")

    def _abrir_actual(self):
        if self._en_previa:
            abrir_en_explorador(Path(self.carpeta))
        elif 0 <= self.indice_actual < len(self.biblioteca):
            abrir_en_explorador(self.biblioteca[self.indice_actual])
        else:
            abrir_en_explorador(Path(self.carpeta))

    # ---------- Ventana ----------

    def showEvent(self, e):
        super().showEvent(e)
        barra_titulo_oscura(self)

    def closeEvent(self, evento):
        if self.gestor.activo:
            r = QMessageBox.question(self, NOMBRE_APP, "Hay descargas en curso. ¿Cancelarlas y salir?")
            if r != QMessageBox.Yes:
                evento.ignore()
                return
        self._cerrando = True  # el escaneo y MusicBrainz revisan esto para parar
        self.player.stop()
        self.gestor.detener()
        if self.analizador:
            self.analizador.wait(10000)
        self._guardar_ajustes()
        evento.accept()


def barra_titulo_oscura(ventana: QWidget) -> None:
    """Pinta la barra de título de Windows del mismo color que la app."""
    if sys.platform != "win32":
        return
    import ctypes
    hwnd = int(ventana.winId())
    dwm = ctypes.windll.dwmapi
    oscuro = ctypes.c_int(1)
    dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(oscuro), 4)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    color = ctypes.c_int(0x00140F0A)  # COLORREF (BGR) de #0a0f14
    dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), 4)  # DWMWA_CAPTION_COLOR (Windows 11)


def configurar_registro() -> Path:
    """Manda errores a %LOCALAPPDATA%\\WaveDrop\\wavedrop.log (el .exe no tiene consola)."""
    carpeta = Path(os.environ.get("LOCALAPPDATA", Path.home())) / NOMBRE_APP
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "wavedrop.log"
    if ruta.exists() and ruta.stat().st_size > 1_000_000:
        ruta.unlink()
    log = open(ruta, "a", encoding="utf-8", buffering=1)
    log.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} · {NOMBRE_APP} {VERSION} · {platform.platform()} =====\n")
    faulthandler.enable(log)  # cierres por errores nativos (DLLs, Qt)
    # Sin consola, sys.stdout/stderr son None y cualquier print() de una librería puede tronar
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log

    def gancho(tipo, valor, tb):
        log.write("".join(traceback.format_exception(tipo, valor, tb)))
        if QApplication.instance():
            QMessageBox.critical(None, NOMBRE_APP, f"Ocurrió un error inesperado:\n\n{valor}\n\nDetalles en:\n{ruta}")

    sys.excepthook = gancho
    threading.excepthook = lambda a: log.write("".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    qInstallMessageHandler(lambda _tipo, _ctx, msg: log.write(f"[Qt] {msg}\n"))
    return ruta


def preparar_app(app: QApplication) -> None:
    """Estilo Fusion con paleta oscura (para diálogos y menús) más la hoja de estilos."""
    app.setStyle("Fusion")
    paleta = QPalette()
    for rol, color in [
        (QPalette.Window, FONDO), (QPalette.WindowText, TEXTO), (QPalette.Base, TARJETA),
        (QPalette.AlternateBase, FONDO), (QPalette.Text, TEXTO), (QPalette.Button, TARJETA),
        (QPalette.ButtonText, TEXTO), (QPalette.Highlight, AZUL), (QPalette.HighlightedText, TEXTO),
        (QPalette.ToolTipBase, TARJETA), (QPalette.ToolTipText, TEXTO), (QPalette.PlaceholderText, TENUE),
    ]:
        paleta.setColor(rol, QColor(color))
    app.setPalette(paleta)
    app.setStyleSheet(QSS)


def main():
    configurar_registro()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DescargadorPlaylists")

    app = QApplication(sys.argv)
    app.setApplicationName(NOMBRE_APP)
    preparar_app(app)
    icono_app = recurso("icono.ico")
    if icono_app.exists():
        app.setWindowIcon(QIcon(str(icono_app)))
    ventana = Ventana()
    ventana.show()
    # WaveDrop.exe "URL" abre la app y analiza ese link
    url = next((a for a in sys.argv[1:] if a.startswith("http")), None)
    if url:
        ventana.url.setText(url)
        QTimer.singleShot(300, ventana.analizar)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
