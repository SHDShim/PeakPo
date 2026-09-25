#ifndef MyAppVersion
  #error MyAppVersion must be supplied to ISCC
#endif

#define ProjectRoot AddBackslash(SourcePath) + "..\.."
#define AppSource ProjectRoot + "\dist\PeakPo"
#define ReleaseDir ProjectRoot + "\release"
#define AppIcon ProjectRoot + "\peakpo\assets\PeakPo.ico"

[Setup]
AppId={{49F23A41-6351-4E3E-BE7F-1DEBCDB80794}
AppName=PeakPo
AppVersion={#MyAppVersion}
AppPublisher=S.-H. Dan Shim
AppPublisherURL=https://github.com/SHDShim/PeakPo
DefaultDirName={localappdata}\Programs\PeakPo
DefaultGroupName=PeakPo
DisableProgramGroupPage=yes
OutputDir={#ReleaseDir}
OutputBaseFilename=PeakPo-{#MyAppVersion}-windows-x86_64-setup
SetupIconFile={#AppIcon}
UninstallDisplayIcon={app}\PeakPo.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PeakPo"; Filename: "{app}\PeakPo.exe"
Name: "{autodesktop}\PeakPo"; Filename: "{app}\PeakPo.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PeakPo.exe"; Description: "Launch PeakPo"; Flags: nowait postinstall skipifsilent
