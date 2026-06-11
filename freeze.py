"""Freeze phantom_ into a static site for Netlify.

Renders every page as a guest into dist/, copies static assets, and writes
the Netlify redirects. The Phantom AI endpoint is served by a Netlify
Function (netlify/functions/assistant.mts) — everything else runs on the
localStorage backend.

    python freeze.py
"""

import shutil
from pathlib import Path

from app import app

DIST = Path("dist")

PAGES = {
    "/": "index.html",
    "/auth": "auth/index.html",
    "/onboarding": "onboarding/index.html",
    "/app": "app/index.html",
    "/app/messages": "app/messages/index.html",
    "/app/messages/ai": "app/messages/ai/index.html",
    "/app/messages/local-template": "app/messages/local-template/index.html",
    "/app/messages/dm-template": "app/messages/dm-template/index.html",
    "/app/spaces": "app/spaces/index.html",
    "/app/moments": "app/moments/index.html",
    "/app/people": "app/people/index.html",
    "/app/calls": "app/calls/index.html",
    "/app/media": "app/media/index.html",
    "/app/settings": "app/settings/index.html",
}

REDIRECTS = """\
/app/messages/local-*  /app/messages/local-template/index.html  200
/app/messages/dm-*     /app/messages/dm-template/index.html     200
/auth/guest            /onboarding                              302
/auth/google           /auth                                    302
/logout                /                                        302
"""


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    app.config["FREEZE"] = True
    client = app.test_client()

    for route, target in PAGES.items():
        resp = client.get(route)
        assert resp.status_code == 200, f"{route} -> {resp.status_code}"
        out = DIST / target
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(resp.data)
        print(f"  {route:38s} -> {target}")

    shutil.copytree("static", DIST / "static")
    (DIST / "_redirects").write_text(REDIRECTS)
    print("static assets copied, redirects written — dist/ ready")


if __name__ == "__main__":
    main()
