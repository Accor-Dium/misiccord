package com.wavedrop.movil

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat

/** Resumen de lo que Python está haciendo en segundo plano (evento "fondo": descargas, actualización, jam...). */
data class ResumenTareas(
    val activas: Int,
    val titulo: String,
    val texto: String,
    val pct: Int, // -1 = no se sabe (barra sin avance fijo)
    val fin: String, // mensaje al terminar todo ("3 canciones descargadas"); vacío si no hay
)

/**
 * Servicio en primer plano para trabajos largos: descargas, la actualización, leer una carpeta de música, un jam abierto.
 *
 * Sin él, Android congela la app poco después de apagar la pantalla o cambiar de app (ServicioMedios solo la
 * mantiene viva mientras suena música). Muestra una notificación con el avance y, mientras trabaja, mantiene
 * el procesador despierto. El resumen lo calcula Python y llega desde PythonPlugin.Emisor, sin pasar por la
 * interfaz (que Android pausa con la pantalla apagada).
 */
class ServicioTareas : Service() {
    companion object {
        private const val CANAL = "tareas"
        private const val NOTIFICACION = 8
        private const val AVISO_FIN = 9
        private var ultimo: ResumenTareas? = null
        private var instancia: ServicioTareas? = null

        private fun crearCanal(contexto: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val canal = NotificationChannel(CANAL, "Descargas y tareas", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Avance de descargas, actualizaciones y jams mientras la app está en segundo plano"
                    setShowBadge(false)
                }
                contexto.getSystemService(NotificationManager::class.java).createNotificationChannel(canal)
            }
        }

        /** Llamado por Python (vía PythonPlugin) cada vez que cambia el resumen. */
        fun actualizar(contexto: Context, resumen: ResumenTareas) {
            ultimo = resumen
            val intento = Intent(contexto, ServicioTareas::class.java)
            if (resumen.activas == 0) {
                instancia = null // ya no se le manda nada: una notificación nueva se quedaría huérfana
                contexto.stopService(intento)
                if (resumen.fin.isNotEmpty()) avisarFin(contexto, resumen.fin)
                return
            }
            // Si ya corre se actualiza directo: Android 12+ no deja ARRANCAR un servicio así desde segundo plano
            val activo = instancia
            if (activo != null) {
                Handler(Looper.getMainLooper()).post { activo.refrescar(resumen) }
                return
            }
            try {
                ContextCompat.startForegroundService(contexto, intento)
            } catch (_: Exception) {
                // Sin permiso para arrancarlo ahora (la app ya estaba en segundo plano): Python sigue, solo sin servicio
            }
        }

        /** Aviso normal (se puede quitar) cuando termina todo: toca para abrir la app. */
        private fun avisarFin(contexto: Context, mensaje: String) {
            crearCanal(contexto)
            val intento = contexto.packageManager.getLaunchIntentForPackage(contexto.packageName)
                ?.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            val abrir = PendingIntent.getActivity(contexto, 1, intento, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            val aviso = NotificationCompat.Builder(contexto, CANAL)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle("Misiccord")
                .setContentText(mensaje)
                .setContentIntent(abrir)
                .setAutoCancel(true)
                .setSilent(true)
                .build()
            contexto.getSystemService(NotificationManager::class.java).notify(AVISO_FIN, aviso)
        }
    }

    private var bloqueo: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        instancia = this
        crearCanal(this)
        // Con la pantalla apagada el procesador se duerme y las descargas se frenan; tope de 3 h por si algo falla
        bloqueo = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "misiccord:tareas")
            .apply {
                setReferenceCounted(false)
                acquire(3 * 60 * 60 * 1000L)
            }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val resumen = ultimo ?: ResumenTareas(0, "Misiccord", "", -1, "")
        val tipo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC else 0
        // Siempre se llama a startForeground (Android lo exige en los 5 s siguientes), aunque ya no quede nada
        ServiceCompat.startForeground(this, NOTIFICACION, notificacion(resumen), tipo)
        if (resumen.activas == 0) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_NOT_STICKY
    }

    fun refrescar(resumen: ResumenTareas) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICACION, notificacion(resumen))
    }

    override fun onDestroy() {
        if (instancia === this) instancia = null
        bloqueo?.takeIf { it.isHeld }?.release()
        bloqueo = null
        super.onDestroy()
    }

    private fun notificacion(r: ResumenTareas): Notification {
        val abrir = PendingIntent.getActivity(
            this, 0,
            packageManager.getLaunchIntentForPackage(packageName)
                ?.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return NotificationCompat.Builder(this, CANAL)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(r.titulo.ifEmpty { "Misiccord" })
            .setContentText(r.texto)
            .setContentIntent(abrir)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setProgress(100, maxOf(r.pct, 0), r.pct < 0)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
    }
}
