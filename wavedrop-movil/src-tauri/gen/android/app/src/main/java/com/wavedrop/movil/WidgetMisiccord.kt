package com.wavedrop.movil

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.widget.RemoteViews

/**
 * Widget de la pantalla de inicio: abre Misiccord con un toque y, mientras suena algo, muestra la canción
 * con anterior / reproducir-pausar / siguiente.
 *
 * Los botones van a ServicioMedios (los mismos de la notificación). Si no suena nada, la app puede no estar
 * corriendo (Python y la interfaz viven en ella), así que ahí cualquier toque solo abre la app.
 */
class WidgetMisiccord : AppWidgetProvider() {
    companion object {
        private var estado: EstadoMedios? = null
        private var portada: Bitmap? = null

        /** Lo llama ServicioMedios cada vez que cambia lo que suena (null = ya no suena nada). */
        fun actualizar(contexto: Context, nuevo: EstadoMedios?, imagen: Bitmap?) {
            estado = nuevo
            portada = imagen
            val gestor = AppWidgetManager.getInstance(contexto)
            val ids = gestor.getAppWidgetIds(ComponentName(contexto, WidgetMisiccord::class.java))
            if (ids.isNotEmpty()) gestor.updateAppWidget(ids, vistas(contexto))
        }

        private fun vistas(contexto: Context): RemoteViews {
            val v = RemoteViews(contexto.packageName, R.layout.widget_misiccord)
            val abrir = abrirApp(contexto)
            v.setOnClickPendingIntent(R.id.widget_raiz, abrir)
            val e = estado
            if (e == null) {
                v.setTextViewText(R.id.widget_titulo, contexto.getString(R.string.app_name))
                v.setTextViewText(R.id.widget_artista, contexto.getString(R.string.widget_abrir))
                v.setImageViewResource(R.id.widget_portada, R.mipmap.ic_launcher)
                v.setImageViewResource(R.id.widget_play, R.drawable.widget_play)
                v.setContentDescription(R.id.widget_play, contexto.getString(R.string.widget_abrir))
                for (id in intArrayOf(R.id.widget_play, R.id.widget_anterior, R.id.widget_siguiente)) {
                    v.setOnClickPendingIntent(id, abrir)
                }
                v.setBoolean(R.id.widget_anterior, "setEnabled", false)
                v.setBoolean(R.id.widget_siguiente, "setEnabled", false)
                v.setInt(R.id.widget_anterior, "setImageAlpha", 90)
                v.setInt(R.id.widget_siguiente, "setImageAlpha", 90)
                return v
            }
            v.setTextViewText(R.id.widget_titulo, e.titulo)
            v.setTextViewText(R.id.widget_artista, if (e.enJam) "${e.artista} · Jam" else e.artista)
            val imagen = portada
            if (imagen != null) v.setImageViewBitmap(R.id.widget_portada, imagen)
            else v.setImageViewResource(R.id.widget_portada, R.mipmap.ic_launcher)
            v.setImageViewResource(R.id.widget_play, if (e.sonando) R.drawable.widget_pausa else R.drawable.widget_play)
            v.setContentDescription(R.id.widget_play,
                contexto.getString(if (e.sonando) R.string.widget_pausar else R.string.widget_reproducir))
            v.setOnClickPendingIntent(R.id.widget_play, boton(contexto, if (e.sonando) "pausa" else "play"))
            v.setOnClickPendingIntent(R.id.widget_siguiente, boton(contexto, "siguiente"))
            v.setBoolean(R.id.widget_siguiente, "setEnabled", true)
            v.setInt(R.id.widget_siguiente, "setImageAlpha", 255)
            // En un jam no se regresa de canción (igual que en la notificación)
            v.setBoolean(R.id.widget_anterior, "setEnabled", !e.enJam)
            v.setInt(R.id.widget_anterior, "setImageAlpha", if (e.enJam) 90 else 255)
            v.setOnClickPendingIntent(R.id.widget_anterior, if (e.enJam) abrir else boton(contexto, "anterior"))
            return v
        }

        private fun boton(contexto: Context, accion: String): PendingIntent = PendingIntent.getService(
            contexto, ("widget-$accion").hashCode(), Intent(contexto, ServicioMedios::class.java).setAction(accion),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        private fun abrirApp(contexto: Context): PendingIntent {
            val intento = contexto.packageManager.getLaunchIntentForPackage(contexto.packageName)
                ?.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            return PendingIntent.getActivity(contexto, 1, intento, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        }
    }

    override fun onUpdate(contexto: Context, gestor: AppWidgetManager, ids: IntArray) {
        gestor.updateAppWidget(ids, vistas(contexto))
    }
}
