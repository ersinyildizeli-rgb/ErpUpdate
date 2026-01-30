#define MyAppName "ERP Uygulaması"
#define MyAppVersion "1.0"
#define MyAppPublisher "Şirket Adı"
#define MyAppExeName "erp_uygulamasi.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-47H8-I9J0-K1L2M3N4O5P6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=.
OutputBaseFilename=ERP_Kurulum
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "f:\cursor\endercelik\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\app.py"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\app.py"; Tasks: desktopicon

[Run]
Filename: "{app}\app.py"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent