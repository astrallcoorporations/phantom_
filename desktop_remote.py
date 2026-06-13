"""Phantom desktop (remote) — thin native window over the deployed site.
No backend bundled, so the download stays small."""
import os
import webview

URL = (os.getenv("PHANTOM_URL") or "https://phantom-git-main-arsh7.vercel.app").rstrip("/")

webview.create_window("Phantom", URL, width=1180, height=780,
                      min_size=(940, 600), background_color="#080808", text_select=True)
webview.start(private_mode=False)
