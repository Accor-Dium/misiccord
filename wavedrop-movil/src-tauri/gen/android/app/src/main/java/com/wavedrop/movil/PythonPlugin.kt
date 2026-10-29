package com.wavedrop.movil

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
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

/** Python llama a emitir(json) para avisar algo (progreso de descargas, recomendaciones listas...). */
class Emisor(private val cola: LinkedBlockingQueue<String>) {
    fun emitir(texto: String) {
        cola.offer(texto)
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
    private val emisor = Emisor(eventos)

    private fun python(): Python {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(activity.applicationContext))
        }
        return Python.getInstance()
    }

    /** Carpetas que usa Python: datos (base de datos), música, caché y dónde está qjs. */
    private fun contexto(): String {
        val app = activity.applicationContext
        return JSONObject()
            .put("datos", app.filesDir.absolutePath + "/wavedrop")
            .put("musica", app.getExternalFilesDir(Environment.DIRECTORY_MUSIC)?.absolutePath ?: app.filesDir.absolutePath + "/musica")
            .put("cache", app.cacheDir.absolutePath)
            .put("libs", app.applicationInfo.nativeLibraryDir)
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
