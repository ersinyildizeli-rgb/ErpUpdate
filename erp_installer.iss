#define MyAppName "Personel Yönetimi"
#define MyAppVersion "1.0.85"
#define MyAppPublisher "Ender Celik"
#define MyAppExeName "ErpBackend.exe"
#define MyIconFile "F:\cursor\endercelik\icon\erp_icon.ico"

[Setup]
AppId={{2E9261CA-DF10-4A49-9CFE-7713A5E6A4E3}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
SetupIconFile={#MyIconFile}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=PersonelYonetimiSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=yes
AppMutex=ErpBackendMutex
SetupMutex=PersonelYonetimiSetupMutex
RestartApplications=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Default.isl"

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Programı zorla kapat
  Exec('taskkill.exe', '/f /im ' + '{#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

[Files]
Source: "dist\ErpBackend\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion restartreplace uninsrestartdelete

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent
