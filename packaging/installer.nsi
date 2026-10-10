; =========================================================================
; G-Mirror Windows x64 NSIS Installer Script
; =========================================================================

!define PRODUCT_NAME "G-Mirror"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "G-Mirror Contributors"
!define PRODUCT_WEB_SITE "https://github.com/gmirror-app/gmirror"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\GMirror.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

; MUI 1.67 compatible ------
!include "MUI.nsh"

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\icons\gmirror.ico"
!define MUI_UNICON "..\assets\icons\gmirror.ico"

; Welcome page
!insertmacro MUI_PAGE_WELCOME
; Directory page
!insertmacro MUI_PAGE_DIRECTORY
; Instfiles page
!insertmacro MUI_PAGE_INSTFILES
; Finish page
!define MUI_FINISHPAGE_RUN "$INSTDIR\GMirror.exe"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_INSTFILES

; Language files
!insertmacro MUI_LANGUAGE "English"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "..\dist\GMirror-Setup-${PRODUCT_VERSION}-x64.exe"
InstallDir "$PROGRAMFILES64\G-Mirror"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show

Section "MainSection" SEC01
  SetOutPath "$INSTDIR"
  SetOverwrite ifnewer
  File /r "..\dist\GMirror\*.*"

  ; Create Start Menu Shortcuts
  CreateDirectory "$SMPROGRAMS\G-Mirror"
  CreateShortcut "$SMPROGRAMS\G-Mirror\G-Mirror.lnk" "$INSTDIR\GMirror.exe" "" "$INSTDIR\assets\icons\gmirror.ico"
  CreateShortcut "$DESKTOP\G-Mirror.lnk" "$INSTDIR\GMirror.exe" "" "$INSTDIR\assets\icons\gmirror.ico"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\GMirror.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\GMirror.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
SectionEnd

Function un.onUninstSuccess
  HideWindow
  MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) was successfully removed from your computer."
FunctionEnd

Function un.onInit
  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely remove $(^Name) and all of its components?" IDYES +2
  Abort
FunctionEnd

Section Uninstall
  Delete "$DESKTOP\G-Mirror.lnk"
  Delete "$SMPROGRAMS\G-Mirror\G-Mirror.lnk"
  RMDir "$SMPROGRAMS\G-Mirror"

  RMDir /r "$INSTDIR"

  DeleteRegKey HKLM "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
  SetAutoClose true
SectionEnd
