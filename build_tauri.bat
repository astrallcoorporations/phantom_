@echo off
REM Build Phantom.exe with Tauri (tiny native bundle). Run from project root.
where cargo >/dev/null 2>/dev/null
if errorlevel 1 (
  echo Rust is required for Tauri. Install it once:
  echo   https://win.rustup.rs   ^(download + run rustup-init.exe, accept defaults^)
  echo Then re-run this script.
  exit /b 1
)
cd phantom-tauri
call npm install
call npm run tauri build
echo.
echo Done. Installer is in  phantom-tauri\src-tauri\target\release\bundle\
