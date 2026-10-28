package com.wavedrop.movil

import android.app.Activity
import android.os.Environment
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
    private val eventos = LinkedBlockingQueue<String>()
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

    @Command
    fun esperarEvento(invoke: Invoke) {
        thread(name = "python-eventos") {
            // Espera hasta 20 s; si no hay nada responde vacío y Rust vuelve a preguntar
            val evento = eventos.poll(20, TimeUnit.SECONDS)
            invoke.resolve(JSObject().put("evento", evento ?: ""))
        }
    }
}
