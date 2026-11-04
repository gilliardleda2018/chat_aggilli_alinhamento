; ============================================================================
; Instalador Windows do Video Builder Pro - Aggilli Intelligence (Inno Setup 6)
;
; Compilar (feito pelo GitHub Actions; manualmente, a partir desta pasta):
;   iscc /DAppVersion=7.8 instalador_windows.iss
; Pre-requisitos: ..\dist\VideoBuilderPro\ (PyInstaller) e ..\assets\gerados\
; (python gerar_icones.py). Saida: ..\dist\instalador\VideoBuilderPro-Setup-<versao>.exe
;
; Decisoes:
;  - Instala por usuario, SEM pedir administrador (PrivilegesRequired=lowest);
;    quem quiser instalar para todos escolhe na tela inicial (dialogo de override).
;  - FFmpeg vem embutido em {app}\_internal\bin: nao depende do PATH do sistema.
;  - Configuracoes, chave da API e logs ficam em %USERPROFILE%\.video_builder_pro
;    e NAO sao apagados na desinstalacao (reinstalar mantem tudo).
; ============================================================================

#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#define AppName "Video Builder Pro"
#define AppPublisher "Aggilli Intelligence"
#define AppExe "VideoBuilderPro.exe"

[Setup]
; AppId fixo: identifica o programa em atualizacoes. NAO alterar.
AppId={{6E1C7F2A-9B4D-4E8C-A1F5-2D7B3C9E4A60}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=Copyright (C) {#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalador do {#AppName}
DefaultDirName={autopf}\Aggilli\{#AppName}
DefaultGroupName=Aggilli\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\instalador
OutputBaseFilename=VideoBuilderPro-Setup-{#AppVersion}
SetupIconFile=..\assets\gerados\icone.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}
WizardStyle=modern
WizardImageFile=..\assets\gerados\assistente_grande.bmp,..\assets\gerados\assistente_grande_2x.bmp
WizardSmallImageFile=..\assets\gerados\assistente_pequeno.bmp,..\assets\gerados\assistente_pequeno_2x.bmp
WizardImageStretch=no
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\VideoBuilderPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Pasta de logs e configuracoes"; Filename: "{%USERPROFILE}\.video_builder_pro"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
