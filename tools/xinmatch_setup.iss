; XinMatch single-file installer (Inno Setup 6).
; Since v3.0.0 the default reference library IS bundled: the portable tree
; built by tools/build_exe.ps1 carries COD-Inorg-<snapshot>.xinDB under
; {app}\data\ (v3 columnar .xinDB), so search works right after install.
; Additional .xinDB libraries can be mounted from any folder via
; 设置→参考数据库… or `xinmatch libraries --add <path>`.
;
; 版本号：只有一个真相源 = pyproject.toml 的 [project] version。这里的 AppVersion
; 是**默认值**，构建脚本用 `ISCC /DAppVersion=<ver> /DDistDir=<ver>` 覆盖；
; tests/test_version_consistency.py 会校验这个默认值与 pyproject 逐字相同，
; 并且禁止文件里再出现字面版本号（历史上这里曾有 10 处各写一遍而漂移）。

#define AppName "XinMatch"
; 构建脚本用 /DAppVersion= 覆盖；不使用覆盖时以此默认值为准（须与 pyproject 同步）
#ifndef AppVersion
#define AppVersion "3.8.0"
#endif

[Setup]
AppId={{8E4D2B90-1F3C-4A5E-9C21-7B6A0F3D5E41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=XinMatch Contributors
AppPublisherURL=https://github.com/XinProf/XinMatch
AppSupportURL=https://github.com/XinProf/XinMatch
AppComments=Open-source powder XRD phase analysis platform
DefaultDirName={autopf}\XinMatch
SetupIconFile=..\assets\icons\logo.ico
DefaultGroupName=XinMatch
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\XinMatch.exe
UninstallDisplayName={#AppName} {#AppVersion}
OutputDir=..\dist
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
SetupLogging=yes
VersionInfoVersion={#AppVersion}
VersionInfoCompany=XinMatch Contributors
VersionInfoDescription={#AppName} {#AppVersion} installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoOriginalFilename={#AppName}-Setup-{#AppVersion}.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 便携树目录名同样由版本号决定（tools/build_exe.ps1 -Version / 默认读 pyproject），
; 由构建脚本用 /DDistDir= 覆盖成实际路径，避免「版本 bump 了但这里没改」。
#ifndef DistDir
#define DistDir "..\dist\xinmatch-" + AppVersion
#endif
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\XinMatch"; Filename: "{app}\XinMatch.exe"
Name: "{group}\Uninstall XinMatch"; Filename: "{uninstallexe}"
Name: "{autodesktop}\XinMatch"; Filename: "{app}\XinMatch.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\XinMatch.exe"; Description: "{cm:LaunchProgram,XinMatch}"; Flags: postinstall nowait skipifsilent
