; Zonor Installer for Inno Setup
; Requires Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;
; Usage:
;   1. Install Inno Setup
;   2. Right-click this file -> Compile
;   3. Or run: iscc installer.iss

#define MyAppName "Zonor"
#define MyAppVersion "1.0"
#define MyAppPublisher "Zonor"
#define MyAppURL "https://github.com/YongllyPM/Zonor"

[Setup]
AppId={{B8A3C8E1-4F2A-4A8C-9D7E-1F2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=Zonor_Setup_v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableProgramGroupPage=yes
CloseApplications=no
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=zonor.ico
UninstallDisplayIcon={app}\zonor.ico
ChangesEnvironment=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Core app files
Source: "run.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "gen_icon.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "installer.iss"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "zonor.ico"; DestDir: "{app}"; Flags: ignoreversion

; Python modules
Source: "app\*.py"; DestDir: "{app}\app"; Flags: ignoreversion

; Web frontend
Source: "web\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs

; Pre-downloaded yt-dlp (optional — setup.bat downloads it if missing)
; Source: "bin\yt-dlp.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

[Dirs]
Name: "{app}\app"
Name: "{app}\web"
Name: "{app}\bin"

[Icons]
; Uses pythonw.exe to avoid CMD window (same as setup.bat)
Name: "{autoprograms}\{#MyAppName}"; \
  Filename: "{code:GetPythonw}"; \
  Parameters: """{app}\run.py"""; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\zonor.ico"; \
  Comment: "Zonor - Reproductor YouTube Music"

Name: "{autodesktop}\{#MyAppName}"; \
  Filename: "{code:GetPythonw}"; \
  Parameters: """{app}\run.py"""; \
  WorkingDir: "{app}"; \
  IconFilename: "{app}\zonor.ico"; \
  Comment: "Zonor - Reproductor YouTube Music"; \
  Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"
Name: "installdeps"; Description: "Ejecutar instalacion de dependencias (pip, yt-dlp)"; GroupDescription: "Configuracion:"; Flags: checkedonce

[Run]
; Run setup.bat if task is selected
Filename: "{app}\setup.bat"; Description: "Instalar dependencias Python..."; \
  Flags: postinstall nowait skipifsilent shellexec; \
  Tasks: installdeps; \
  StatusMsg: "Instalando dependencias Python y descargando yt-dlp..."

; Run app after install (optional)
Filename: "{code:GetPythonw}"; Parameters: """{app}\run.py"""; \
  Description: "Abrir Zonor ahora"; \
  Flags: postinstall nowait skipifsilent shellexec unchecked; \
  WorkingDir: "{app}"

[UninstallRun]
; Ask before deleting user data
Filename: "{cmd}"; Parameters: "/c echo Al eliminar Zonor, los datos de usuario en %APPDATA%\Zonor\ no se borraran automaticamente."; \
  Flags: runhidden

[Code]
var
  PythonwPath: string;

function GetPythonw(Param: string): string;
begin
  if PythonwPath <> '' then
    Result := PythonwPath
  else
    Result := 'pythonw.exe';
end;

function FindPythonw: string;
var
  PythonPath: string;
  ResultCode: Integer;
begin
  // Try common Python 3 install locations
  PythonPath := ExpandConstant('{autopf}\Python313\');
  if FileExists(PythonPath + 'pythonw.exe') then begin
    Result := PythonPath + 'pythonw.exe'; exit;
  end;

  PythonPath := ExpandConstant('{autopf}\Python312\');
  if FileExists(PythonPath + 'pythonw.exe') then begin
    Result := PythonPath + 'pythonw.exe'; exit;
  end;

  PythonPath := ExpandConstant('{autopf}\Python311\');
  if FileExists(PythonPath + 'pythonw.exe') then begin
    Result := PythonPath + 'pythonw.exe'; exit;
  end;

  // Check from registry (exact versions, no wildcards)
  PythonPath := '';
  if RegQueryStringValue(HKLM64, 'SOFTWARE\Python\PythonCore\3.13\InstallPath', '', PythonPath) or
     RegQueryStringValue(HKLM32, 'SOFTWARE\Python\PythonCore\3.13\InstallPath', '', PythonPath) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Python\PythonCore\3.13\InstallPath', '', PythonPath) then
  begin
    if FileExists(PythonPath + 'pythonw.exe') then begin
      Result := PythonPath + 'pythonw.exe'; exit;
    end;
  end;
  PythonPath := '';
  if RegQueryStringValue(HKLM64, 'SOFTWARE\Python\PythonCore\3.12\InstallPath', '', PythonPath) or
     RegQueryStringValue(HKLM32, 'SOFTWARE\Python\PythonCore\3.12\InstallPath', '', PythonPath) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Python\PythonCore\3.12\InstallPath', '', PythonPath) then
  begin
    if FileExists(PythonPath + 'pythonw.exe') then begin
      Result := PythonPath + 'pythonw.exe'; exit;
    end;
  end;
  PythonPath := '';
  if RegQueryStringValue(HKLM64, 'SOFTWARE\Python\PythonCore\3.11\InstallPath', '', PythonPath) or
     RegQueryStringValue(HKLM32, 'SOFTWARE\Python\PythonCore\3.11\InstallPath', '', PythonPath) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Python\PythonCore\3.11\InstallPath', '', PythonPath) then
  begin
    if FileExists(PythonPath + 'pythonw.exe') then begin
      Result := PythonPath + 'pythonw.exe'; exit;
    end;
  end;

  // Check %LOCALAPPDATA%\Programs\Python (Microsoft Store installs)
  PythonPath := ExpandConstant('{localappdata}\Programs\Python\Python313\');
  if FileExists(PythonPath + 'pythonw.exe') then begin
    Result := PythonPath + 'pythonw.exe'; exit;
  end;
  PythonPath := ExpandConstant('{localappdata}\Programs\Python\Python312\');
  if FileExists(PythonPath + 'pythonw.exe') then begin
    Result := PythonPath + 'pythonw.exe'; exit;
  end;

  // Try to find via PATH (where command)
  if Exec('where', 'pythonw.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    // where succeeded but we don't capture output easily.
    // Let PATH handle it at runtime.
  end;

  // Fallback: let Windows resolve via PATH
  Result := 'pythonw.exe';
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  PythonwPath := FindPythonw();
  if PythonwPath = 'pythonw.exe' then
  begin
    MsgBox('No se encontro Python 3 en las ubicaciones habituales.' + #13#10#13#10 +
           'Si Python 3.11+ esta instalado pero no se detecto,' + #13#10 +
           'el acceso directo usara pythonw.exe desde PATH.' + #13#10#13#10 +
           'Descarga: https://www.python.org/downloads/',
           mbInformation, MB_OK);
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := 0;
end;
