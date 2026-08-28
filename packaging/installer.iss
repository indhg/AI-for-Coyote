[Setup]
AppId={{CoyoteInCradleDesktop}}
AppName=Coyote in Cradle
AppVersion={version}
DefaultDirName={localappdata}\Programs\Coyote in Cradle
DefaultGroupName=Coyote in Cradle
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\Coyote-in-Cradle.exe
Compression=lzma2
SolidCompression=yes
OutputDir={outdir}
OutputBaseFilename=Coyote-in-Cradle-setup-v{version}
DisableProgramGroupPage=yes
WizardStyle=modern
SetupIconFile={pkgdir}\setup.ico
LicenseFile={pkgdir}\说明.txt
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "{pkgdir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{autoprograms}\Coyote in Cradle"; Filename: "{app}\Coyote-in-Cradle.exe"
Name: "{autodesktop}\Coyote in Cradle"; Filename: "{app}\Coyote-in-Cradle.exe"

[Run]
Filename: "{app}\Coyote-in-Cradle.exe"; Description: "启动 Coyote in Cradle"; Flags: nowait postinstall skipifsilent
