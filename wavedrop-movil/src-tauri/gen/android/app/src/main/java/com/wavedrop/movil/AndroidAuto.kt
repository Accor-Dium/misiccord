package com.wavedrop.movil

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import androidx.media.AudioAttributesCompat
import androidx.media.AudioFocusRequestCompat
import androidx.media.AudioManagerCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale
import java.util.concurrent.LinkedBlockingQueue
import kotlin.concurrent.thread

/** optString da "null" (el texto) si el valor es null en el JSON. */
fun JSONObject.texto(clave: String): String = if (isNull(clave)) "" else optString(clave)

/**
 * Python (Chaquopy) sin depender de la interfaz. PythonPlugin lo usa para todo; Android Auto, para pedir listas y canciones
 * aunque la app esté cerrada (Android Auto puede arrancar solo el servicio, sin la Activity ni la WebView).
 */
object Nucleo {
    private var iniciadoAqui = false

    fun python(app: Context): Python {
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))
        return Python.getInstance()
    }

    /** Carpetas que usa Python: datos (base de datos), música, caché, dónde está qjs y los almacenamientos. */
    fun contexto(app: Context): String {
        // Raíz de cada almacenamiento (interno y tarjetas SD): getExternalFilesDirs da .../Android/data/<app>/files en cada uno
        val volumenes = JSONArray()
        for (dir in app.getExternalFilesDirs(null)) {
            val ruta = dir?.absolutePath ?: continue
            val corte = ruta.indexOf("/Android/data/")
            if (corte > 0) volumenes.put(ruta.substring(0, corte))
        }
        return JSONObject()
            .put("datos", app.filesDir.absolutePath + "/wavedrop")
            .put("musica", app.getExternalFilesDir(android.os.Environment.DIRECTORY_MUSIC)?.absolutePath ?: app.filesDir.absolutePath + "/musica")
            .put("cache", app.cacheDir.absolutePath)
            .put("libs", app.applicationInfo.nativeLibraryDir)
            .put("volumenes", volumenes)
            .toString()
    }

    /**
     * Una función de api.py desde Kotlin (no corre en el hilo principal: puede tardar). Si la interfaz no ha arrancado en
     * este proceso, primero se inicia el núcleo como lo haría ella, en el idioma del teléfono; cuando ella arranque lo
     * vuelve a iniciar con el suyo, igual que siempre.
     */
    fun llamar(contexto: Context, funcion: String, datos: JSONObject = JSONObject()): JSONObject {
        val app = contexto.applicationContext
        val api = python(app).getModule("wavedrop.api")
        synchronized(this) {
            if (Medios.eventos == null && !iniciadoAqui) {
                val idioma = if (Locale.getDefault().language == "es") "es" else "en"
                // Los avisos de Python (escaneo, descargas) no tienen a quién llegar: cola corta que nadie lee
                api.callAttr("despachar", "iniciar", JSONObject().put("idioma", idioma).toString(), contexto(app),
                             Emisor(LinkedBlockingQueue(20), app))
                iniciadoAqui = true
            }
        }
        val r = JSONObject(api.callAttr("despachar", funcion, datos.toString()).toString())
        if (!r.optBoolean("ok")) throw RuntimeException(r.texto("error"))
        return r
    }
}

/**
 * Reproductor de Android Auto para cuando no hay interfaz (la app cerrada): la música de Misiccord suena en la WebView y
 * sin ella nadie tocaría. Toca las mismas listas (api.auto) con MediaPlayer: los archivos tal cual y lo de YouTube Music por
 * el flujo local de Python (api.previa), como la app. Lo que suena se ve igual que siempre (ServicioMedios.actualizar).
 * Al abrir la app le entrega todo (`entregar`): guarda la sesión como la guarda la interfaz y ella sigue desde ahí.
 * Todo menos lo que llama a Python corre en el hilo principal.
 */
object ReproductorAuto {
    lateinit var app: Context
    private val principal = Handler(Looper.getMainLooper())
    private var cola = listOf<JSONObject>()
    private var origen = ""
    private var indice = -1
    private var mp: MediaPlayer? = null
    private var listo = false // mp ya se puede tocar
    private var quiereSonar = false
    private var pausadaPorFoco = false // una llamada o el navegador del coche hablando: sigue al terminar
    private var pedido = 0 // cada canción nueva invalida la que se estaba preparando
    private var fallos = 0 // seguidas que no se pudieron oír: con la cola entera se detiene
    private var foco: AudioFocusRequestCompat? = null

    val activo get() = indice >= 0

    /** Los botones (Android Auto, notificación, reloj, audífonos) cuando no hay interfaz. */
    fun accion(nombre: String, posicionMs: Long?) {
        when (nombre) {
            "play" -> play()
            "pausa" -> pausa()
            "siguiente" -> siguiente()
            "anterior" -> anterior()
            "ir" -> if (listo && posicionMs != null) {
                mp?.seekTo(posicionMs.toInt())
                publicar()
            }
        }
    }

    /** Toca la carpeta `padre` de api.auto desde la canción `n`. */
    fun tocar(padre: String, n: Int) {
        thread(name = "auto-tocar") {
            val r = try { Nucleo.llamar(app, "auto", JSONObject().put("id", padre)) } catch (_: Exception) { return@thread }
            val elementos = r.getJSONArray("elementos")
            val lista = List(elementos.length()) { elementos.getJSONObject(it).getJSONObject("cancion") }
            if (lista.isNotEmpty()) principal.post { empezar(lista, n.coerceIn(0, lista.size - 1), r.texto("titulo"), 0) }
        }
    }

    fun aIndice(i: Int) {
        if (i in cola.indices) cargar(i)
    }

    fun play() {
        pausadaPorFoco = false
        if (!activo) return retomar()
        quiereSonar = true
        if (listo && pedirFoco()) mp?.start()
        publicar()
    }

    fun pausa() {
        quiereSonar = false
        if (listo) mp?.pause()
        publicar()
        guardar()
    }

    fun siguiente() {
        if (!activo) return
        if (indice + 1 < cola.size) cargar(indice + 1) else pausa() // se acabó la cola: se queda en la última
    }

    fun anterior() {
        if (!activo) return
        if (listo && (mp?.currentPosition ?: 0) > 3000) {
            mp?.seekTo(0)
            publicar()
        } else {
            cargar(maxOf(0, indice - 1))
        }
    }

    /** La app se abrió: la interfaz toma lo que suena. true si sonaba (para que ella siga sonando). */
    fun entregar(): Boolean {
        if (!activo) return false
        val sonaba = quiereSonar
        val datos = sesion()
        pedido++
        soltarMp()
        foco?.let { AudioManagerCompat.abandonAudioFocusRequest(app.getSystemService(AudioManager::class.java), it) }
        indice = -1
        cola = emptyList()
        try {
            Nucleo.llamar(app, "guardar_sesion", datos)
        } catch (_: Exception) {
        }
        return sonaba
    }

    /** Play sin nada en la cola (recién conectado al coche): lo que sonaba la última vez, donde se quedó. */
    private fun retomar() {
        thread(name = "auto-retomar") {
            val s = try { Nucleo.llamar(app, "sesion_guardada") } catch (_: Exception) { return@thread }
            val c = s.optJSONArray("cola") ?: return@thread
            val lista = List(c.length()) { c.getJSONObject(it) }
            if (lista.isEmpty()) return@thread
            val i = s.optInt("indice").coerceIn(0, lista.size - 1)
            val pos = s.optDouble("posicion", 0.0)
            val desde = if (pos < s.optDouble("duracion", 0.0) - 3) (pos * 1000).toInt() else 0
            principal.post { if (!activo) empezar(lista, i, s.texto("origen"), desde) }
        }
    }

    private fun empezar(lista: List<JSONObject>, i: Int, titulo: String, desdeMs: Int) {
        cola = lista
        origen = titulo
        fallos = 0
        cargar(i, desdeMs)
    }

    private fun cargar(i: Int, desdeMs: Int = 0) {
        indice = i
        quiereSonar = true
        val yo = ++pedido
        soltarMp()
        publicar()
        val c = cola[i]
        thread(name = "auto-fuente") {
            // El archivo, o la caché / el flujo local de una de YouTube Music (igual que fuenteDe en reproductor.svelte.js)
            val fuente = c.texto("ruta").ifEmpty {
                try {
                    Nucleo.llamar(app, "previa", JSONObject().put("id", c.texto("id"))).let { it.texto("ruta").ifEmpty { it.texto("url") } }
                } catch (_: Exception) {
                    ""
                }
            }
            principal.post { if (yo == pedido) preparar(fuente, yo, desdeMs) }
            try {
                // Para el historial, las recomendaciones y las estadísticas, como al tocarla en la app
                Nucleo.llamar(app, "reproduccion", JSONObject().put("ruta", c.opt("ruta")).put("id", c.opt("id"))
                    .put("titulo", c.texto("titulo")).put("artista", c.texto("artista")).put("duracion", c.opt("duracion"))
                    .put("portada", c.opt("portada")))
            } catch (_: Exception) {
            }
        }
        guardar()
    }

    private fun preparar(fuente: String, yo: Int, desdeMs: Int) {
        if (fuente.isEmpty()) return saltarPorError()
        val m = MediaPlayer()
        mp = m
        m.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
        m.setWakeMode(app, PowerManager.PARTIAL_WAKE_LOCK)
        m.setOnPreparedListener {
            if (yo != pedido) return@setOnPreparedListener
            listo = true
            fallos = 0
            if (desdeMs > 0) it.seekTo(desdeMs)
            if (quiereSonar && pedirFoco()) it.start()
            publicar()
        }
        m.setOnCompletionListener { if (yo == pedido) siguiente() }
        m.setOnErrorListener { _, _, _ ->
            if (yo == pedido) saltarPorError()
            true
        }
        try {
            m.setDataSource(fuente)
            m.prepareAsync()
        } catch (_: Exception) {
            saltarPorError()
        }
    }

    /** No se pudo oír (sin internet, archivo borrado): la siguiente, sin dar vueltas para siempre. */
    private fun saltarPorError() {
        soltarMp()
        if (++fallos < cola.size && indice + 1 < cola.size) cargar(indice + 1) else pausa()
    }

    private fun soltarMp() {
        listo = false
        mp?.release()
        mp = null
    }

    private val alCambiarFoco = AudioManager.OnAudioFocusChangeListener { cambio ->
        when (cambio) {
            AudioManager.AUDIOFOCUS_LOSS -> pausa()
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> if (quiereSonar) {
                pausa()
                pausadaPorFoco = true
            }
            AudioManager.AUDIOFOCUS_GAIN -> if (pausadaPorFoco) play()
            // LOSS_TRANSIENT_CAN_DUCK: Android 8+ baja el volumen solo (el navegador del coche hablando)
        }
    }

    private fun pedirFoco(): Boolean {
        val f = foco ?: AudioFocusRequestCompat.Builder(AudioManagerCompat.AUDIOFOCUS_GAIN)
            .setAudioAttributes(AudioAttributesCompat.Builder().setUsage(AudioAttributesCompat.USAGE_MEDIA)
                .setContentType(AudioAttributesCompat.CONTENT_TYPE_MUSIC).build())
            .setOnAudioFocusChangeListener(alCambiarFoco)
            .build().also { foco = it }
        return AudioManagerCompat.requestAudioFocus(app.getSystemService(AudioManager::class.java), f) ==
            AudioManager.AUDIOFOCUS_REQUEST_GRANTED
    }

    private fun posicion(): Double = if (listo) (mp?.currentPosition ?: 0) / 1000.0 else 0.0

    private fun duracion(c: JSONObject): Double =
        if (listo && (mp?.duration ?: 0) > 0) mp!!.duration / 1000.0 else c.optDouble("duracion", 0.0).takeIf { !it.isNaN() } ?: 0.0

    /** Lo mismo que guarda la interfaz (guardarCola en reproductor.svelte.js): así ella sigue donde se quedó esto. */
    private fun sesion(): JSONObject = JSONObject()
        .put("indice", indice).put("posicion", posicion()).put("duracion", cola.getOrNull(indice)?.let { duracion(it) } ?: 0.0)
        .put("sesion", JSONObject().put("cola", JSONArray(cola)).put("origen", origen).put("aleatorio", false).put("repetir", 0))

    private fun guardar() {
        if (!activo) return
        val datos = sesion()
        thread(name = "auto-sesion") {
            try {
                Nucleo.llamar(app, "guardar_sesion", datos)
            } catch (_: Exception) {
            }
        }
    }

    private fun publicar() {
        val c = cola.getOrNull(indice) ?: return
        val siguientes = cola.subList(indice, minOf(cola.size, indice + 30)).map { it.texto("titulo") to it.texto("artista") }
        ServicioMedios.actualizar(app, EstadoMedios(
            c.texto("titulo"), c.texto("artista"), c.texto("album"), c.texto("portada").ifEmpty { null }, duracion(c),
            posicion(), listo && mp?.isPlaying == true, false, siguientes, indice))
    }
}
