# Publica una versión nueva de Misiccord en GitHub Releases (Accor-Dium/misiccord).
#
# Las apps ya instaladas la detectan solas:
#   - Windows: leen latest.json (firmado) y se actualizan con el plugin de Tauri.
#   - Android: leen la última Release, bajan el APK y abren el instalador.
#
# Uso:   .\scripts\publicar.ps1 -Version 1.0.1 -Notas "Arreglos en el lector QR"
# Antes: gh auth login   (una sola vez, con una cuenta que pueda publicar en Accor-Dium)
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Notas = "",
    [switch]$SinServicio,   # no volver a empaquetar Python (solo si no cambió nada en python/)
    [switch]$Borrador       # crear la Release como borrador para revisarla antes
)
$ErrorActionPreference = "Stop"
$Repo = "Accor-Dium/misiccord"
$Raiz = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Raiz
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "La versión debe verse como 1.0.1" }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "Falta GitHub CLI: winget install GitHub.cli y luego gh auth login" }
gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE) { throw "Inicia sesión primero: gh auth login" }

# 1) Versión (Tauri la usa para Windows y Android: versionName y versionCode)
$python = Join-Path $Raiz "..\venv\Scripts\python.exe"
& $python -c "import json,pathlib,sys; p=pathlib.Path('src-tauri/tauri.conf.json'); c=json.loads(p.read_text(encoding='utf-8-sig')); c['version']=sys.argv[1]; p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')" $Version
Write-Host "Versión $Version"

# 2) Servicio de Python (lleva el núcleo adentro)
if (-not $SinServicio) {
    Write-Host "Empaquetando el servicio de Python..."
    & $python scripts\construir_servicio.py | Select-String "Servicio listo"
}

# 3) Instalador de Windows firmado para el actualizador
$env:TAURI_SIGNING_PRIVATE_KEY = (Resolve-Path "firma\actualizaciones.key").Path
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = ((Get-Content "firma\actualizaciones.properties" | Where-Object { $_ -like "TAURI_SIGNING_PRIVATE_KEY_PASSWORD=*" }) -split "=", 2)[1]
Write-Host "Compilando Windows..."
npx tauri build
if ($LASTEXITCODE) { throw "Falló la compilación de Windows" }

# 4) APK firmado con la llave de firma/
Write-Host "Compilando Android..."
npx tauri android build --apk --target aarch64
if ($LASTEXITCODE) { throw "Falló la compilación de Android" }

# 5) Archivos de la Release + latest.json
$salida = Join-Path $Raiz "publicar\v$Version"
New-Item -ItemType Directory -Force $salida | Out-Null
$setup = Get-ChildItem "src-tauri\target\release\bundle\nsis" -Filter "*_${Version}_x64-setup.exe" | Select-Object -First 1
if (-not $setup) { throw "No encontré el instalador de Windows de la versión $Version" }
$nombreSetup = "Misiccord_${Version}_x64-setup.exe"
Copy-Item $setup.FullName (Join-Path $salida $nombreSetup) -Force
Copy-Item "$($setup.FullName).sig" (Join-Path $salida "$nombreSetup.sig") -Force
$apk = Get-ChildItem "src-tauri\gen\android\app\build\outputs\apk" -Recurse -Filter "*release*.apk" | Sort-Object LastWriteTime | Select-Object -Last 1
$nombreApk = "Misiccord-$Version.apk"
Copy-Item $apk.FullName (Join-Path $salida $nombreApk) -Force

$latest = [ordered]@{
    version   = $Version
    notes     = $Notas
    pub_date  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    platforms = [ordered]@{
        "windows-x86_64" = [ordered]@{
            signature = (Get-Content (Join-Path $salida "$nombreSetup.sig") -Raw).Trim()
            url       = "https://github.com/$Repo/releases/download/v$Version/$nombreSetup"
        }
    }
}
[IO.File]::WriteAllText((Join-Path $salida "latest.json"), ($latest | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding $false))

# 6) Publicar
$archivos = @("$salida\$nombreSetup", "$salida\$nombreSetup.sig", "$salida\$nombreApk", "$salida\latest.json")
$extra = @()
if ($Borrador) { $extra += "--draft" }
$textoNotas = if ($Notas) { $Notas } else { "Misiccord $Version" }
gh release create "v$Version" @archivos --repo $Repo --title "Misiccord $Version" --notes $textoNotas @extra
if ($LASTEXITCODE) { throw "No se pudo crear la Release en GitHub" }
Write-Host "`nListo: https://github.com/$Repo/releases/tag/v$Version"
