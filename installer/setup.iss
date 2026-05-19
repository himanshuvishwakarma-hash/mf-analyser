; Z1N MF Analyser - Inno Setup script
; Build with Inno Setup 6.x: ISCC.exe installer\setup.iss
; Output: installer\Output\Z1NMFAnalyser-Setup-v2.0.0.exe

#define AppName       "Z1N MF Analyser"
#define AppShortName  "Z1NMFAnalyser"
#define AppVersion    "2.0.0"
#define AppPublisher  "Z1N Capital"
#define AppURL        "https://z1ncapital.in"

[Setup]
AppId={{6F2C8B9E-4D5A-4F7B-9C3E-7B1D2E3F4A5B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/support
AppUpdatesURL={#AppURL}/releases
DefaultDirName={localappdata}\{#AppShortName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=Z1NMFAnalyser-Setup-v{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; Code signing: sign post-build with signtool (see OPS_RUNBOOK).
; SignTool=signtool

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkablealone
Name: "startupicon";  Description: "Start {#AppName} when Windows starts"; GroupDescription: "Startup behavior:"

[Files]
Source: "tray_launcher\dist\Z1NLauncher.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "payload\docker-compose.yml";          DestDir: "{app}\payload"; Flags: ignoreversion
Source: "payload\.env.template";               DestDir: "{app}\payload"; Flags: ignoreversion; AfterInstall: CreateUserEnvIfMissing
Source: "payload\README.txt";                  DestDir: "{app}\payload"; Flags: ignoreversion
Source: "assets\z1n.ico";                       DestDir: "{app}\assets"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}";              Filename: "{app}\Z1NLauncher.exe"
Name: "{group}\Open Dashboard";          Filename: "http://localhost:5173"
Name: "{group}\Uninstall {#AppName}";    Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";      Filename: "{app}\Z1NLauncher.exe"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";        Filename: "{app}\Z1NLauncher.exe"; Tasks: startupicon

[Run]
; Optional final step: launch the tray app right after install.
Filename: "{app}\Z1NLauncher.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop the compose stack on uninstall (best-effort, no prompt).
Filename: "{cmd}"; Parameters: "/c docker compose -f ""{app}\payload\docker-compose.yml"" down"; Flags: runhidden; RunOnceId: "ComposeDown"

[Code]
function InitializeSetup(): Boolean;
var
  DockerOk: Boolean;
  Resp: Integer;
begin
  Result := True;
  // Detect Docker Desktop: look for docker.exe via PATH (where.exe).
  DockerOk := Exec(ExpandConstant('{cmd}'), '/c where docker >nul 2>nul', '',
                   SW_HIDE, ewWaitUntilTerminated, Resp) and (Resp = 0);
  if not DockerOk then begin
    if MsgBox(
      'Docker Desktop is required but was not detected.' + #13#10 + #13#10 +
      'Click Yes to open the Docker Desktop download page in your browser, ' +
      'then re-run this installer once Docker is installed.',
      mbConfirmation, MB_YESNO) = IDYES then begin
      ShellExec('open', 'https://www.docker.com/products/docker-desktop/', '', '',
                SW_SHOWNORMAL, ewNoWait, Resp);
    end;
    Result := False;
  end;
end;

procedure CreateUserEnvIfMissing;
var
  Src, Dest: string;
begin
  Src  := ExpandConstant('{app}\payload\.env.template');
  Dest := ExpandConstant('{app}\payload\.env');
  if not FileExists(Dest) then begin
    FileCopy(Src, Dest, False);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Resp: Integer;
begin
  if CurUninstallStep = usUninstall then begin
    if MsgBox(
      'Also remove all downloaded fund data and the local database?' + #13#10 +
      'Choose No to keep the data for a future re-install.',
      mbConfirmation, MB_YESNO) = IDYES then begin
      Exec(ExpandConstant('{cmd}'),
           '/c docker compose -f "' + ExpandConstant('{app}\payload\docker-compose.yml') +
           '" down -v', '', SW_HIDE, ewWaitUntilTerminated, Resp);
    end;
  end;
end;
