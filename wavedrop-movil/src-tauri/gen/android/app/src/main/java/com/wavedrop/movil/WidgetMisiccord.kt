package com.wavedrop.movil

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.widget.RemoteViews
import java.io.File

/**
 * Widget de la pantalla de inicio: abre Misiccord con un toque y muestra la canción con anterior / reproducir-pausar /
 * siguiente. La última canción se recuerda aquí: con la app cerrada se sigue viendo y su Play la abre y sigue sonando.
 *
 * Los botones van a ServicioMedios (los mismos de la notificación), menos Play, que va a ReanudarWidget. Con la app
 * cerrada anterior y siguiente solo abren la app (Python y la interfaz viven en ella).
 */
class WidgetMisiccord : AppWidgetProvider() {
    companion object {
        private const val PREFERENCIAS = "widget"
        private var estado: EstadoMedios? = null
        private var portada: Bitmap? = null

        /** Lo llama ServicioMedios cada vez que cambia lo que suena (null = la app no tiene nada vivo que mostrar). */
        fun actualizar(contexto: Context, nuevo: EstadoMedios?, imagen: Bitmap?) {
            estado = nuevo
            portada = imagen
            if (nuevo != null && !nuevo.enJam) recordar(contexto, nuevo, imagen)
            val gestor = AppWidgetManager.getInstance(contexto)
            val ids = gestor.getAppWidgetIds(ComponentName(contexto, WidgetMisiccord::class.java))
            if (ids.isNotEmpty()) gestor.updateAppWidget(ids, vistas(contexto))
        }

        /** Ya no hay canción (se borró o la sesión quedó vacía): de vuelta a "Toca para abrir". */
        fun olvidar(contexto: Context) {
            contexto.getSharedPreferences(PREFERENCIAS, Context.MODE_PRIVATE).edit().clear().apply()
            archivoPortada(contexto).delete()
            actualizar(contexto, null, null)
        }

        private fun archivoPortada(contexto: Context) = File(contexto.filesDir, "widget_portada.jpg")

        private fun recordar(contexto: Context, e: EstadoMedios, imagen: Bitmap?) {
            contexto.getSharedPreferences(PREFERENCIAS, Context.MODE_PRIVATE).edit()
                .putString("titulo", e.titulo).putString("artista", e.artista).apply()
            val archivo = archivoPortada(contexto)
            // Sin imagen es que la de esta canción sigue cargando: la anterior ya no le corresponde
            if (imagen == null) archivo.delete()
            else archivo.outputStream().use { imagen.compress(Bitmap.CompressFormat.JPEG, 85, it) }
        }

        private fun recordada(contexto: Context): EstadoMedios? {
            val p = contexto.getSharedPreferences(PREFERENCIAS, Context.MODE_PRIVATE)
            val titulo = p.getString("titulo", null) ?: return null
            return EstadoMedios(titulo, p.getString("artista", "") ?: "", "", null, 0.0, 0.0, sonando = false, enJam = false)
        }

        private fun vistas(contexto: Context): RemoteViews {
            val v = RemoteViews(contexto.packageName, R.layout.widget_misiccord)
            val abrir = abrirApp(contexto)
            v.setOnClickPendingIntent(R.id.widget_raiz, abrir)
            val viva = estado != null
            val e = estado ?: recordada(contexto)
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
            val imagen = if (viva) portada else BitmapFactory.decodeFile(archivoPortada(contexto).path)
            if (imagen != null) v.setImageViewBitmap(R.id.widget_portada, imagen)
            else v.setImageViewResource(R.id.widget_portada, R.mipmap.ic_launcher)
            v.setImageViewResource(R.id.widget_play, if (e.sonando) R.drawable.widget_pausa else R.drawable.widget_play)
            v.setContentDescription(R.id.widget_play,
                contexto.getString(if (e.sonando) R.string.widget_pausar else R.string.widget_reproducir))
            v.setOnClickPendingIntent(R.id.widget_play, if (e.sonando) boton(contexto, "pausa") else reanudar(contexto))
            v.setOnClickPendingIntent(R.id.widget_siguiente, if (viva) boton(contexto, "siguiente") else abrir)
            v.setBoolean(R.id.widget_siguiente, "setEnabled", viva)
            v.setInt(R.id.widget_siguiente, "setImageAlpha", if (viva) 255 else 90)
            // En un jam no se regresa de canción (igual que en la notificación)
            val regresa = viva && !e.enJam
            v.setBoolean(R.id.widget_anterior, "setEnabled", regresa)
            v.setInt(R.id.widget_anterior, "setImageAlpha", if (regresa) 255 else 90)
            v.setOnClickPendingIntent(R.id.widget_anterior, if (regresa) boton(contexto, "anterior") else abrir)
            return v
        }

        private fun reanudar(contexto: Context): PendingIntent = PendingIntent.getActivity(
            contexto, 2, Intent(contexto, ReanudarWidget::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

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
