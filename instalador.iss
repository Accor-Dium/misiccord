; Script de Inno Setup para el instalador. Lo usa build.py automáticamente.

#define Nombre "WaveDrop"
#define Exe "DescargadorPlaylists.exe"
#define Version "2.2.0"

[Setup]
AppId={{6F3B2A1E-8C4D-4E7A-9B21-5D0C7E9A4F13}
AppName={#Nombre}
AppVersion={#Version}
AppPublisher=Hiram
DefaultDirName={autopf}\DescargadorPlaylists
DefaultGroupName={#Nombre}
UninstallDisplayIcon={app}\{#Exe}
SetupIconFile=icono.ico
OutputDir=instalador
OutputBaseFilename=DescargadorPlaylists-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Se instala solo para el usuario actual, sin pedir permisos de administrador
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\DescargadorPlaylists\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nombre}"; Filename: "{app}\{#Exe}"
Name: "{group}\Desinstalar {#Nombre}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent
