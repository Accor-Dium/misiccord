package com.wavedrop.movil

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.os.Process
import android.view.ViewGroup
import android.webkit.WebView
import androidx.activity.OnBackPressedCallback
import androidx.activity.enableEdgeToEdge

/**
 * La única pantalla de Misiccord.
 *
 * Quitar la app de "recientes" destruye esta Activity y, con ella, Tauri cerraba todo el proceso (y la música, que suena en
 * la WebView). Si en ese momento algo suena, se "conserva" la sesión: a Tauri se le dice que la Activity solo se está
 * recreando (como al girar la pantalla), así no cierra el proceso ni destruye la WebView, y la música sigue con su
 * notificación. Al volver a abrir la app, esa misma WebView se pone en la Activity nueva: nada se recarga ni se corta.
 */
class MainActivity : TauriActivity() {
  companion object {
    /** La Activity visible (los plugins se crean con la primera y la usan para abrir pantallas del sistema). */
    var actual: Activity? = null
      private set

    /** La WebView de una sesión conservada, esperando a que se vuelva a abrir la app. */
    private var conservada: WebView? = null

    /** true después de volver a una sesión conservada: Tauri y sus plugins siguen ligados a la Activity vieja. */
    var reanudada = false
      private set

    /** Reinicia la app desde cero (para lo que necesita la Activity original, como la cámara del lector QR). */
    fun reiniciar(desde: Activity) {
      val intento = desde.packageManager.getLaunchIntentForPackage(desde.packageName)
        ?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
      desde.startActivity(intento)
      Process.killProcess(Process.myPid())
    }
  }

  private var webView: WebView? = null
  private var conservar = false

  override fun onCreate(savedInstanceState: Bundle?) {
    enableEdgeToEdge()
    super.onCreate(savedInstanceState)
    actual = this
    val vieja = conservada ?: return
    conservada = null
    reanudada = true
    // Sin Activity de por medio Tauri no crea otra WebView: se muda la que siguió sonando
    (vieja.parent as? ViewGroup)?.removeView(vieja)
    setContentView(vieja)
    webView = vieja
    vieja.onResume()
    // Tauri registra "atrás = regresar en la WebView" solo con la WebView que él crea: aquí se hace a mano
    onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
      override fun handleOnBackPressed() {
        if (vieja.canGoBack()) vieja.goBack() else finish()
      }
    })
  }

  override fun onWebViewCreate(webView: WebView) {
    this.webView = webView
  }

  override fun onResume() {
    super.onResume()
    actual = this
  }

  override fun onDestroy() {
    // isFinishing: la cierran de verdad (recientes, atrás), no es un giro de pantalla
    conservar = isFinishing && ServicioMedios.sonando && webView != null
    if (conservar) {
      conservada = webView
      (webView?.parent as? ViewGroup)?.removeView(webView)
    }
    if (actual === this) actual = null
    super.onDestroy()
    // Una Activity a la que se mudó la WebView no es la que Tauri conoce: si se cierra sin conservar, Tauri no se
    // entera y el proceso quedaría vivo sin pantalla. Se cierra como se cerraría la app normal.
    if (reanudada && isFinishing && !conservar) Process.killProcess(Process.myPid())
  }

  // Tauri (tao y wry) revisa esto en onDestroy: si es true guarda la ventana y la WebView en vez de cerrar la app
  override fun isChangingConfigurations(): Boolean = conservar || super.isChangingConfigurations()
}
