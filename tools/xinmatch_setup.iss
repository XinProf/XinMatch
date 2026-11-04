; XinMatch 3.3.0 single-file installer (Inno Setup 6).
; Since v3.0.0 the default reference library IS bundled: the portable tree
; built by tools/build_exe.ps1 carries COD-Inorg-<snapshot>.xinDB under
; {app}\data\ (v3 columnar .xinDB), so search works right after install.
; Additional .xinDB libraries can be mounted from any folder via
; 设置→参考数据库… or `xinmatch libraries --add <path>`.

[Setup]
AppId={{8E4D2B90-1F3C-4A5E-9C21-7B6A0F3D5E41}
AppName=XinMatch
AppVersion=3.3.0
AppVerName=XinMatch 3.3.0
AppPublisher=XinMatch Contributors
AppPublisherURL=https://github.com/PolyXRD/XinMatch
AppSupportURL=https://github.com/PolyXRD/XinMatch
AppComments=Open-source powder XRD phase analysis platform
DefaultDirName={autopf}\XinMatch
SetupIconFile=..\assets\icons\logo.ico
DefaultGroupName=XinMatch
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\XinMatch.exe
UninstallDisplayName=XinMatch 3.3.0
OutputDir=..\dist
OutputBaseFilename=XinMatch-Setup-3.3.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
SetupLogging=yes
VersionInfoVersion=3.3.0
VersionInfoCompany=XinMatch Contributors
VersionInfoDescription=XinMatch 3.3.0 installer
VersionInfoProductName=XinMatch
VersionInfoProductVersion=3.3.0
VersionInfoOriginalFilename=XinMatch-Setup-3.3.0.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\xinmatch-3.3.0\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\XinMatch"; Filename: "{app}\XinMatch.exe"
Name: "{group}\Uninstall XinMatch"; Filename: "{uninstallexe}"
Name: "{autodesktop}\XinMatch"; Filename: "{app}\XinMatch.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\XinMatch.exe"; Description: "{cm:LaunchProgram,XinMatch}"; Flags: postinstall nowait skipifsilent
