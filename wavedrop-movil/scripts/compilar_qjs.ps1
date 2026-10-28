# Compila QuickJS-ng (qjs) para Android con el NDK y lo deja como libqjs.so en jniLibs.
# yt-dlp lo usa para resolver los retos de JavaScript de YouTube (en Android no existe deno).
#
# Uso:  .\scripts\compilar_qjs.ps1            (descarga QuickJS-ng v0.17.0 en %TEMP%\wd-qjs si no está)
param(
    [string]$Version = "v0.17.0",
    [string]$Fuente = "$env:TEMP\wd-qjs",
    [int]$Api = 24
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path "$Fuente\qjs.c")) {
    git clone --quiet --depth 1 --branch $Version https://github.com/quickjs-ng/quickjs.git $Fuente
}

$ndk = $env:NDK_HOME
if (-not $ndk) { $ndk = Get-ChildItem "$env:LOCALAPPDATA\Android\Sdk\ndk" -Directory | Sort-Object Name | Select-Object -Last 1 -ExpandProperty FullName }
$clang = "$ndk\toolchains\llvm\prebuilt\windows-x86_64\bin\clang.exe"
if (-not (Test-Path $clang)) { throw "No encontré clang del NDK en $clang" }

$jniLibs = Join-Path $PSScriptRoot "..\src-tauri\gen\android\app\src\main\jniLibs"
$archivos = "dtoa.c", "libregexp.c", "libunicode.c", "quickjs.c", "quickjs-libc.c", "gen\repl.c", "gen\standalone.c", "qjs.c" |
    ForEach-Object { Join-Path $Fuente $_ }

foreach ($abi in @{ "x86_64" = "x86_64-linux-android"; "arm64-v8a" = "aarch64-linux-android" }.GetEnumerator()) {
    $salida = Join-Path $jniLibs "$($abi.Key)\libqjs.so"
    New-Item -ItemType Directory -Force (Split-Path $salida) | Out-Null
    Write-Host "Compilando qjs para $($abi.Key)..."
    & $clang "--target=$($abi.Value)$Api" -O2 -DNDEBUG -D_GNU_SOURCE -fPIE -pie `
        -I $Fuente @archivos -o $salida -lm -ldl -s
    if ($LASTEXITCODE) { throw "Falló la compilación para $($abi.Key)" }
    Write-Host ("  {0} ({1:N1} MB)" -f $salida, ((Get-Item $salida).Length / 1MB))
}
