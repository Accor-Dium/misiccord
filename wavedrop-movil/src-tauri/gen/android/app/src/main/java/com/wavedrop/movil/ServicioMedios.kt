package com.wavedrop.movil

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import android.support.v4.media.MediaBrowserCompat
import android.support.v4.media.MediaDescriptionCompat
import android.support.v4.media.MediaMetadataCompat
import android.support.v4.media.session.MediaSessionCompat
import android.support.v4.media.session.PlaybackStateCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.media.MediaBrowserServiceCompat
import org.json.JSONObject
import java.io.File
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
    val cola: List<Pair<String, String>> = emptyList(), // título y artista de la que suena y las que siguen (Android Auto)
    val indice: Int = 0, // lugar en la cola de la que suena: el id de cada una para "tocar esta" desde el coche
)

/**
 * Une el servicio con la interfaz: los botones (notificación, reloj, audífonos, Android Auto) llegan como evento "medios".
 * Sin interfaz (`eventos` null: Android Auto arrancó solo el servicio) los atiende ReproductorAuto.
 */
object Medios {
    var eventos: LinkedBlockingQueue<String>? = null
    var playAlAbrir = false // el Play del widget abrió la app: la interfaz lo pregunta al arrancar

    fun avisar(accion: String, posicion: Long? = null) {
        if (eventos == null) return ReproductorAuto.accion(accion, posicion)
        val evento = JSONObject().put("accion", accion)
        if (posicion != null) evento.put("posicion", posicion / 1000.0)
        mandar(evento)
    }

    /** Tocar algo que se eligió en Android Auto: la carpeta de api.auto y su número, o un lugar de la cola. */
    fun tocar(padre: String, n: Int) {
        if (eventos == null) return ReproductorAuto.tocar(padre, n)
        mandar(JSONObject().put("accion", "auto").put("padre", padre).put("indice", n))
    }

    fun tocarDeCola(i: Int) {
        if (eventos == null) return ReproductorAuto.aIndice(i)
        mandar(JSONObject().put("accion", "cola").put("indice", i))
    }

    private fun mandar(evento: JSONObject) {
        eventos?.offer(evento.put("tipo", "medios").toString())
    }
}

/**
 * Servicio de reproducción en primer plano con una MediaSession.
 *
 * Gracias a la sesión, Android muestra los controles en la notificación y la pantalla bloqueada, y los
 * relojes (Wear OS, Galaxy Watch) y los audífonos Bluetooth pueden pausar, cambiar de canción y ver qué suena.
 * Además evita que Android duerma la app mientras suena música (o un jam) en segundo plano.
 *
 * También es el MediaBrowserService de Android Auto: el coche lo enlaza (aunque la app esté cerrada) para ver tu música
 * (onLoadChildren → api.auto), buscar, tocar algo y ver la cola. Lo elegido lo toca la interfaz si existe; si no, ReproductorAuto.
 */
class ServicioMedios : MediaBrowserServiceCompat() {
    companion object {
        private const val CANAL = "reproduccion"
        private const val NOTIFICACION = 7
        private var ultimo: EstadoMedios? = null
        private var sesion: MediaSessionCompat? = null
        private var portadaUrl: String? = null
        private var portada: Bitmap? = null
        private var instancia: ServicioMedios? = null
        private var claveWidget: String? = null
        private var claveCola: String? = null

        // Siempre se puede: tocar algo de tu música, buscar (también por voz), elegir de la cola y play
        private const val ACCIONES = PlaybackStateCompat.ACTION_PLAY or PlaybackStateCompat.ACTION_PLAY_PAUSE or
            PlaybackStateCompat.ACTION_PLAY_FROM_MEDIA_ID or PlaybackStateCompat.ACTION_PLAY_FROM_SEARCH or
            PlaybackStateCompat.ACTION_SKIP_TO_QUEUE_ITEM

        // Android Auto (y su simulador de escritorio, que habla por la misma app) y el Asistente de Google
        private val CONFIABLES = setOf("com.google.android.projection.gearhead", "com.google.android.googlequicksearchbox",
                                       "com.google.android.carassistant")

        /** ¿Está sonando algo ahora? (MainActivity no deja que Tauri cierre la app si es así) */
        val sonando: Boolean get() = ultimo?.sonando == true

        /** El widget solo se redibuja si cambió algo que se ve (no con cada avance de la canción). */
        private fun avisarWidget(contexto: Context, estado: EstadoMedios?) {
            val imagen = if (estado != null && portadaUrl == estado.portada) portada else null
            val clave = estado?.let { "${it.titulo}|${it.artista}|${it.sonando}|${it.enJam}|${imagen?.hashCode()}" }
            if (clave == claveWidget) return
            claveWidget = clave
            WidgetMisiccord.actualizar(contexto, estado, imagen)
        }

        /** Llamado por PythonPlugin cada vez que cambia lo que suena. null = ya no hay nada: se quita todo. */
        fun actualizar(contexto: Context, estado: EstadoMedios?) {
            ultimo = estado
            val intento = Intent(contexto, ServicioMedios::class.java)
            if (estado == null) {
                contexto.stopService(intento)
                // Si Android Auto lo tiene enlazado no se destruye: hay que quitarle la notificación a mano
                instancia?.let { s -> Handler(Looper.getMainLooper()).post { s.quitar() } }
                claveWidget = null
                WidgetMisiccord.olvidar(contexto)
                return
            }
            // Si ya corre se actualiza directo: Android 12+ no deja ARRANCAR un servicio así desde segundo plano.
            // Enlazado por Android Auto existe sin estar en primer plano: ese pasa por startForegroundService (el coche
            // lo tiene enlazado, así que la app cuenta como en primer plano y Android lo deja)
            val activo = instancia
            if (activo != null && activo.enPrimerPlano) {
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

    private var enPrimerPlano = false
    private val clientes = mutableSetOf<String>() // apps de confianza que leen tu música (para darles las portadas)

    // Se desconectó el coche o los audífonos: la música no debe seguir por la bocina del teléfono
    private val ruidoso = object : BroadcastReceiver() {
        override fun onReceive(c: Context?, i: Intent?) {
            if (ultimo?.sonando == true) Medios.avisar("pausa")
        }
    }

    override fun onCreate() {
        super.onCreate()
        instancia = this
        ReproductorAuto.app = applicationContext
        ContextCompat.registerReceiver(this, ruidoso, IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY),
                                       ContextCompat.RECEIVER_NOT_EXPORTED)
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
                // Android Auto: algo de tu música ("<carpeta>#<n>", ver api.auto), una búsqueda (también por voz) o la cola
                override fun onPlayFromMediaId(id: String?, extras: Bundle?) {
                    if (id != null) Medios.tocar(id.substringBeforeLast('#'), id.substringAfterLast('#').toIntOrNull() ?: 0)
                }
                override fun onPlayFromSearch(texto: String?, extras: Bundle?) {
                    if (texto.isNullOrBlank()) Medios.avisar("play") else Medios.tocar("buscar:$texto", 0) // "pon música en Misiccord"
                }
                override fun onSkipToQueueItem(id: Long) = Medios.tocarDeCola(id.toInt())
            })
            setSessionActivity(abrirApp())
            setPlaybackState(PlaybackStateCompat.Builder().setActions(ACCIONES).setState(PlaybackStateCompat.STATE_NONE, 0, 0f).build())
            isActive = true
        }
        sessionToken = sesion!!.sessionToken // Android Auto controla esta misma sesión
    }

    /** Ya no suena nada pero Android Auto sigue enlazado: sin notificación ni nada que mostrar. */
    fun quitar() {
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        enPrimerPlano = false
        sesion?.run {
            setMetadata(null)
            setQueue(null)
            setPlaybackState(PlaybackStateCompat.Builder().setActions(ACCIONES).setState(PlaybackStateCompat.STATE_NONE, 0, 0f).build())
        }
        claveCola = null
    }

    // ---------- Android Auto: tu música ----------

    override fun onGetRoot(paquete: String, uid: Int, hints: Bundle?): BrowserRoot {
        // Solo Android Auto, el Asistente y la propia app ven tu música; los demás pueden controlar lo que suena, nada más
        val confiable = uid == Process.myUid() || uid == Process.SYSTEM_UID || paquete in CONFIABLES
        if (confiable) clientes += paquete
        return BrowserRoot(if (confiable) "raiz" else "vacio", Bundle().apply {
            putBoolean("android.media.browse.CONTENT_STYLE_SUPPORTED", true)
            putInt("android.media.browse.CONTENT_STYLE_BROWSABLE_HINT", 2) // playlists, álbumes y artistas en cuadrícula
            putInt("android.media.browse.CONTENT_STYLE_PLAYABLE_HINT", 1) // canciones en lista
            putBoolean("android.media.browse.SEARCH_SUPPORTED", true)
        })
    }

    override fun onLoadChildren(padre: String, resultado: Result<MutableList<MediaBrowserCompat.MediaItem>>) {
        if (padre == "vacio") return resultado.sendResult(mutableListOf())
        resultado.detach() // Python puede tardar (y la primera vez inicia el núcleo): fuera del hilo principal
        kotlin.concurrent.thread(name = "auto-lista") { resultado.sendResult(elementos(padre)) }
    }

    override fun onSearch(texto: String, extras: Bundle?, resultado: Result<MutableList<MediaBrowserCompat.MediaItem>>) {
        resultado.detach()
        kotlin.concurrent.thread(name = "auto-buscar") { resultado.sendResult(elementos("buscar:$texto")) }
    }

    private fun elementos(id: String): MutableList<MediaBrowserCompat.MediaItem> = try {
        val lista = Nucleo.llamar(this, "auto", JSONObject().put("id", id)).getJSONArray("elementos")
        MutableList(lista.length()) { k ->
            val e = lista.getJSONObject(k)
            val descripcion = MediaDescriptionCompat.Builder()
                .setMediaId(e.getString("id"))
                .setTitle(e.texto("titulo"))
                .setSubtitle(e.texto("subtitulo"))
                .setIconUri(icono(e.texto("portada")))
                .build()
            MediaBrowserCompat.MediaItem(descripcion, if (e.optBoolean("carpeta")) MediaBrowserCompat.MediaItem.FLAG_BROWSABLE
                                                      else MediaBrowserCompat.MediaItem.FLAG_PLAYABLE)
        }
    } catch (e: Exception) {
        mutableListOf()
    }

    /**
     * Android Auto corre en otra app: una ruta de archivo no le sirve, necesita un content:// con permiso para leerlo.
     * ponytail: las portadas de internet (canciones en línea) no salen en las listas; un ContentProvider que las baje lo resolvería.
     */
    private fun icono(ruta: String): Uri? {
        if (!ruta.startsWith("/") || !File(ruta).exists()) return null
        return try {
            FileProvider.getUriForFile(this, "$packageName.fileprovider", File(ruta)).also { uri ->
                for (c in clientes) grantUriPermission(c, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        } catch (_: IllegalArgumentException) {
            null // fuera de las carpetas de file_paths.xml
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
            // Un botón del widget después de que Android cerró la app: se dibuja como app cerrada
            WidgetMisiccord.actualizar(this, null, null)
            stopSelf()
            return START_NOT_STICKY
        }
        val tipo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK else 0
        aplicar(estado)
        ServiceCompat.startForeground(this, NOTIFICACION, notificacion(estado), tipo)
        enPrimerPlano = true
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
        unregisterReceiver(ruidoso)
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
        avisarWidget(this, e)
        var acciones = ACCIONES or PlaybackStateCompat.ACTION_PAUSE or PlaybackStateCompat.ACTION_SKIP_TO_NEXT
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
                .setActiveQueueItemId(e.indice.toLong())
                .build(),
        )
        // La cola que ve Android Auto: solo si cambió (con cada avance sería mandar 30 canciones por nada)
        val clave = "${e.indice}|${e.cola}"
        if (clave != claveCola) {
            claveCola = clave
            s.setQueue(e.cola.mapIndexed { k, (titulo, artista) ->
                MediaSessionCompat.QueueItem(MediaDescriptionCompat.Builder().setMediaId("cola#${e.indice + k}")
                    .setTitle(titulo).setSubtitle(artista).build(), (e.indice + k).toLong())
            }.ifEmpty { null })
        }
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
