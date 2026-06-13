@echo off
REM Build a standalone Phantom.exe (Windows). Run from the project root.
pip install pywebview pyinstaller
pyinstaller --noconfirm --windowed --name Phantom ^
  --icon static\img\phantom.ico ^
  --collect-all webview ^
  desktop.py
echo.
echo Done. Your app is at  dist\Phantom\Phantom.exe
echo (zip the dist\Phantom folder to share it)
