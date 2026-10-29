import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("rust")
    id("com.chaquo.python")
}

val tauriProperties = Properties().apply {
    val propFile = file("tauri.properties")
    if (propFile.exists()) {
        propFile.inputStream().use { load(it) }
    }
}

// Llave de firma (wavedrop-movil/firma/keystore.properties, fuera del control de versiones)
val firma = Properties().apply {
    val archivo = file("../../../../firma/keystore.properties")
    if (archivo.exists()) {
        archivo.inputStream().use { load(it) }
    }
}

android {
    compileSdk = 37
    namespace = "com.wavedrop.movil"
    defaultConfig {
        // Los jams van por HTTP dentro de la red local (no hay certificados en una red de casa)
        manifestPlaceholders["usesCleartextTraffic"] = "true"
        applicationId = "com.wavedrop.movil"
        minSdk = 24
        targetSdk = 37
        versionCode = tauriProperties.getProperty("tauri.android.versionCode", "1").toInt()
        versionName = tauriProperties.getProperty("tauri.android.versionName", "1.0")
        // Chaquopy necesita saber para qué procesadores empaquetar Python
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }
    // qjs (QuickJS) va como "libqjs.so" para que Android lo deje ejecutar: hay que extraerlo al instalar
    packaging { jniLibs { useLegacyPackaging = true } }
    signingConfigs {
        create("release") {
            if (firma.containsKey("storeFile")) {
                storeFile = file(firma.getProperty("storeFile"))
                storePassword = firma.getProperty("storePassword")
                keyAlias = firma.getProperty("keyAlias")
                keyPassword = firma.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        getByName("debug") {
            manifestPlaceholders["usesCleartextTraffic"] = "true"
            isDebuggable = true
            isJniDebuggable = true
            isMinifyEnabled = false
            packaging {
                jniLibs.keepDebugSymbols.add("*/arm64-v8a/*.so")
                jniLibs.keepDebugSymbols.add("*/armeabi-v7a/*.so")
                jniLibs.keepDebugSymbols.add("*/x86/*.so")
                jniLibs.keepDebugSymbols.add("*/x86_64/*.so")
            }
        }
        getByName("release") {
            signingConfig = signingConfigs.getByName("release")
            optimization {
               enable = true
            }
            proguardFiles(
                *fileTree(".") {
                  include("**/*.pro")
                  exclude("build/**")
                }.files.toTypedArray()
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    buildFeatures {
        buildConfig = true
    }
}

kotlin {
    compilerOptions {
        jvmTarget = JvmTarget.JVM_1_8
    }
}

rust {
    rootDirRel = "../../../"
}

chaquopy {
    // El núcleo de Python vive fuera de gen/ (wavedrop-movil/python) y lo comparten Android y Windows
    sourceSets {
        getByName("main") {
            srcDir("../../../../python")
        }
    }
    defaultConfig {
        version = "3.14"
        buildPython("C:/Python314/python.exe")  // debe ser la misma versión que la de la app
        pip {
            // Sin "[default]": esos extras traen código compilado (brotli, pycryptodomex, curl_cffi)
            // que no existe para Android y pip terminaría eligiendo un yt-dlp viejísimo
            install("yt-dlp>=2026.10.26")
            install("yt-dlp-ejs")  // scripts de JS que yt-dlp corre con QuickJS para YouTube
            install("ytmusicapi")
            install("mutagen")
            install("qrcode")  // QR para unirse a un jam (puro Python)
        }
    }
}

dependencies {
    implementation("androidx.webkit:webkit:1.14.0")
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.lifecycle:lifecycle-process:2.10.0")
    implementation("androidx.media:media:1.7.0") // MediaSession y notificación de música (relojes, pantalla bloqueada)
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.4")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.0")
}

apply(from = file("tauri.build.gradle.kts"))
