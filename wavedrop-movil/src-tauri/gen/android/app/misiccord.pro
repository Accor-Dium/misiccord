# Tauri encuentra los plugins (el nuestro y los oficiales, como el escáner de QR) por su nombre
# y Python llama a Emisor.emitir por reflexión: la optimización de release no debe quitar ni
# renombrar estas clases, o la app se cierra al usarlas.
-keep class com.wavedrop.movil.** { *; }
-keep class com.chaquo.python.** { *; }
-keep class app.tauri.** { *; }
-keep @app.tauri.annotation.TauriPlugin class * { *; }
-keepclassmembers class * {
    @app.tauri.annotation.Command *;
    @app.tauri.annotation.PermissionCallback *;
    @app.tauri.annotation.ActivityCallback *;
}
-keep @app.tauri.annotation.InvokeArg class * { *; }

# Lector QR: ML Kit crea sus componentes por reflexión (ComponentRegistrar con constructor vacío).
# Si R8 les quita el constructor, el escáner truena con el primer cuadro de la cámara.
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.internal.mlkit_vision_barcode.** { *; }
-keep class com.google.android.gms.internal.mlkit_vision_common.** { *; }
-keep class com.google.firebase.components.** { *; }
-keep class * implements com.google.firebase.components.ComponentRegistrar { <init>(); }
-keep class androidx.camera.** { *; }
-dontwarn com.google.mlkit.**
