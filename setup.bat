@echo off
setlocal enabledelayedexpansion
title Zonor - Instalador
color 0D

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BIN_DIR=%ROOT%\bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

:: ===== PASO 1: Python =====
cls
echo.
echo  ============================================================
echo    Zonor - Instalacion automatica
echo  ============================================================
echo.
echo  Paso 1/6: Verificando Python...
echo.

python --version >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] Python no instalado.
    echo  Descarga: https://www.python.org/downloads/
    pause
    start https://www.python.org/downloads/
    goto :end
)

python --version
echo  [OK] Python encontrado
echo.
echo  ======================== 100%%
echo.
timeout /t 1 /nobreak >nul 2>&1

:: ===== PASO 2: pip =====
cls
echo.
echo  ============================================================
echo    Zonor - Instalacion automatica
echo  ============================================================
echo.
echo  Paso 2/6: Instalando dependencias Python...
echo.
echo  Paquetes: pywebview, ytmusicapi, yt-dlp, Pillow, requests, syncedlyrics, browser-cookie3
echo.
echo  (Esto puede tardar varios minutos, depende de tu internet)
echo.

set "PIP_LOG=%TEMP%\zonor_pip.log"
python -m pip install --timeout 120 -r "%ROOT%\requirements.txt" >"%PIP_LOG%" 2>&1
set "PIP_OK=%errorlevel%"
type "%PIP_LOG%"

if %PIP_OK% equ 0 (
    echo.
    echo  [OK] Dependencias instaladas correctamente
) else (
    echo.
    echo  [ERROR] Fallo la instalacion (codigo: %PIP_OK%)
    echo.
    echo  Revisa "%PIP_LOG%" para mas detalles
    echo.
    echo  Para instalar manualmente:
    echo    cd /d "%ROOT%"
    echo    python -m pip install -r requirements.txt
    echo.
    pause
)
echo.
echo  ======================== 100%%
echo.
timeout /t 1 /nobreak >nul 2>&1

:: ===== PASO 3: Icono =====
cls
echo.
echo  ============================================================
echo    Zonor - Instalacion automatica
echo  ============================================================
echo.
echo  Paso 3/6: Generando icono multi-tamano...
echo.

if exist "%ROOT%\zonor.ico" (
    echo  [OK] Icono listo
) else (
    set "PNG_FILE="
    for %%f in ("%ROOT%\icon_source.png" "%ROOT%\*.png") do if exist "%%f" if not defined PNG_FILE set "PNG_FILE=%%f"
    if defined PNG_FILE (
        python "%ROOT%\gen_icon.py" "!PNG_FILE!"
        if exist "%ROOT%\zonor.ico" (
            echo  [OK] Icono generado
        )
    ) else (
        echo  [AVISO] No se encontro imagen para icono
    )
)
echo.
echo  ======================== 100%%
echo.
timeout /t 1 /nobreak >nul 2>&1

:: ===== PASO 4: yt-dlp =====
cls
echo.
echo  ============================================================
echo    Zonor - Instalacion automatica
echo  ============================================================
echo.
echo  Paso 4/6: Descargando yt-dlp...
echo.

if exist "%BIN_DIR%\yt-dlp.exe" (
    echo  [OK] yt-dlp ya existe
) else (
    bitsadmin /transfer "ZonorDL" /download /priority high "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" "%BIN_DIR%\yt-dlp.exe" >nul 2>&1
    if not exist "%BIN_DIR%\yt-dlp.exe" (
        powershell -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile '%BIN_DIR%\yt-dlp.exe' -UseBasicParsing } catch { }" >nul 2>&1
    )
    if exist "%BIN_DIR%\yt-dlp.exe" (
        echo  [OK] yt-dlp descargado
    ) else (
        echo  [AVISO] No se pudo descargar automaticamente
        echo  Manual: https://github.com/yt-dlp/yt-dlp/releases
    )
)
echo.
echo  ======================== 100%%
echo.
timeout /t 1 /nobreak >nul 2>&1

:: ===== PASO 5: Verificacion =====
cls
echo.
echo  ============================================================
echo    Zonor - Instalacion automatica
echo  ============================================================
echo.
echo  Paso 5/6: Verificando instalacion...
echo.

python -c "import webview" >nul 2>&1 && echo  [OK] pywebview     || echo  [FAIL] pywebview
python -c "import ytmusicapi" >nul 2>&1 && echo  [OK] ytmusicapi    || echo  [FAIL] ytmusicapi
python -c "import yt_dlp" >nul 2>&1 && echo  [OK] yt-dlp        || echo  [FAIL] yt-dlp
python -c "import PIL" >nul 2>&1 && echo  [OK] Pillow        || echo  [FAIL] Pillow
python -c "import syncedlyrics" >nul 2>&1 && echo  [OK] syncedlyrics || echo  [FAIL] syncedlyrics
python -c "import browser_cookie3" >nul 2>&1 && echo  [OK] browser-cookie3 || echo  [FAIL] browser-cookie3
if exist "%ROOT%\zonor.ico" ( echo  [OK] Icono ) else ( echo  [AVISO] Sin icono )
if exist "%BIN_DIR%\yt-dlp.exe" ( echo  [OK] yt-dlp.exe ) else ( echo  [AVISO] Sin yt-dlp.exe )
echo.
echo  ======================== 100%%
echo.
timeout /t 1 /nobreak >nul 2>&1

:: ===== PASO 6: Shortcut y lanzador =====
cls
echo.
echo  ============================================================
echo    Zonor - Instalacion automatica
echo  ============================================================
echo.
echo  Paso 6/6: Creando acceso directo en el Escritorio...
echo.

:: Eliminar lanzador VBS antiguo (ya no se usa)
if exist "%ROOT%\Zonor.vbs" del "%ROOT%\Zonor.vbs"

:: Buscar pythonw.exe (absoluto, evita ventana CMD)
set "PYW="
for /f "tokens=*" %%a in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%a"
if not defined PYW (
    for /f "tokens=*" %%a in ('where python 2^>nul') do set "PYW=%%a"
    if defined PYW set "PYW=!PYW:\python.exe=\pythonw.exe!"
)
if not defined PYW set "PYW=pythonw.exe"

:: Crear acceso directo directo a pythonw.exe (sin VBS, sin CMD)
set "ICONO=%ROOT%\zonor.ico"
set "PS=%TEMP%\zonor_lnk.ps1"
> "%PS%" echo $ws = New-Object -ComObject WScript.Shell
>>"%PS%" echo $desktop = [Environment]::GetFolderPath("Desktop")
>>"%PS%" echo $lnk = $ws.CreateShortcut("$desktop\Zonor.lnk")
>>"%PS%" echo $lnk.TargetPath = "%PYW:\=\\%"
>>"%PS%" echo $lnk.Arguments = """%ROOT:\=\\%\\run.py"""
>>"%PS%" echo $lnk.WorkingDirectory = "%ROOT:\=\\%"
>>"%PS%" echo $lnk.Description = "Zonor - Reproductor YouTube Music"
>>"%PS%" echo $lnk.WindowStyle = 7
if exist "%ICONO%" (
    >>"%PS%" echo $lnk.IconLocation = "%ICONO:\=\\%, 0"
)
>>"%PS%" echo $lnk.Save()

powershell -ExecutionPolicy Bypass -File "%PS%"
del "%PS%" 2>nul

if exist "%USERPROFILE%\Desktop\Zonor.lnk" (
    echo  [OK] Acceso directo creado en el Escritorio
    echo  [INFO] Ejecuta pythonw.exe directamente - sin ventana CMD, sin VBS
) else (
    echo  [AVISO] No se pudo crear el acceso directo
    echo  Para abrir: pythonw "%ROOT%\run.py"
)
echo.
echo  ======================== 100%%
echo.
timeout /t 2 /nobreak >nul 2>&1

:: ===== FINAL =====
cls
echo.
echo  ============================================================
echo    Zonor - Instalacion completada
echo  ============================================================
echo.
echo  Ruta: %ROOT%
echo.
echo  Abre Zonor desde el Escritorio (Zonor.lnk)
echo  o directamente: pythonw "%ROOT%\run.py"
echo.
echo  ============================================================

:end
pause
endlocal
