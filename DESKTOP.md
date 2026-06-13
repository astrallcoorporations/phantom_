# Phantom — desktop apps

Two ways to run Phantom as a native desktop app. Both wrap your deployed
site, so AI, encryption, calls, and files all work with no extra setup.

## 1. pywebview (ready now — no extra toolchain)

Run it:
    python desktop.py

Build a standalone .exe:
    build_desktop.bat          ->  dist\Phantom\Phantom.exe   (~21 MB)

Point it at a local server instead of the deployed site:
    set PHANTOM_URL=http://127.0.0.1:5000
    python desktop.py

## 2. Tauri (tiny native bundle — needs Rust once)

Tauri produces a much smaller installer (~3-6 MB) and a true native shell.
It needs the Rust toolchain (one-time install):

    1. Install Rust:  https://win.rustup.rs  (run rustup-init.exe, accept defaults)
    2. build_tauri.bat
       -> phantom-tauri\src-tauri\target\release\bundle\  (.msi + .exe installer)

Dev mode (hot window):
    cd phantom-tauri && npm run tauri dev

The window URL lives in  phantom-tauri\src-tauri\tauri.conf.json  (app.windows[0].url).
Change it to your production domain when you have one.
