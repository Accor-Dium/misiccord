package com.wavedrop.movil

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.support.v4.media.MediaMetadataCompat
import android.support.v4.media.session.MediaSessionCompat
import android.support.v4.media.session.PlaybackStateCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.net.URL
import java.util.concurrent.LinkedBlockingQueue
import kotlin.concurrent.thread

/** Lo que está sonando, tal como lo manda la interfaz. */
data class EstadoMedios(
    val titulo: String,
    val artista: String,
    val album: String,
    val portada: String?,
    val duracion: Double,
    val posicion: Double,
    val sonando: Boolean,
    val enJam: Boolean,
)

/** Une el servicio con la interfaz: los botones (notificación, reloj, audífonos) llegan como evento "medios". */
object Medios {
    var eventos: LinkedBlockingQueue<String>? = null

    fun avisar(accion: String, posicion: Long? = null) {
        val evento = JSONObject().put("tipo", "medios").put("accion", accion)
        if (posicion != null) evento.put("posicion", posicion / 1000.0)
        eventos?.offer(evento.toString())
    }
}

/**
 * Servicio de reproducción en primer plano con una MediaSession.
 *
 * Gracias a la sesión, Android muestra los controles en la notificación y la pantalla bloqueada, y los
 * relojes (Wear OS, Galaxy Watch) y los audífonos Bluetooth pueden pausar, cambiar de canción y ver qué suena.
 * Además evita que Android duerma la app mientras suena música (o un jam) en segundo plano.
 */
class ServicioMedios : Service() {
    companion object {
        private const val CANAL = "reproduccion"
        private const val NOTIFICACION = 7
        private var ultimo: EstadoMedios? = null
        private var sesion: MediaSessionCompat? = null
        private var portadaUrl: String? = null
        private var portada: Bitmap? = null
        private var instancia: ServicioMedios? = null

        /** Llamado por PythonPlugin cada vez que cambia lo que suena. null = ya no hay nada: se quita todo. */
        fun actualizar(contexto: Context, estado: EstadoMedios?) {
            ultimo = estado
            val intento = Intent(contexto, ServicioMedios::class.java)
            if (estado == null) {
                contexto.stopService(intento)
                return
            }
            // Si ya corre se actualiza directo: Android 12+ no deja ARRANCAR un servicio así desde segundo plano
            val activo = instancia
            if (activo != null) {
                Handler(Looper.getMainLooper()).post { activo.refrescar(estado) }
                return
            }
            try {
                ContextCompat.startForegroundService(contexto, intento)
            } catch (_: Exception) {
                // Sin permiso para arrancarlo ahora (app en segundo plano): se intenta con el siguiente cambio
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        instancia = this
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val canal = NotificationChannel(CANAL, "Reproducción", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Controles de la música que suena en Misiccord"
                setShowBadge(false)
            }
            getSystemService(NotificationManager::class.java).createNotificationChannel(canal)
        }
        sesion = MediaSessionCompat(this, "Misiccord").apply {
            setCallback(object : MediaSessionCompat.Callback() {
                override fun onPlay() = Medios.avisar("play")
                override fun onPause() = Medios.avisar("pausa")
                override fun onSkipToNext() = Medios.avisar("siguiente")
                override fun onSkipToPrevious() = Medios.avisar("anterior")
                override fun onStop() = Medios.avisar("pausa")
                override fun onSeekTo(pos: Long) = Medios.avisar("ir", pos)
            })
            setSessionActivity(abrirApp())
            isActive = true
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Botones de la notificación
        when (intent?.action) {
            "play" -> Medios.avisar("play")
            "pausa" -> Medios.avisar("pausa")
            "siguiente" -> Medios.avisar("siguiente")
            "anterior" -> Medios.avisar("anterior")
        }
        val estado = ultimo
        if (estado == null) {
            stopSelf()
            return START_NOT_STICKY
        }
        val tipo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK else 0
        aplicar(estado)
        ServiceCompat.startForeground(this, NOTIFICACION, notificacion(estado), tipo)
        cargarPortada(estado)
        return START_NOT_STICKY
    }

    fun refrescar(estado: EstadoMedios) {
        aplicar(estado)
        getSystemService(NotificationManager::class.java).notify(NOTIFICACION, notificacion(estado))
        cargarPortada(estado)
    }

    override fun onDestroy() {
        instancia = null
        sesion?.run {
            isActive = false
            release()
        }
        sesion = null
        super.onDestroy()
    }

    /** Lo que ven el reloj y la pantalla bloqueada: título, artista, portada, duración y avance. */
    private fun aplicar(e: EstadoMedios) {
        val s = sesion ?: return
        val meta = MediaMetadataCompat.Builder()
            .putString(MediaMetadataCompat.METADATA_KEY_TITLE, e.titulo)
            .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, e.artista)
            .putString(MediaMetadataCompat.METADATA_KEY_ALBUM, if (e.enJam) "Jam · Misiccord" else e.album)
            .putLong(MediaMetadataCompat.METADATA_KEY_DURATION, (e.duracion * 1000).toLong())
        if (portadaUrl == e.portada && portada != null) {
            meta.putBitmap(MediaMetadataCompat.METADATA_KEY_ALBUM_ART, portada)
        }
        s.setMetadata(meta.build())
        var acciones = PlaybackStateCompat.ACTION_PLAY or PlaybackStateCompat.ACTION_PAUSE or
            PlaybackStateCompat.ACTION_PLAY_PAUSE or PlaybackStateCompat.ACTION_SKIP_TO_NEXT
        if (!e.enJam) {
            // En un jam el anfitrión manda el tiempo: no se puede adelantar ni regresar desde fuera
            acciones = acciones or PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS or PlaybackStateCompat.ACTION_SEEK_TO
        }
        s.setPlaybackState(
            PlaybackStateCompat.Builder()
                .setActions(acciones)
                .setState(
                    if (e.sonando) PlaybackStateCompat.STATE_PLAYING else PlaybackStateCompat.STATE_PAUSED,
                    (e.posicion * 1000).toLong(), if (e.sonando) 1f else 0f, SystemClock.elapsedRealtime(),
                )
                .build(),
        )
    }

    private fun notificacion(e: EstadoMedios): Notification {
        val boton = { accion: String, icono: Int, texto: String ->
            NotificationCompat.Action(icono, texto, PendingIntent.getService(
                this, accion.hashCode(), Intent(this, ServicioMedios::class.java).setAction(accion),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        }
        val constructor = NotificationCompat.Builder(this, CANAL)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(e.titulo)
            .setContentText(e.artista)
            .setSubText(if (e.enJam) "En un jam" else null)
            .setContentIntent(abrirApp())
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setOngoing(e.sonando)
        if (portadaUrl == e.portada) constructor.setLargeIcon(portada)
        val compactos = if (e.enJam) {
            constructor.addAction(boton(if (e.sonando) "pausa" else "play",
                if (e.sonando) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play,
                if (e.sonando) "Pausar" else "Reproducir"))
            constructor.addAction(boton("siguiente", android.R.drawable.ic_media_next, "Siguiente"))
            intArrayOf(0, 1)
        } else {
            constructor.addAction(boton("anterior", android.R.drawable.ic_media_previous, "Anterior"))
            constructor.addAction(boton(if (e.sonando) "pausa" else "play",
                if (e.sonando) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play,
                if (e.sonando) "Pausar" else "Reproducir"))
            constructor.addAction(boton("siguiente", android.R.drawable.ic_media_next, "Siguiente"))
            intArrayOf(0, 1, 2)
        }
        constructor.setStyle(
            androidx.media.app.NotificationCompat.MediaStyle()
                .setMediaSession(sesion?.sessionToken)
                .setShowActionsInCompactView(*compactos),
        )
        return constructor.build()
    }

    private fun abrirApp(): PendingIntent {
        val intento = packageManager.getLaunchIntentForPackage(packageName)
            ?.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        return PendingIntent.getActivity(this, 0, intento, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    }

    /** La portada puede ser un archivo de la caché o una URL (YouTube Music o el servidor del jam). */
    private fun cargarPortada(e: EstadoMedios) {
        val origen = e.portada
        if (origen == portadaUrl) return
        portadaUrl = origen
        portada = null
        if (origen.isNullOrEmpty()) return
        thread(name = "portada-medios") {
            val imagen = try {
                val crudo = if (origen.startsWith("http")) URL(origen).openStream().use { BitmapFactory.decodeStream(it) }
                            else BitmapFactory.decodeFile(origen)
                crudo?.let { Bitmap.createScaledBitmap(it, 512, 512 * it.height / maxOf(1, it.width), true) }
            } catch (_: Exception) {
                null
            }
            if (portadaUrl != origen || imagen == null) return@thread
            portada = imagen
            val estado = ultimo ?: return@thread
            aplicar(estado)
            getSystemService(NotificationManager::class.java).notify(NOTIFICACION, notificacion(estado))
        }
    }
}
