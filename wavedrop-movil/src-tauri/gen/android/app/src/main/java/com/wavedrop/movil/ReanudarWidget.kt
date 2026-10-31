package com.wavedrop.movil

import android.app.Activity
import android.os.Bundle

/**
 * El Play del widget. Es una Activity invisible porque un servicio no puede abrir la app desde segundo plano (Android 10+)
 * y un widget no se entera de que Android o tú cerraron la app: su botón sigue apuntando a lo mismo.
 * Si la app está viva es un Play normal; si no, la abre y ella sigue sonando lo que quedó.
 */
class ReanudarWidget : Activity() {
    override fun onCreate(estado: Bundle?) {
        super.onCreate(estado)
        if (Medios.eventos != null) {
            Medios.avisar("play")
        } else {
            Medios.playAlAbrir = true
            packageManager.getLaunchIntentForPackage(packageName)?.let { startActivity(it) }
        }
        finish()
    }
}
