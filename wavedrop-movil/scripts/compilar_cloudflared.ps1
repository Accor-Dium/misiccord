# Compila cloudflared para Android con el NDK y lo deja como libcloudflared.so en jniLibs.
# Con él un celular puede abrir su jam a internet (túnel rápido de Cloudflare).
#
# Se compila con GOOS=android y cgo: así usa el DNS del sistema (el binario de Linux que publica
# Cloudflare busca /etc/resolv.conf, que Android no tiene, y no logra conectarse).
#
# Uso:  .\scripts\compilar_cloudflared.ps1      (necesita Go: winget install GoLang.Go)
param(
    [string]$Version = "2026.10.5",
    [string]$Fuente = "$env:TEMP\wd-cf",
    [int]$Api = 24
)
$ErrorActionPreference = "Stop"
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
# Go portátil (zip de go.dev en %LOCALAPPDATA%\wd-go) si no está instalado en el sistema
if (Test-Path "$env:LOCALAPPDATA\wd-go\go\bin\go.exe") { $env:Path = "$env:LOCALAPPDATA\wd-go\go\bin;$env:Path" }
if (-not (Get-Command go -ErrorAction SilentlyContinue)) { throw "Falta Go: baja el zip de https://go.dev/dl y descomprímelo en %LOCALAPPDATA%\wd-go" }

if (-not (Test-Path "$Fuente\cmd\cloudflared")) {
    git clone --quiet --depth 1 --branch $Version https://github.com/cloudflare/cloudflared.git $Fuente
}

$ndk = $env:NDK_HOME
if (-not $ndk) { $ndk = Get-ChildItem "$env:LOCALAPPDATA\Android\Sdk\ndk" -Directory | Sort-Object Name | Select-Object -Last 1 -ExpandProperty FullName }
$bin = "$ndk\toolchains\llvm\prebuilt\windows-x86_64\bin"
if (-not (Test-Path "$bin\clang.exe")) { throw "No encontré clang del NDK en $bin" }

$jniLibs = Join-Path $PSScriptRoot "..\src-tauri\gen\android\app\src\main\jniLibs"
Push-Location $Fuente
try {
    foreach ($abi in @(
            @{ Carpeta = "arm64-v8a"; Arch = "arm64"; Destino = "aarch64-linux-android" },
            @{ Carpeta = "x86_64"; Arch = "amd64"; Destino = "x86_64-linux-android" })) {
        $salida = Join-Path $jniLibs "$($abi.Carpeta)\libcloudflared.so"
        New-Item -ItemType Directory -Force (Split-Path $salida) | Out-Null
        Write-Host "Compilando cloudflared $Version para $($abi.Carpeta)..."
        $env:CGO_ENABLED = "1"
        $env:GOOS = "android"
        $env:GOARCH = $abi.Arch
        $env:CC = "$bin\clang.exe --target=$($abi.Destino)$Api"
        # go escribe su avance en stderr: en PowerShell 5 eso no debe contar como error
        $ErrorActionPreference = "Continue"
        go build -trimpath -ldflags "-s -w -X main.Version=$Version" -o $salida ./cmd/cloudflared 2>&1 |
            Where-Object { "$_" -notmatch '^go: downloading' } | ForEach-Object { Write-Host "  $_" }
        $codigo = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        if ($codigo) { throw "Falló la compilación para $($abi.Carpeta)" }
        Write-Host ("  {0:N1} MB -> {1}" -f ((Get-Item $salida).Length / 1MB), $salida)
    }
} finally {
    Pop-Location
    Remove-Item Env:CGO_ENABLED, Env:GOOS, Env:GOARCH, Env:CC -ErrorAction SilentlyContinue
}
