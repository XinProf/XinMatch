; XinMatch 1.7.0 single-file installer (Inno Setup 6).
; The COD reference DB (~512 MB) is intentionally NOT bundled — it ships as a
; separate archive (xinmatch-cod-db-1.7.0.zip).  After install, extract that
; archive into the install directory so the DB lands at
; {app}\data\cod_inorganics.db — auto-resolved by multi_db.default_db_path()
; when the app runs frozen.

[Setup]
AppId={{8E4D2B90-1F3C-4A5E-9C21-7B6A0F3D5E41}
AppName=XinMatch
AppVersion=1.7.0
AppVerName=XinMatch 1.7.0
AppPublisher=XinMatch Contributors
AppPublisherURL=https://github.com/PolyXRD/XinMatch
AppSupportURL=https://github.com/PolyXRD/XinMatch
AppComments=Open-source powder XRD phase analysis platform
DefaultDirName={autopf}\XinMatch
DefaultGroupName=XinMatch
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\XinMatch.exe
UninstallDisplayName=XinMatch 1.7.0
OutputDir=..\dist
OutputBaseFilename=XinMatch-Setup-1.7.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
SetupLogging=yes
VersionInfoVersion=1.7.0
VersionInfoCompany=XinMatch Contributors
VersionInfoDescription=XinMatch 1.7.0 installer
VersionInfoProductName=XinMatch
VersionInfoProductVersion=1.7.0
VersionInfoOriginalFilename=XinMatch-Setup-1.7.0.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\xinmatch-1.7.0\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\XinMatch"; Filename: "{app}\XinMatch.exe"
Name: "{group}\Uninstall XinMatch"; Filename: "{uninstallexe}"
Name: "{autodesktop}\XinMatch"; Filename: "{app}\XinMatch.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\XinMatch.exe"; Description: "{cm:LaunchProgram,XinMatch}"; Flags: postinstall nowait skipifsilent
