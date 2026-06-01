; Z1N MF Analyser - Inno Setup script
; Build with Inno Setup 6.x: ISCC.exe installer\setup.iss
; Output: installer\Output\Z1NMFAnalyser-Setup-v2.0.0.exe

#define AppName       "Z1N MF Analyser"
#define AppShortName  "Z1NMFAnalyser"
#define AppVersion    "3.0.1"
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
Name: "{userdesktop}\{#AppName}";      Filename: "{app}\Z1NLauncher.exe"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";        Filename: "{app}\Z1NLauncher.exe"; Tasks: startupicon

[Run]
; Pre-pull Docker images so first launch is instant (vs 5-10 min download).
; Best-effort: if Docker is not running yet, the launcher will pull on first start.
Filename: "{cmd}"; Parameters: "/c docker compose -f ""{app}\payload\docker-compose.yml"" pull"; \
  Description: "Pre-download data service images (about 5 minutes)"; \
  StatusMsg: "Downloading data service images... (one-time, takes about 5 minutes)"; \
  Flags: runhidden waituntilterminated
; Final step: launch the tray app right after install.
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
  Lines, Filtered: TArrayOfString;
  I, NewLen: Integer;
  Trimmed: string;
begin
  Src  := ExpandConstant('{app}\payload\.env.template');
  Dest := ExpandConstant('{app}\payload\.env');
  if not FileExists(Dest) then begin
    FileCopy(Src, Dest, False);
    Exit;
  end;
  // Upgrade path: existing .env from older install may pin APP_VERSION=2.0.0
  // (which no longer exists on GHCR). Strip any non-comment APP_VERSION line
  // so compose's :latest default kicks in.
  if LoadStringsFromFile(Dest, Lines) then begin
    NewLen := 0;
    SetArrayLength(Filtered, 0);
    for I := 0 to GetArrayLength(Lines) - 1 do begin
      Trimmed := Trim(Lines[I]);
      SetArrayLength(Filtered, NewLen + 1);
      if Copy(Trimmed, 1, 12) = 'APP_VERSION=' then
        Filtered[NewLen] := '# APP_VERSION removed by installer upgrade (defaults to :latest)'
      else
        Filtered[NewLen] := Lines[I];
      NewLen := NewLen + 1;
    end;
    SaveStringsToFile(Dest, Filtered, False);
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
