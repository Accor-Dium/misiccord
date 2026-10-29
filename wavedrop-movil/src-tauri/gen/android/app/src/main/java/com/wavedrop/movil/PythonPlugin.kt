package com.wavedrop.movil

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.PowerManager
import android.provider.Settings
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import java.io.File
import app.tauri.annotation.Command
import app.tauri.annotation.InvokeArg
import app.tauri.annotation.TauriPlugin
import app.tauri.plugin.Invoke
import app.tauri.plugin.JSObject
import app.tauri.plugin.Plugin
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

@InvokeArg
class Llamada {
    lateinit var funcion: String
    var datos: String = "{}"
}

@InvokeArg
class Pedido {
    var pedir: Boolean = false
}

@InvokeArg
class Apk {
    lateinit var ruta: String
}

@InvokeArg
class ArgsMedios {
    var hay: Boolean = false
    var titulo: String = ""
    var artista: String = ""
    var album: String = ""
    var portada: String? = null
    var duracion: Double = 0.0
    var posicion: Double = 0.0
    var sonando: Boolean = false
    var enJam: Boolean = false
}

@InvokeArg
class ArgsCompartir {
    var rutas: Array<String> = arrayOf()
    var texto: String? = null  // un link (canciones que no tienes descargadas)
    var titulo: String = ""    // título del menú de compartir
}

@InvokeArg
class ArgsFondo {
    var pedir: String = "" // "notificaciones" | "bateria" | "" (solo consultar)
}

/** Python llama a emitir(json) para avisar algo (progreso de descargas, recomendaciones listas...). */
class Emisor(private val cola: LinkedBlockingQueue<String>, private val contexto: Context) {
    fun emitir(texto: String) {
        cola.offer(texto)
        // El resumen del trabajo en segundo plano va directo al servicio, sin esperar a la interfaz
        // (con la pantalla apagada Android la pausa y la notificación se quedaría vieja)
        if (texto.startsWith("{\"tipo\": \"fondo\"")) {
            try {
                val j = JSONObject(texto)
                ServicioTareas.actualizar(contexto, ResumenTareas(
                    j.getInt("activas"), j.optString("titulo"), j.optString("texto"), j.optInt("pct", -1), j.optString("fin")))
            } catch (_: Exception) {
            }
        }
    }
}

/**
 * Puente entre Tauri y Python (Chaquopy).
 * - llamar: ejecuta wavedrop.api.despachar(funcion, datos, contexto, emisor) en un hilo aparte.
 * - esperarEvento: Rust lo llama en bucle para recoger los avisos de Python y mandarlos a la interfaz.
 */
@TauriPlugin
class PythonPlugin(private val activity: Activity) : Plugin(activity) {
    private val eventos = LinkedBlockingQueue<String>().also { Medios.eventos = it }
    private val emisor = Emisor(eventos, activity.applicationContext)

    private fun python(): Python {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(activity.applicationContext))
        }
        return Python.getInstance()
    }

    /** Carpetas que usa Python: datos (base de datos), música, caché, dónde está qjs y los almacenamientos. */
    private fun contexto(): String {
        val app = activity.applicationContext
        // Raíz de cada almacenamiento (interno y tarjetas SD): getExternalFilesDirs da .../Android/data/<app>/files en cada uno
        val volumenes = JSONArray()
        for (dir in app.getExternalFilesDirs(null)) {
            val ruta = dir?.absolutePath ?: continue
            val corte = ruta.indexOf("/Android/data/")
            if (corte > 0) volumenes.put(ruta.substring(0, corte))
        }
        return JSONObject()
            .put("datos", app.filesDir.absolutePath + "/wavedrop")
            .put("musica", app.getExternalFilesDir(Environment.DIRECTORY_MUSIC)?.absolutePath ?: app.filesDir.absolutePath + "/musica")
            .put("cache", app.cacheDir.absolutePath)
            .put("libs", app.applicationInfo.nativeLibraryDir)
            .put("volumenes", volumenes)
            .toString()
    }

    @Command
    fun llamar(invoke: Invoke) {
        val args = invoke.parseArgs(Llamada::class.java)
        thread(name = "python-${args.funcion}") {
            try {
                val resultado = python().getModule("wavedrop.api")
                    .callAttr("despachar", args.funcion, args.datos, contexto(), emisor)
                    .toString()
                invoke.resolve(JSObject().put("resultado", resultado))
            } catch (e: Throwable) {
                invoke.reject(e.toString())
            }
        }
    }

    /** ¿Puede escribir en carpetas públicas (Música)? Con pedir=true abre la pantalla para dar el permiso. */
    @Command
    fun permisoArchivos(invoke: Invoke) {
        val args = invoke.parseArgs(Pedido::class.java)
        val concedido = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            ContextCompat.checkSelfPermission(activity, Manifest.permission.WRITE_EXTERNAL_STORAGE) ==
                PackageManager.PERMISSION_GRANTED
        }
        if (!concedido && args.pedir) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                // Android 11+: "Acceso a todos los archivos" solo se activa desde Ajustes del sistema
                val intento = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                                     Uri.parse("package:${activity.packageName}"))
                try {
                    activity.startActivity(intento)
                } catch (e: Exception) {
                    activity.startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
                }
            } else {
                ActivityCompat.requestPermissions(activity, arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE), 41)
            }
        }
        invoke.resolve(JSObject().put("concedido", concedido))
    }

    /** Abre el instalador de Android con el APK de la actualización (el usuario confirma). */
    @Command
    fun instalarApk(invoke: Invoke) {
        val args = invoke.parseArgs(Apk::class.java)
        val app = activity.applicationContext
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !app.packageManager.canRequestPackageInstalls()) {
            // Primero hay que permitir que Misiccord instale apps (solo la primera vez)
            activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                          Uri.parse("package:${activity.packageName}")))
            invoke.resolve(JSObject().put("abierto", false).put("falta_permiso", true))
            return
        }
        val uri = FileProvider.getUriForFile(app, "${app.packageName}.fileprovider", File(args.ruta))
        val intento = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        activity.startActivity(intento)
        invoke.resolve(JSObject().put("abierto", true))
    }

    /**
     * Menú "Compartir" del sistema (WhatsApp, Telegram, Drive, Bluetooth, guardar en una USB con Archivos…)
     * con los archivos de las canciones, o con un texto/link si no hay archivos.
     */
    @Command
    fun compartir(invoke: Invoke) {
        val a = invoke.parseArgs(ArgsCompartir::class.java)
        val app = activity.applicationContext
        val uris = ArrayList<Uri>()
        for (ruta in a.rutas) {
            val archivo = File(ruta)
            if (!archivo.exists()) continue
            try {
                uris.add(FileProvider.getUriForFile(app, "${app.packageName}.fileprovider", archivo))
            } catch (e: IllegalArgumentException) {
                // fuera de las rutas de file_paths.xml: no se puede compartir ese
            }
        }
        val intento = when {
            uris.size == 1 -> Intent(Intent.ACTION_SEND).apply {
                type = tipoDe(a.rutas.first { File(it).exists() })
                putExtra(Intent.EXTRA_STREAM, uris[0])
            }
            uris.size > 1 -> Intent(Intent.ACTION_SEND_MULTIPLE).apply {
                type = if (a.rutas.all { tipoDe(it).startsWith("audio/") }) "audio/*" else "*/*"
                putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris)
            }
            !a.texto.isNullOrEmpty() -> Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, a.texto)
            }
            else -> {
                invoke.reject("No hay nada que compartir")
                return
            }
        }
        if (uris.isNotEmpty()) {
            // Sin ClipData, algunas apps (WhatsApp) no reciben el permiso de lectura de todos los archivos
            val clip = android.content.ClipData.newUri(app.contentResolver, a.titulo, uris[0])
            for (u in uris.drop(1)) clip.addItem(android.content.ClipData.Item(u))
            intento.clipData = clip
            intento.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        activity.startActivity(Intent.createChooser(intento, a.titulo.ifEmpty { null }))
        invoke.resolve(JSObject().put("compartidas", uris.size))
    }

    private fun tipoDe(ruta: String): String = when (ruta.substringAfterLast('.', "").lowercase()) {
        "mp3" -> "audio/mpeg"
        "m4a", "aac" -> "audio/mp4"
        "opus", "ogg" -> "audio/ogg"
        "webm" -> "audio/webm"
        "flac" -> "audio/flac"
        "wav" -> "audio/wav"
        "mp4" -> "video/mp4"
        "m3u8", "m3u" -> "audio/x-mpegurl"
        else -> "application/octet-stream"
    }

    /**
     * Permisos para que descargas y actualizaciones sigan en segundo plano: ver la notificación de avance y
     * que Android no limite la batería de la app. Con pedir="notificaciones" o "bateria" abre el diálogo
     * del sistema; siempre responde cómo están ahora (la respuesta del usuario se vuelve a consultar al volver).
     */
    @Command
    fun segundoPlano(invoke: Invoke) {
        val a = invoke.parseArgs(ArgsFondo::class.java)
        val app = activity.applicationContext
        val energia = app.getSystemService(PowerManager::class.java)
        fun notificaciones() = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(activity, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        fun bateria() = energia.isIgnoringBatteryOptimizations(app.packageName)

        if (a.pedir == "notificaciones" && !notificaciones()) {
            val prefs = app.getSharedPreferences("misiccord", Context.MODE_PRIVATE)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !prefs.getBoolean("pidio_notificaciones", false)) {
                prefs.edit().putBoolean("pidio_notificaciones", true).apply()
                ActivityCompat.requestPermissions(activity, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 42)
            } else {
                // Ya se negó una vez: Android no vuelve a mostrar el diálogo, hay que ir a los ajustes de la app
                activity.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, app.packageName))
            }
        } else if (a.pedir == "bateria" && !bateria()) {
            try {
                activity.startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                                              Uri.parse("package:${app.packageName}")))
            } catch (e: Exception) {
                activity.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            }
        }
        invoke.resolve(JSObject().put("notificaciones", notificaciones()).put("bateria", bateria()))
    }

    /** Lo que suena ahora: notificación de música, pantalla bloqueada, relojes y audífonos (ServicioMedios). */
    @Command
    fun medios(invoke: Invoke) {
        val a = invoke.parseArgs(ArgsMedios::class.java)
        ServicioMedios.actualizar(activity.applicationContext, if (!a.hay) null else EstadoMedios(
            a.titulo, a.artista, a.album, a.portada, a.duracion, a.posicion, a.sonando, a.enJam))
        invoke.resolve()
    }

    @Command
    fun esperarEvento(invoke: Invoke) {
        thread(name = "python-eventos") {
            // Espera hasta 20 s; si no hay nada responde vacío y Rust vuelve a preguntar
            val evento = eventos.poll(20, TimeUnit.SECONDS)
            invoke.resolve(JSObject().put("evento", evento ?: ""))
        }
    }
}
