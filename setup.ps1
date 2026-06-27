# Zonor - Setup Script for Windows
Write-Host "=== Zonor Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pyVersion = python --version
    Write-Host "✓ Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python no encontrado. Instálalo desde https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

# Install Python dependencies
Write-Host ""
Write-Host "Instalando dependencias Python..." -ForegroundColor Yellow
$reqFile = Join-Path $PSScriptRoot "requirements.txt"
python -m pip install -r $reqFile
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Error instalando dependencias" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Dependencias instaladas" -ForegroundColor Green

# Download yt-dlp
Write-Host ""
Write-Host "Descargando yt-dlp..." -ForegroundColor Yellow
$binDir = Join-Path $PSScriptRoot "bin"
New-Item -ItemType Directory -Path $binDir -Force | Out-Null
$ytdlpPath = Join-Path $binDir "yt-dlp.exe"
if (-not (Test-Path $ytdlpPath)) {
    Invoke-WebRequest -Uri "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" -OutFile $ytdlpPath
    Write-Host "✓ yt-dlp descargado" -ForegroundColor Green
} else {
    Write-Host "✓ yt-dlp ya existe" -ForegroundColor Green
}

# Ask about mpv
Write-Host ""
Write-Host "¿Descargar mpv para reproducción de audio? (Recomendado)" -ForegroundColor Yellow
Write-Host "Si no, se usará VLC (python-vlc) si está instalado." -ForegroundColor Gray
$dlMpv = Read-Host "¿Descargar mpv? (s/N)"

if ($dlMpv -eq "s" -or $dlMpv -eq "S") {
    $mpvPath = Join-Path $binDir "mpv.exe"
    if (-not (Test-Path $mpvPath)) {
        Write-Host "Descargando mpv..." -ForegroundColor Yellow
        # Download mpv portable from GitHub
        $mpvUrl = "https://sourceforge.net/projects/mpv-player-windows/files/64bit/mpv-x86_64-20230226.7z/download"
        $mpvArchive = Join-Path $env:TEMP "mpv.7z"
        try {
            Invoke-WebRequest -Uri $mpvUrl -OutFile $mpvArchive
            # Extract mpv.exe
            if (Get-Command 7z -ErrorAction SilentlyContinue) {
                7z e $mpvArchive -o"$binDir" mpv.exe -y
            } elseif (Get-Command Expand-Archive -ErrorAction SilentlyContinue) {
                # 7z not available, try to download just the exe
                Remove-Item $mpvArchive -Force -ErrorAction SilentlyContinue
                Write-Host "Usando método alternativo..." -ForegroundColor Yellow
                # Download from alternative source
                $mpvDirectUrl = "https://downloads.sourceforge.net/project/mpv-player-windows/64bit/mpv-x86_64-20230226.7z"
                Invoke-WebRequest -Uri $mpvDirectUrl -OutFile $mpvArchive
                # Try to extract with Python
                python -c "
import zipfile, tarfile, os, shutil
import subprocess
result = subprocess.run(['where', '7z'], capture_output=True, text=True)
if result.returncode == 0:
    subprocess.run(['7z', 'e', r'$mpvArchive', '-o"$binDir"', 'mpv.exe', '-y'])
else:
    # Download just the exe from GitHub releases
    import urllib.request
    url = 'https://github.com/audiohacked/mpv-winbuild/releases/download/mpv-x86_64-20230226/mpv-x86_64-20230226.7z'
    print('Download failed, please manually download mpv.exe to bin/ folder')
    print('Get it from: https://mpv.io/installation/')
" 2>$null
            }
            if (Test-Path $mpvPath) {
                Write-Host "✓ mpv descargado" -ForegroundColor Green
            } else {
                Write-Host "⚠ No se pudo extraer mpv. Descárgalo manualmente." -ForegroundColor Yellow
            }
            Remove-Item $mpvArchive -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Host "⚠ Error descargando mpv. Descárgalo manualmente desde https://mpv.io/installation/" -ForegroundColor Yellow
        }
    } else {
        Write-Host "✓ mpv ya existe" -ForegroundColor Green
    }
} else {
    Write-Host "Instalando python-vlc como alternativa..." -ForegroundColor Yellow
    python -m pip install python-vlc
}

Write-Host ""
Write-Host "=== Instalación completa ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para ejecutar:" -ForegroundColor White
Write-Host "  cd $(Split-Path $PSScriptRoot -Leaf)" -ForegroundColor Gray
Write-Host "  python run.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Requisitos para funcionalidad completa:" -ForegroundColor Yellow
Write-Host "  1. Tener una cuenta de YouTube Music" -ForegroundColor Gray
Write-Host "  2. Instalar extensión 'Get cookies.txt' en Chrome/Edge" -ForegroundColor Gray
Write-Host "  3. O usar autenticación desde el navegador" -ForegroundColor Gray
Write-Host ""
Read-Host "Presiona Enter para salir"
