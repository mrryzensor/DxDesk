; ==============================================================================
; Script de Inno Setup para crear el instalador oficial de DxDesk
; ==============================================================================

#define MyAppName "DxDesk"
#ifndef MyAppVersion
#define MyAppVersion "1.5.0"
#endif
#ifndef MyAppBuildDate
#define MyAppBuildDate "1970-01-01 00:00"
#endif
#define MyAppPublisher "DxDesk"
#define MyAppExeName "DxDesk.exe"
#define MyAppAssocName MyAppName + " Remote Desktop"

[Setup]
AppId={{E380B41C-8D57-48BC-96E6-8E383845496B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=DxDesk-Setup
SetupIconFile=..\assets\dxdesk.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; DxDesk's Windows client reads the machine-wide Inno uninstall key to detect
; that this is an installed copy and to enable service/UAC integration.
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "output\RustDesk2.toml"; DestDir: "{userappdata}\RustDesk\config"; Flags: ignoreversion onlyifdoesntexist

; Keep the installer metadata in the same uninstall key that the client
; checks. Without BuildDate, every installed copy is incorrectly reported as
; an older version because an empty registry value compares lower than the
; build date embedded in the executable.
[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{E380B41C-8D57-48BC-96E6-8E383845496B}_is1"; ValueType: string; ValueName: "BuildDate"; ValueData: "{#MyAppBuildDate}"; Flags: uninsdeletevalue

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
