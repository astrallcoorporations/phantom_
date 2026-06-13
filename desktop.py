"""
phantom_ — desktop app.

A native window (Windows WebView2 / macOS WKWebView / Linux GTK) wrapping
phantom. By default it loads your deployed site, so everything — Phantom AI,
E2E messaging, calls, file sharing — works with no local setup. Calls work
because WebView2 supports getUserMedia / WebRTC.

    python desktop.py                 # opens the deployed app in a window
    set PHANTOM_URL=http://127.0.0.1:5000 && python desktop.py   # local server

Build a standalone Phantom.exe (Windows):
    build_desktop.bat                 # -> dist\\Phantom\\Phantom.exe
"""

import os
import threading
import time

import webview

# Where the window points. Override with the PHANTOM_URL env var.
DEPLOYED_URL = "https://phantom-git-main-arsh7.vercel.app"
URL = (os.getenv("PHANTOM_URL") or DEPLOYED_URL).rstrip("/")

# Pointing at localhost spins up the Flask server in-process (full local app).
_local = URL.startswith("http://127.0.0.1") or URL.startswith("http://localhost")


def _serve_local():
    from app import app
    tail = URL.split("//", 1)[-1]
    port = int(tail.rsplit(":", 1)[-1]) if ":" in tail else 5000
    app.run(port=port, debug=False, use_reloader=False)


def main():
    if _local:
        threading.Thread(target=_serve_local, daemon=True).start()
        time.sleep(1.2)  # let Flask bind before the window opens

    webview.create_window(
        "Phantom",
        URL,
        width=1180,
        height=780,
        min_size=(940, 600),
        background_color="#080808",
        text_select=True,
    )
    # private_mode=False keeps localStorage (your keys, drafts) between runs.
    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
