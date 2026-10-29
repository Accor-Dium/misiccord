"""Dibuja el ícono de Misiccord (1024x1024) en iconos/misiccord.png.

Después: npx tauri icon iconos/misiccord.png  (genera todos los tamaños para Windows y Android)
"""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath

LADO = 1024
salida = Path(__file__).resolve().parent.parent / "iconos" / "misiccord.png"
salida.parent.mkdir(exist_ok=True)

app = QGuiApplication(sys.argv)
img = QImage(LADO, LADO, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)

# Fondo: cuadro redondeado oscuro con un brillo cian en diagonal
fondo = QPainterPath()
fondo.addRoundedRect(QRectF(0, 0, LADO, LADO), 230, 230)
degradado = QLinearGradient(0, 0, LADO, LADO)
degradado.setColorAt(0, QColor("#0e1c24"))
degradado.setColorAt(1, QColor("#0a0f14"))
p.fillPath(fondo, degradado)

# Barras de onda (como el logo de la barra lateral), de cian a azul
alturas = [0.30, 0.62, 0.92, 0.70, 0.46, 0.80, 0.38]
ancho, hueco = 74, 40
total = len(alturas) * ancho + (len(alturas) - 1) * hueco
x = (LADO - total) / 2
barra = QLinearGradient(0, 200, 0, 820)
barra.setColorAt(0, QColor("#67e8f9"))
barra.setColorAt(0.5, QColor("#22d3ee"))
barra.setColorAt(1, QColor("#3b82f6"))
p.setPen(Qt.NoPen)
p.setBrush(barra)
for h in alturas:
    alto = h * 620
    p.drawRoundedRect(QRectF(x, (LADO - alto) / 2, ancho, alto), ancho / 2, ancho / 2)
    x += ancho + hueco
p.end()
img.save(str(salida))
print("ícono:", salida)
