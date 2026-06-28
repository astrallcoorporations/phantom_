"""
phantom_ — private conversations. nothing else.

Flask server backed by Supabase: real profiles (incl. guests), spaces with
membership / visibility / theme, and persisted messages you can read back,
delete, and search. Gemini powers the Phantom AI assistant.
"""

from __future__ import annotations

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import (Flask, abort, g, jsonify, redirect, render_template, request,
                   session, url_for)
import re
try:
    from flask_compress import Compress
except ImportError:
    Compress = None
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

GEMINI_API_KEY = (os.getenv("gemini_api_key") or "").strip()
SUPABASE_URL = (os.getenv("supabase_url") or os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("supabase_key") or os.getenv("SUPABASE_KEY") or "").strip()
GOOGLE_CLIENT_ID = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
GOOGLE_CLIENT_SECRET = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
GITHUB_CLIENT_ID = (os.getenv("GITHUB_CLIENT_ID") or "").strip()
GITHUB_CLIENT_SECRET = (os.getenv("GITHUB_CLIENT_SECRET") or "").strip()
TURN_URLS = (os.getenv("TURN_URLS") or os.getenv("turn_urls") or "").strip()
TURN_USERNAME = (os.getenv("TURN_USERNAME") or os.getenv("turn_username") or "").strip()
TURN_CREDENTIAL = (os.getenv("TURN_CREDENTIAL") or os.getenv("turn_credential") or os.getenv("TURN_PASSWORD") or os.getenv("turn_password") or "").strip()
PUBLIC_URL = (os.getenv("PUBLIC_URL") or "").strip().rstrip("/")

OWNER_EMAIL = "animedevelopment58@gmail.com"
ADMIN_HANDLE = "totoandhenry"
ADMIN_FIRST_PASSWORD = "phantom-admin"
# Emails that automatically get owner/admin rights (e.g. on Google sign-in)
ADMIN_EMAILS = {"animedevelopment58@gmail.com"}


def is_admin_identity(handle=None, email=None):
    return (handle and handle == ADMIN_HANDLE) or (email and email.lower() in ADMIN_EMAILS)

app = Flask(__name__)
app.secret_key = (os.getenv("flask_secret_key") or "").strip() or "phantom-dev-key"
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000
app.config["JSON_SORT_KEYS"] = False
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False
# Stay logged in: persistent session cookie that survives browser/app restarts
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=180)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if Compress:
    Compress(app)
# Behind Vercel's proxy — trust the forwarded host/proto so OAuth redirects
# and url_for(_external=True) build https://<your-domain> correctly.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

_supabase = None


def sb():
    global _supabase
    if _supabase is None and SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def sb_insert(table, row):
    try:
        c = sb()
        if c:
            c.table(table).insert(row).execute()
    except Exception:
        pass


_io_pool = ThreadPoolExecutor(max_workers=8)


def run_parallel(**tasks):
    """Run independent, request-context-free DB reads concurrently.
    Each task is a zero-arg callable that must NOT touch flask.session/g
    (those are thread-local). Returns {name: result}."""
    futs = {k: _io_pool.submit(v) for k, v in tasks.items()}
    return {k: f.result() for k, f in futs.items()}


def sb_rows(query_fn, default=None):
    """Run a read, returning .data or a default on any failure."""
    try:
        c = sb()
        if not c:
            return default if default is not None else []
        return query_fn(c).execute().data or (default if default is not None else [])
    except Exception:
        return default if default is not None else []


def find_profile(identity):
    c = sb()
    if not c:
        return None
    ident = (identity or "").strip().lstrip("@").lower()
    if not ident:
        return None
    cache = getattr(g, "_pcache", None)
    if cache is None:
        cache = g._pcache = {}
    if ident in cache:
        return cache[ident]
    found = None
    for col in ("handle", "email"):
        try:
            r = c.table("profiles").select("*").eq(col, ident).limit(1).execute()
            if r.data:
                found = r.data[0]
                break
        except Exception:
            continue
    cache[ident] = found
    if found:
        cache[found.get("handle")] = found
    return found


def _load_space_members(space_ids):
    cache = getattr(g, "_space_member_sets", {})
    if not isinstance(space_ids, (list, tuple, set)):
        space_ids = [space_ids]
    missing = [sid for sid in space_ids if sid and sid not in cache]
    if missing:
        rows = sb_rows(lambda c: c.table("space_members")
                       .select("space_id, handle").in_("space_id", missing))
        for sid in missing:
            cache[sid] = set()
        for r in rows:
            cache.setdefault(r["space_id"], set()).add(r["handle"])
        g._space_member_sets = cache
    return cache


def space_member_count(space_id):
    return len(_load_space_members(space_id).get(space_id, set()))


def is_member(space_id, handle):
    if not handle:
        return False
    return handle in _load_space_members(space_id).get(space_id, set())


def get_space(space_id):
    cache = getattr(g, "_space_cache", {})
    if space_id in cache:
        return cache[space_id]
    rows = sb_rows(lambda c: c.table("spaces").select("*").eq("id", space_id).limit(1))
    space = rows[0] if rows else None
    cache[space_id] = space
    g._space_cache = cache
    return space


def profiles_by_handles(handles):
    """One query for many handles -> {handle: profile}."""
    handles = [h for h in {h for h in handles} if h]
    if not handles:
        return {}
    rows = sb_rows(lambda c: c.table("profiles")
                   .select("handle, display_name, public_key, status, is_admin, is_guest")
                   .in_("handle", handles))
    return {r["handle"]: r for r in rows}


# ---------------------------------------------------------------------------
# Gemini — Phantom AI
# ---------------------------------------------------------------------------

ASSISTANT_SYSTEM = (
    "You are Phantom AI, the built-in assistant of phantom_ — a private, "
    "minimal messaging app. Voice: calm, concise, helpful, a little quiet. "
    "Answer plainly in a few short sentences unless asked for depth. "
    "Never use emoji. If asked about phantom problems, troubleshoot step by "
    f"step; the owner can be reached at {OWNER_EMAIL}."
)

_gemini = None


def gemini_client():
    global _gemini
    if _gemini is None and GEMINI_API_KEY:
        from google import genai
        _gemini = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini


# ---------------------------------------------------------------------------
# Atmospheres (HD, web-sourced) and skins
# ---------------------------------------------------------------------------

ATMOSPHERES = {
    "moon-horizon": {"label": "Moon Horizon", "src": "img/web/moon.jpg"},
    "deep-space":   {"label": "Deep Space",   "src": "img/web/milkyway.jpg"},
    "frozen-peaks": {"label": "Frozen Peaks", "src": "img/web/ridge.jpg"},
    "black-ocean":  {"label": "Black Ocean",  "src": "img/web/ocean.jpg"},
    "cloud-sea":    {"label": "Cloud Sea",    "src": "img/web/valley.jpg"},
    "orbit":        {"label": "Orbit",        "src": "img/web/orbit.jpg"},
    "nebula":       {"label": "Nebula",       "src": "img/web/nebula.jpg"},
    "starfield":    {"label": "Starfield",    "src": "img/web/stars.jpg"},
    "fog":          {"label": "Fog",          "src": "img/web/fog.jpg"},
    "night":        {"label": "Night",        "src": "img/web/night.jpg"},
    "glass-desert": {"label": "Glass Desert", "src": "img/atm/glass-desert.jpg"},
    "glass-cube":   {"label": "Glass Cube",   "src": "img/atm/glass-cube.jpg"},
    "halo":         {"label": "Halo",         "src": "img/atm/halo.jpg"},
    "dark-ridge":   {"label": "Dark Ridge",   "src": "img/atm/dark-ridge.jpg"},
}
SKINS = ["dark", "light", "midnight", "glass"]  # + "system", resolved client-side

MEDIA = [
    {"src": a["src"], "title": a["label"], "kind": "image",
     "source": "atmosphere", "atmosphere": key}
    for key, a in ATMOSPHERES.items()
]

LANGUAGES = ["en", "hi", "es", "fr", "de", "ja", "ar"]

TROUBLESHOOT = [
    {"q": "Phantom AI says it isn't connected",
     "a": "Set GEMINI_API_KEY in your environment (Vercel → Settings → Environment Variables, or .env for local) and redeploy. Free keys: aistudio.google.com/apikey."},
    {"q": "Gemini replies 'busy right now'",
     "a": "Google's servers are briefly overloaded (503). Phantom retries two fallback models — wait a few seconds and send again."},
    {"q": "My messages disappeared",
     "a": "Signed-in and guest messages persist in Supabase and reload anywhere. Conversations marked 'on this device only' live in your browser's localStorage."},
    {"q": "Can't sign in with Google",
     "a": "Google sign-in needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET set, and your exact callback URL (https://your-domain/auth/google/callback) registered as an Authorized redirect URI in Google Cloud Console."},
    {"q": "Adding a person says 'no one found'",
     "a": "You can only add people who have a phantom account. Type their full username and press Enter to search."},
    {"q": "A private space isn't visible to someone",
     "a": "Private spaces only appear to members. Open the space, use Add member to invite them by username."},
]


# ---------------------------------------------------------------------------
# Session / users
# ---------------------------------------------------------------------------

def current_user():
    return session.get("user")


def user_handle(user=None):
    user = user or current_user() or {}
    return (user.get("handle") or "").lstrip("@").lower()


def login_as(profile):
    session.permanent = True          # persist across browser/app restarts
    admin = bool(profile.get("is_admin")) or is_admin_identity(profile.get("handle"), profile.get("email"))
    # promote known admin emails/handles in the DB too, so it sticks
    if admin and not profile.get("is_admin"):
        try:
            sb().table("profiles").update({"is_admin": True}).eq("handle", profile["handle"]).execute()
        except Exception:
            pass
    session["user"] = {
        "handle": "@" + profile["handle"],
        "name": profile.get("display_name") or profile["handle"],
        "email": profile.get("email") or "",
        "admin": admin,
        "guest": bool(profile.get("is_guest")),
    }


@app.after_request
def _cache_static(resp):
    p = request.path
    if p.startswith("/static/"):
        if p.rsplit(".", 1)[-1].lower() in ("jpg", "jpeg", "png", "webp", "ico", "mp4", "woff", "woff2", "svg"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"   # heavy, stable assets
        else:
            resp.headers["Cache-Control"] = "public, max-age=300"                   # css/js: short, revalidate
    elif p == "/":
        # "/" redirects signed-in users into the app, so it must run per-request
        # (not CDN-cached). Anonymous render is still fast (region-pinned + light).
        resp.headers["Cache-Control"] = "no-store"
    elif p in ("/docs", "/download"):
        resp.headers["Cache-Control"] = "public, max-age=300, s-maxage=86400, stale-while-revalidate=604800"
        resp.headers["Vary"] = "Accept-Encoding"
    elif p in ("/manifest.webmanifest", "/.well-known/assetlinks.json"):
        resp.headers["Cache-Control"] = "public, max-age=86400"  # stable manifest links
    return resp


@app.before_request
def guard_app():
    if app.config.get("FREEZE"):
        return None
    if request.path.startswith("/app") and not current_user():
        return redirect(url_for("auth"))
    return None


# ---------------------------------------------------------------------------
# Spaces
# ---------------------------------------------------------------------------

def space_member_count(space_id):
    rows = sb_rows(lambda c: c.table("space_members").select("handle").eq("space_id", space_id))
    return len(rows)


def is_member(space_id, handle):
    rows = sb_rows(lambda c: c.table("space_members").select("handle")
                   .eq("space_id", space_id).eq("handle", handle).limit(1))
    return bool(rows)


def get_space(space_id):
    rows = sb_rows(lambda c: c.table("spaces").select("*").eq("id", space_id).limit(1))
    return rows[0] if rows else None


def user_spaces(handle):
    """Spaces the user belongs to, newest first."""
    mem = sb_rows(lambda c: c.table("space_members").select("space_id, role").eq("handle", handle))
    if not mem:
        return []
    ids = [m["space_id"] for m in mem]
    roles = {m["space_id"]: m["role"] for m in mem}
    rows = sb_rows(lambda c: c.table("spaces").select("*").in_("id", ids))
    allmem = sb_rows(lambda c: c.table("space_members").select("space_id").in_("space_id", ids))
    counts = {}
    for m in allmem:
        counts[m["space_id"]] = counts.get(m["space_id"], 0) + 1
    for r in rows:
        r["role"] = roles.get(r["id"], "member")
        r["members"] = counts.get(r["id"], 0)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows


def public_spaces(exclude_handle=None, limit=12):
    rows = sb_rows(lambda c: c.table("spaces").select("*").eq("visibility", "public")
                   .order("created_at", desc=True).limit(limit))
    out = []
    member_sets = _load_space_members([r["id"] for r in rows])
    for r in rows:
        if exclude_handle and exclude_handle in member_sets.get(r["id"], set()):
            continue
        r["members"] = len(member_sets.get(r["id"], set()))
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Conversations & messages
# ---------------------------------------------------------------------------

def dm_storage_id(a, b):
    return "dm:" + "__".join(sorted([a, b]))


def resolve_conversation(conv_id, user):
    """Map a URL conv_id to a storage id + metadata + access decision."""
    handle = user_handle(user)
    if not conv_id:
        return None
    if conv_id == "ai":
        return {"sid": f"ai:{handle}", "type": "ai", "title": "Phantom AI",
                "sub": "your private assistant", "atmosphere": "night",
                "skin": None, "allowed": True, "deletable": True}
    if conv_id.startswith("dm-"):
        other = conv_id[3:].lstrip("@").lower()
        prof = find_profile(other)
        return {"sid": dm_storage_id(handle, other), "type": "dm",
                "title": (prof or {}).get("display_name") or other,
                "sub": "@" + other, "atmosphere": "halo", "skin": None,
                "peer": other, "allowed": bool(prof), "deletable": True}
    if conv_id.startswith("space-"):
        sid = conv_id[6:]
        sp = get_space(sid)
        if not sp:
            return None
        allowed = sp.get("visibility") == "public" or is_member(sid, handle)
        return {"sid": f"space:{sid}", "type": "space", "title": sp["name"],
                "sub": f"{space_member_count(sid)} members",
                "atmosphere": sp.get("atmosphere") or "moon-horizon",
                "skin": sp.get("skin") or "dark", "space": sp,
                "allowed": allowed, "deletable": sp.get("owner") == handle}
    if conv_id.startswith("local-"):
        return {"sid": conv_id, "type": "local",
                "title": request.args.get("t", "New conversation"),
                "sub": "on this device only", "atmosphere": "dark-ridge",
                "skin": None, "allowed": True, "local": True, "deletable": True}
    return None


def load_messages(sid, me):
    rows = sb_rows(lambda c: c.table("messages").select("*")
                   .eq("conversation_id", sid).order("created_at", desc=False).limit(500))
    clr = cleared_at(me, sid) if me else 0.0
    out, expired = [], []
    now = time.time()
    for r in rows:
        meta = r.get("meta") or {}
        if meta.get("expires") and float(meta["expires"]) < now:
            expired.append(r["id"])
            continue
        if clr and r.get("created_at"):
            try:
                from datetime import datetime as _dt
                ts = _dt.fromisoformat(r["created_at"].replace("Z", "+00:00")).timestamp()
                if ts < clr:
                    continue
            except Exception:
                pass
        out.append({
            "id": r["id"], "author": r["author"], "body": r["body"],
            "kind": r.get("kind") or "text", "meta": meta,
            "mine": (r["author"] == me) or (r["author"] == "me"),
        })
    if expired:  # ghost messages burn on read
        try:
            sb().table("messages").delete().in_("id", expired).execute()
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

def cleared_at(handle, sid):
    rows = sb_rows(lambda c: c.table("convo_clears").select("cleared_at")
                   .eq("handle", handle).eq("conversation_id", sid).limit(1))
    return float(rows[0]["cleared_at"]) if rows else 0.0


def _iso_ts(s):
    """ISO-8601 string -> epoch seconds (0.0 on failure)."""
    if not s:
        return 0.0
    try:
        from datetime import datetime as _dt
        return _dt.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def user_dms(handle):
    """Every DM the user has. Tags each with `request`: True when it's an
    incoming message from someone you don't know and haven't replied to."""
    if not handle:
        return []
    rows = sb_rows(lambda c: c.table("messages").select("conversation_id, body, kind, author, created_at, meta")
                   .like("conversation_id", "dm:%").order("created_at", desc=True).limit(400))
    contacts = set(cr["contact"] for cr in
                   sb_rows(lambda c: c.table("contacts").select("contact").eq("owner", handle)))
    clears = {}
    for r in sb_rows(lambda c: c.table("convo_clears").select("conversation_id, cleared_at").eq("handle", handle)):
        try:
            clears[r["conversation_id"]] = float(r["cleared_at"])
        except Exception:
            pass
    seen, i_authored = {}, set()       # newest row wins (rows come desc); track DMs I've spoken in
    for r in rows:
        sid = r["conversation_id"]
        parts = sid[3:].split("__")
        if handle not in parts or len(parts) != 2:
            continue
        other = parts[0] if parts[1] == handle else parts[1]
        if r.get("author") == handle:
            i_authored.add(other)
        if other in seen:
            continue
        ts_iso = r.get("created_at", "")
        # a declined/cleared request (or cleared stranger chat) stays hidden until they write again
        if other not in contacts and clears.get(sid) and _iso_ts(ts_iso) < clears[sid]:
            seen[other] = None
            continue
        last = "(encrypted)" if (r.get("meta") or {}).get("e2e") else (
            ("file: " + r["body"]) if r.get("kind") in ("file", "image", "system") else r["body"])
        seen[other] = {"handle": other, "last": last[:48], "ts": ts_iso}
    real = {k: v for k, v in seen.items() if v}
    for h in contacts:                 # contacts you added but never messaged
        if h not in seen:
            real[h] = {"handle": h, "last": "", "ts": ""}
    pmap = profiles_by_handles(list(real))
    out = []
    for other, d in real.items():
        d["name"] = (pmap.get(other) or {}).get("display_name") or other
        d["request"] = (other not in contacts) and (other not in i_authored)
        out.append(d)
    out.sort(key=lambda d: d["ts"], reverse=True)
    return out


def greeting():
    h = datetime.now().hour
    return ("Up late" if h < 5 else "Good morning" if h < 12
            else "Good afternoon" if h < 18 else "Good evening")


def base_context(view):
    user = current_user() or {"handle": "@guest", "name": "Guest", "email": "",
                              "admin": False, "guest": True}
    # Sidebar spaces + DMs are independent reads — fetch them concurrently
    # (resolve session-dependent values here, on the request thread, first).
    logged_in = current_user() is not None
    handle = user_handle(user)
    want_dms = logged_in and view in ("messages", "home")
    if logged_in:
        res = run_parallel(
            spaces=(lambda: user_spaces(handle)),
            dms=((lambda: user_dms(handle)) if want_dms else (lambda: [])),
        )
        spaces, dms_all = res["spaces"], res["dms"]
    else:
        spaces, dms_all = [], []
    return {
        "view": view,
        "atmospheres": ATMOSPHERES,
        "skins": SKINS,
        "spaces": spaces,
        "dms": [d for d in dms_all if not d.get("request")],
        "requests": [d for d in dms_all if d.get("request")],
        "conversations": [{"id": "ai", "type": "ai", "title": "Phantom AI",
                           "sub": "your private assistant", "atmosphere": "night"}],
        "ghost": session.get("ghost", False),
        "lang": session.get("lang", "en"),
        "ai_ready": bool(GEMINI_API_KEY),
        "sb_ready": bool(SUPABASE_URL and SUPABASE_KEY),
        "sb_url": SUPABASE_URL,
        "sb_anon": SUPABASE_KEY,
        "google_ready": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "owner_email": OWNER_EMAIL,
        "troubleshoot": TROUBLESHOOT,
        "user": user,
        "my_handle": user_handle(user),
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def landing():
    if current_user():                     # already signed in → straight into the app
        return redirect(url_for("home"))
    ua = (request.headers.get('User-Agent') or '')
    mobile_re = re.compile(r'Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini', re.I)
    if mobile_re.search(ua):
        return render_template("landing_mobile.html", lang=session.get("lang", "en"),
                               user=current_user())
    return render_template("landing.html", lang=session.get("lang", "en"),
                           user=current_user())


@app.route("/docs")
def docs():
    return render_template("docs.html", lang=session.get("lang", "en"))


# --- PWA: manifest + service worker (served from root for full scope) ---

@app.route("/manifest.webmanifest")
def manifest():
    base = url_for("static", filename="img")
    manifest = {
        "name": "Phantom", "short_name": "Phantom",
        "description": "Private, encrypted messaging, calls and spaces.",
        "start_url": "/app", "scope": "/", "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#15120e", "theme_color": "#15120e",
        "categories": ["social", "communication"],
        "icons": [
            {"src": base + "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": base + "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": base + "/icon-192-maskable.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": base + "/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    android_pkg = os.getenv("ANDROID_PACKAGE")
    android_fps = [f.strip() for f in (os.getenv("ANDROID_FINGERPRINTS") or "").split(",") if f.strip()]
    if android_pkg and android_fps:
        manifest["related_applications"] = [{
            "platform": "play",
            "url": f"https://play.google.com/store/apps/details?id={android_pkg}",
            "id": android_pkg,
        }]
        manifest["prefer_related_applications"] = True
    return jsonify(manifest)


@app.route("/sw.js")
def service_worker():
    from flask import Response
    sw = """
const CACHE = 'phantom-v2';
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim())));
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  // stale-while-revalidate for static: instant from cache, refresh in background
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(caches.open(CACHE).then((c) =>
      c.match(e.request).then((hit) => {
        const net = fetch(e.request).then((r) => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => hit);
        return hit || net;
      })));
  } else {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
  }
});
"""
    resp = Response(sw, mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/.well-known/assetlinks.json")
def assetlinks():
    # Digital Asset Links — paste your PWABuilder/Play SHA-256 fingerprint(s) into
    # the ANDROID_FINGERPRINTS env var (comma-separated) to verify the TWA.
    fps = [f.strip() for f in (os.getenv("ANDROID_FINGERPRINTS") or "").split(",") if f.strip()]
    return jsonify([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app",
                   "package_name": os.getenv("ANDROID_PACKAGE") or "chat.phantom.twa",
                   "sha256_cert_fingerprints": fps},
    }])


DOWNLOAD_WIN = (SUPABASE_URL + "/storage/v1/object/public/files/downloads/Phantom-windows.exe") if SUPABASE_URL else "#"


@app.route("/download/windows")
def download_windows():
    if not DOWNLOAD_WIN:
        return redirect(url_for("download"))
    import requests as rq
    from flask import Response
    try:
        upstream = rq.get(DOWNLOAD_WIN, stream=True, timeout=20)
        if upstream.status_code != 200:
            return redirect(DOWNLOAD_WIN)
        headers = {
            "Content-Type": upstream.headers.get("content-type", "application/octet-stream"),
            "Content-Disposition": "attachment; filename=Phantom-windows.exe",
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        }
        return Response(upstream.iter_content(chunk_size=8192), headers=headers)
    except Exception:
        return redirect(DOWNLOAD_WIN)


@app.route("/download")
def download():
    return render_template("download.html", lang=session.get("lang", "en"),
                           win_url=url_for("download_windows"), user=current_user())


@app.route("/auth")
def auth():
    return render_template("auth.html", lang=session.get("lang", "en"),
                           google_ready=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
                           error=request.args.get("error"))


@app.route("/auth/guest")
def auth_guest():
    handle = "guest-" + uuid.uuid4().hex[:6]
    profile = {"handle": handle, "display_name": "Guest " + handle[-4:],
               "is_guest": True, "theme": "moon-horizon"}
    sb_insert("profiles", profile)
    login_as(profile)
    return redirect(url_for("onboarding"))


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("landing"))


@app.route("/onboarding")
def onboarding():
    return render_template("onboarding.html", lang=session.get("lang", "en"),
                           atmospheres=ATMOSPHERES)


@app.route("/app")
def home():
    ctx = base_context("home")
    ctx["greeting"] = greeting()
    ctx["explore"] = public_spaces(ctx["my_handle"], limit=4)
    return render_template("home.html", **ctx)


@app.route("/app/messages")
@app.route("/app/messages/<conv_id>")
def messages(conv_id=None):
    ctx = base_context("messages")
    conv = resolve_conversation(conv_id, ctx["user"]) if conv_id else None
    if conv:
        conv["id"] = conv_id
    if conv and conv.get("allowed") and not conv.get("local"):
        msgs = load_messages(conv["sid"], ctx["my_handle"])
        if conv["type"] == "ai" and not msgs:
            msgs = [{"id": "seed", "author": "ai", "mine": False, "kind": "text",
                     "meta": {}, "body": "Hello. I'm Phantom AI — ask me anything, it stays between us."}]
        conv["messages"] = msgs
        # right info panel: peer profile + recent shared media
        if conv["type"] == "dm" and conv.get("peer"):
            conv["peer_profile"] = find_profile(conv["peer"])
        conv["media"] = [m for m in msgs if m["kind"] in ("file", "image")][-4:]
    elif conv:
        conv["messages"] = []
        conv["media"] = []
    ctx["active"] = conv
    return render_template("messages.html", **ctx)


@app.route("/app/spaces")
def spaces_view():
    ctx = base_context("spaces")
    ctx["explore"] = public_spaces(ctx["my_handle"])
    return render_template("spaces.html", **ctx)


def recent_moments(hours=24, limit=60):
    """Everyone's moments from the last `hours` hours, newest first, with author."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    rows = sb_rows(lambda c: c.table("moments").select("*")
                   .gte("created_at", cutoff).order("created_at", desc=True).limit(limit))
    pmap = profiles_by_handles([r.get("author") for r in rows if r.get("author")])
    out = []
    for r in rows:
        prof = pmap.get(r.get("author")) or {}
        r["author_name"] = prof.get("display_name") or r.get("author") or "someone"
        out.append(r)
    return out


@app.route("/app/moments")
def moments_view():
    ctx = base_context("moments")
    ctx["moments"] = recent_moments()
    return render_template("moments.html", **ctx)


@app.post("/api/moments")
def api_moment_create():
    user = current_user()
    if not user:
        return jsonify({"error": "Sign in to post a moment."}), 401
    d = request.json or {}
    note = (d.get("note") or "").strip()[:500]
    media_url = (d.get("media_url") or "").strip()[:600]
    if not note and not media_url:
        return jsonify({"error": "Write something or add a photo."}), 400
    atmosphere = d.get("atmosphere") if d.get("atmosphere") in ATMOSPHERES else "glass-cube"
    row = {"author": user_handle(user), "title": (user.get("name") or "")[:60],
           "note": note, "media_url": media_url, "atmosphere": atmosphere,
           "kind": "image" if media_url else "text"}
    try:
        res = sb().table("moments").insert(row).execute()
        new = (res.data or [row])[0]
    except Exception as exc:
        return jsonify({"error": str(exc)[:160]}), 500
    new["author_name"] = user.get("name") or user_handle(user)
    return jsonify({"ok": True, "moment": new}), 201


@app.delete("/api/moments/<mid>")
def api_moment_delete(mid):
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    rows = sb_rows(lambda c: c.table("moments").select("author").eq("id", mid).limit(1))
    if rows and rows[0].get("author") not in (user_handle(user), None) and not user.get("admin"):
        return jsonify({"error": "You can only delete your own moments."}), 403
    try:
        sb().table("moments").delete().eq("id", mid).execute()
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/app/people")
def people_view():
    ctx = base_context("people")
    contacts = []
    me = ctx["my_handle"]
    rows = sb_rows(lambda c: c.table("contacts").select("contact").eq("owner", me))
    handles = [r["contact"] for r in rows]
    if handles:
        contacts = sb_rows(lambda c: c.table("profiles")
                           .select("handle, display_name, is_admin, is_guest").in_("handle", handles))
    ctx["contacts"] = contacts
    return render_template("people.html", **ctx)


@app.route("/app/calls")
def calls_view():
    ctx = base_context("calls")
    return render_template("calls.html", **ctx)


# ---------------------------------------------------------------------------
# Apps — a marketplace where people publish HTML/CSS/JS (and in-browser
# Python via Pyodide) apps & games. Sandboxed iframe play; optional realtime
# multiplayer via the injected Phantom SDK. Admin approves submissions.
# ---------------------------------------------------------------------------

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return (s or "app")[:40]


def get_app(slug):
    rows = sb_rows(lambda c: c.table("apps").select("*").eq("slug", slug).limit(1))
    return rows[0] if rows else None


def list_apps(status="approved", author=None, limit=80):
    def q(c):
        sel = c.table("apps").select(
            "id, slug, title, tagline, author, kind, plays, status, created_at")
        if status:
            sel = sel.eq("status", status)
        if author:
            sel = sel.eq("author", author)
        return sel.order("created_at", desc=True).limit(limit)
    return sb_rows(q) or []


@app.route("/app/apps")
def apps_view():
    ctx = base_context("apps")
    ctx["apps"] = list_apps("approved")
    ctx["pending"] = list_apps("pending") if ctx["user"].get("admin") else []
    ctx["mine"] = (list_apps(status=None, author=ctx["my_handle"], limit=40)
                   if current_user() else [])
    return render_template("apps.html", **ctx)


@app.route("/app/apps/new")
def apps_new():
    if not current_user():
        return redirect(url_for("auth"))
    return render_template("app_submit.html", **base_context("apps"))


@app.route("/app/apps/<slug>")
def app_play(slug):
    ctx = base_context("apps")
    a = get_app(slug)
    if not a:
        abort(404)
    if a["status"] != "approved" and not ctx["user"].get("admin") and a["author"] != ctx["my_handle"]:
        abort(403)
    ctx["app"] = a
    return render_template("app_play.html", **ctx)


@app.post("/api/apps")
def api_app_create():
    user = current_user()
    if not user:
        return jsonify({"error": "Sign in to publish an app."}), 401
    d = request.json or {}
    title = (d.get("title") or "").strip()[:60]
    code = d.get("code") or ""
    kind = d.get("kind") if d.get("kind") in ("html", "python") else "html"
    if not title:
        return jsonify({"error": "Give your app a title."}), 400
    if not code.strip():
        return jsonify({"error": "Add your app's code."}), 400
    if len(code) > 400000:
        return jsonify({"error": "App is too large (400 KB max)."}), 400
    slug = slugify(title) + "-" + uuid.uuid4().hex[:5]
    row = {"slug": slug, "title": title, "tagline": (d.get("tagline") or "").strip()[:120],
           "author": user_handle(user), "kind": kind, "code": code, "status": "pending"}
    try:
        sb().table("apps").insert(row).execute()
    except Exception as exc:
        return jsonify({"error": str(exc)[:160]}), 500
    return jsonify({"ok": True, "slug": slug})


@app.post("/api/apps/<aid>/approve")
def api_app_approve(aid):
    user = current_user()
    if not user or not user.get("admin"):
        return jsonify({"error": "Admins only."}), 403
    try:
        sb().table("apps").update({"status": "approved"}).eq("id", aid).execute()
    except Exception as exc:
        return jsonify({"error": str(exc)[:160]}), 500
    return jsonify({"ok": True})


@app.post("/api/apps/<aid>/reject")
def api_app_reject(aid):
    user = current_user()
    if not user or not user.get("admin"):
        return jsonify({"error": "Admins only."}), 403
    try:
        sb().table("apps").update({"status": "rejected"}).eq("id", aid).execute()
    except Exception:
        pass
    return jsonify({"ok": True})


@app.delete("/api/apps/<aid>")
def api_app_delete(aid):
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    rows = sb_rows(lambda c: c.table("apps").select("author").eq("id", aid).limit(1))
    if rows and rows[0]["author"] != user_handle(user) and not user.get("admin"):
        return jsonify({"error": "You can only delete your own apps."}), 403
    try:
        sb().table("apps").delete().eq("id", aid).execute()
    except Exception:
        pass
    return jsonify({"ok": True})


@app.post("/api/apps/<aid>/play")
def api_app_play(aid):
    rows = sb_rows(lambda c: c.table("apps").select("plays").eq("id", aid).limit(1))
    if rows:
        try:
            sb().table("apps").update({"plays": (rows[0].get("plays") or 0) + 1}).eq("id", aid).execute()
        except Exception:
            pass
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Call signaling — Supabase Realtime handles the WebRTC messages client-side.
# These endpoints let the server ring a specific user via their personal channel,
# and log call history for the sidebar.
# ---------------------------------------------------------------------------

@app.post("/api/calls/ring")
def api_ring():
    """
    Signal a call-offer to a specific peer via their personal Supabase channel.
    The caller's browser does WebRTC directly; this is just the ring notification.
    Body: { to, convId, callType, offer }
    """
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    data = request.json or {}
    to       = (data.get("to") or "").strip().lstrip("@")
    conv_id  = (data.get("convId") or "").strip()
    call_type = data.get("callType", "voice")
    if not to or not conv_id:
        return jsonify({"error": "missing to or convId"}), 400
    me = user_handle(user)
    # Log to call history table if available
    try:
        sb().table("call_history").insert({
            "caller": me, "callee": to, "conv_id": conv_id,
            "call_type": call_type, "status": "ringing",
        }).execute()
    except Exception:
        pass
    # The actual WebRTC offer is passed client-side via Supabase Realtime broadcast.
    return jsonify({"ok": True, "from": me})


@app.post("/api/calls/end")
def api_call_end():
    """Log a call as ended (optional — clients handle hang-up via signaling)."""
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    data   = request.json or {}
    conv_id = (data.get("convId") or "").strip()
    me      = user_handle(user)
    try:
        sb().table("call_history") \
            .update({"status": "ended", "ended_at": datetime.utcnow().isoformat()}) \
            .eq("caller", me).eq("conv_id", conv_id).eq("status", "ringing") \
            .execute()
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/app/media")
def media_view():
    ctx = base_context("media")
    ctx["media"] = MEDIA
    return render_template("media.html", **ctx)


@app.route("/app/settings")
def settings_view():
    return render_template("settings.html", **base_context("settings"))


@app.route("/app/profile")
@app.route("/app/u/<handle>")
def profile_view(handle=None):
    ctx = base_context("profile")
    me = ctx["my_handle"]
    target = (handle or me).lstrip("@").lower()
    profile = find_profile(target)
    if not profile:
        profile = {"handle": target, "display_name": ctx["user"]["name"],
                   "status": "", "tags": [], "theme": "moon-horizon",
                   "is_admin": ctx["user"]["admin"], "is_guest": ctx["user"]["guest"],
                   "created_at": ""}
    their_spaces = user_spaces(target)
    if target == me:
        shared = their_spaces
    else:
        shared = [s for s in their_spaces
                  if s.get("visibility") == "public" or is_member(s["id"], me)]
    contacts_n = len(sb_rows(lambda c: c.table("contacts").select("contact").eq("owner", target)))
    is_contact = bool(sb_rows(lambda c: c.table("contacts").select("id")
                              .eq("owner", me).eq("contact", target).limit(1)))
    ctx.update({
        "profile": profile,
        "own": target == me,
        "shared_spaces": shared,
        "contacts_n": contacts_n,
        "is_contact": is_contact,
        "joined": (profile.get("created_at") or "")[:10],
    })
    return render_template("profile.html", **ctx)


@app.post("/api/profile")
def api_profile_update():
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    data = request.json or {}
    patch = {}
    if "status" in data:
        patch["status"] = str(data.get("status") or "")[:80]
    if "tags" in data:
        tags = [str(t)[:24] for t in (data.get("tags") or []) if str(t).strip()][:8]
        patch["tags"] = tags
    if "display_name" in data and str(data.get("display_name") or "").strip():
        patch["display_name"] = str(data["display_name"]).strip()[:40]
    if "theme" in data and data.get("theme") in ATMOSPHERES:
        patch["theme"] = data["theme"]
    if "public_key" in data and str(data.get("public_key") or "").strip():
        patch["public_key"] = str(data["public_key"]).strip()[:128]
    if not patch:
        return jsonify({"error": "nothing to update"}), 400
    try:
        sb().table("profiles").update(patch).eq("handle", user_handle(user)).execute()
    except Exception as exc:
        return jsonify({"error": str(exc)[:160]}), 500
    if "display_name" in patch:
        session["user"]["name"] = patch["display_name"]
        session.modified = True
    return jsonify({"ok": True, **patch})


# ---------------------------------------------------------------------------
# Auth APIs
# ---------------------------------------------------------------------------

@app.post("/api/signup")
def api_signup():
    data = request.json or {}
    username = (data.get("username") or "").strip().lstrip("@").lower()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not username or not email or len(password) < 6:
        return jsonify({"error": "Username, email and a 6+ character password are required."}), 400
    if not sb():
        return jsonify({"error": "Cloud profiles need Supabase keys configured."}), 503
    if find_profile(username):
        return jsonify({"error": "That username is taken."}), 409
    if find_profile(email):
        return jsonify({"error": "That email already has an account."}), 409
    profile = {"handle": username, "display_name": data.get("name") or username,
               "email": email, "password_hash": generate_password_hash(password),
               "is_admin": is_admin_identity(username, email)}
    try:
        sb().table("profiles").insert(profile).execute()
    except Exception as exc:
        return jsonify({"error": f"Could not create the account: {exc}"}), 500
    login_as(profile)
    return jsonify({"ok": True, "handle": "@" + username})


@app.post("/api/login")
def api_login():
    data = request.json or {}
    identity = (data.get("identity") or "").strip()
    password = data.get("password") or ""
    if not identity or not password:
        return jsonify({"error": "Enter your username or email, and your password."}), 400
    profile = find_profile(identity)
    if not profile:
        return jsonify({"error": "No account found for that username or email."}), 404
    stored = profile.get("password_hash")
    if not stored and profile["handle"] == ADMIN_HANDLE:
        if password != ADMIN_FIRST_PASSWORD:
            return jsonify({"error": "Wrong password."}), 401
        try:
            sb().table("profiles").update({"password_hash": generate_password_hash(password)}) \
                .eq("handle", ADMIN_HANDLE).execute()
        except Exception:
            pass
    elif not stored or not check_password_hash(stored, password):
        return jsonify({"error": "Wrong password."}), 401
    login_as(profile)
    return jsonify({"ok": True, "handle": "@" + profile["handle"], "admin": bool(profile.get("is_admin"))})


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def google_redirect_uri():
    if PUBLIC_URL:
        return PUBLIC_URL + "/auth/google/callback"
    return url_for("google_callback", _external=True)


@app.route("/auth/google")
def google_auth():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        return redirect(url_for("auth", error="Google sign-in needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."))
    params = {"client_id": GOOGLE_CLIENT_ID, "redirect_uri": google_redirect_uri(),
              "response_type": "code", "scope": "openid email profile",
              "prompt": "select_account"}
    return redirect(GOOGLE_AUTH_URL + "?" + urlencode(params))


@app.route("/auth/google/callback")
def google_callback():
    import requests as rq
    code = request.args.get("code")
    if not code:
        return redirect(url_for("auth", error="Google sign-in was cancelled."))
    try:
        token = rq.post(GOOGLE_TOKEN_URL, data={
            "code": code, "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code"}, timeout=15).json()
        if "access_token" not in token:
            return redirect(url_for("auth", error="Google rejected the sign-in (check client secret + redirect URI)."))
        info = rq.get(GOOGLE_USERINFO_URL,
                      headers={"Authorization": "Bearer " + token["access_token"]}, timeout=15).json()
    except Exception:
        return redirect(url_for("auth", error="Google sign-in failed — check credentials."))
    email = (info.get("email") or "").lower()
    if not email:
        return redirect(url_for("auth", error="Google did not return an email."))
    profile = find_profile(email)
    if not profile:
        handle = email.split("@")[0].replace(".", "")[:24] or ("g" + uuid.uuid4().hex[:8])
        if find_profile(handle):
            handle += uuid.uuid4().hex[:4]
        profile = {"handle": handle, "display_name": info.get("name") or handle,
                   "email": email, "is_admin": is_admin_identity(handle, email)}
        sb_insert("profiles", profile)
    login_as(profile)
    return redirect(url_for("home"))


@app.route("/auth/github")
def github_auth():
    if not (GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET):
        return redirect(url_for("auth", error="GitHub sign-in needs GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in the environment."))
    params = {"client_id": GITHUB_CLIENT_ID,
              "redirect_uri": (PUBLIC_URL + "/auth/github/callback") if PUBLIC_URL
              else url_for("github_callback", _external=True),
              "scope": "read:user user:email"}
    return redirect("https://github.com/login/oauth/authorize?" + urlencode(params))


@app.route("/auth/github/callback")
def github_callback():
    import requests as rq
    code = request.args.get("code")
    if not code:
        return redirect(url_for("auth", error="GitHub sign-in was cancelled."))
    try:
        token = rq.post("https://github.com/login/oauth/access_token",
                        data={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET,
                              "code": code},
                        headers={"Accept": "application/json"}, timeout=15).json()
        gh = rq.get("https://api.github.com/user",
                    headers={"Authorization": "Bearer " + token["access_token"]}, timeout=15).json()
        emails = rq.get("https://api.github.com/user/emails",
                        headers={"Authorization": "Bearer " + token["access_token"]}, timeout=15).json()
        email = next((e["email"] for e in emails if e.get("primary")), gh.get("email") or "")
    except Exception:
        return redirect(url_for("auth", error="GitHub sign-in failed — check credentials."))
    handle = (gh.get("login") or "").lower() or ("gh" + uuid.uuid4().hex[:8])
    profile = find_profile(email) or find_profile(handle)
    if not profile:
        if find_profile(handle):
            handle += uuid.uuid4().hex[:4]
        profile = {"handle": handle, "display_name": gh.get("name") or handle,
                   "email": (email or "").lower() or None, "is_admin": is_admin_identity(handle, email)}
        sb_insert("profiles", profile)
    login_as(profile)
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# People APIs
# ---------------------------------------------------------------------------

@app.get("/api/users/find")
def api_users_find():
    q = (request.args.get("q") or "").strip().lstrip("@").lower()
    if len(q) < 2:
        return jsonify({"results": []})
    me = user_handle()
    rows = sb_rows(lambda c: c.table("profiles").select("handle, display_name, is_admin, is_guest")
                   .ilike("handle", f"%{q}%").limit(10))
    return jsonify({"results": [r for r in rows if r["handle"] != me]})


@app.post("/api/contacts")
def api_contacts_add():
    user = current_user()
    if not user:
        return jsonify({"error": "Sign in to add people."}), 401
    contact = ((request.json or {}).get("contact") or "").strip().lstrip("@").lower()
    if not contact:
        return jsonify({"error": "No username given."}), 400
    if not find_profile(contact):
        return jsonify({"error": "No one found with that username."}), 404
    sb_insert("contacts", {"owner": user_handle(user), "contact": contact})
    return jsonify({"ok": True, "contact": "@" + contact})


@app.delete("/api/contacts/<handle>")
def api_contacts_remove(handle):
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    try:
        sb().table("contacts").delete().eq("owner", user_handle(user)) \
            .eq("contact", handle.lstrip("@").lower()).execute()
    except Exception:
        pass
    return jsonify({"ok": True})


@app.post("/api/dm")
def api_dm():
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    other = ((request.json or {}).get("handle") or "").strip().lstrip("@").lower()
    if not find_profile(other):
        return jsonify({"error": "No one found with that username."}), 404
    return jsonify({"ok": True, "conv_id": "dm-" + other})


# ---------------------------------------------------------------------------
# Spaces APIs
# ---------------------------------------------------------------------------

@app.post("/api/spaces")
def api_space_create():
    user = current_user()
    if not user:
        return jsonify({"error": "Sign in to create a space."}), 401
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Give your space a name."}), 400
    if len(name) > 40:
        name = name[:40]
    atmosphere = data.get("atmosphere") if data.get("atmosphere") in ATMOSPHERES else "moon-horizon"
    skin = data.get("skin") if data.get("skin") in SKINS else "dark"
    visibility = "private" if data.get("visibility") == "private" else "public"
    me = user_handle(user)
    sid = "sp-" + uuid.uuid4().hex[:10]
    space = {"id": sid, "name": name[:40], "atmosphere": atmosphere, "skin": skin,
             "visibility": visibility, "tagline": (data.get("tagline") or "")[:80],
             "owner": me, "created_by": me}
    try:
        sb().table("spaces").insert(space).execute()
        sb().table("space_members").insert({"space_id": sid, "handle": me, "role": "owner"}).execute()
    except Exception as exc:
        return jsonify({"error": f"Could not create the space: {exc}"}), 500
    # invite members by username (only real accounts)
    added = []
    for raw in (data.get("members") or [])[:30]:
        h = (raw or "").strip().lstrip("@").lower()
        if h and h != me and find_profile(h):
            sb_insert("space_members", {"space_id": sid, "handle": h, "role": "member"})
            added.append(h)
    return jsonify({"ok": True, "id": sid, "conv_id": "space-" + sid, "added": added})


@app.post("/api/spaces/<sid>/join")
def api_space_join(sid):
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    sp = get_space(sid)
    if not sp:
        return jsonify({"error": "no such space"}), 404
    if sp.get("visibility") != "public" and not is_member(sid, user_handle(user)):
        return jsonify({"error": "This space is private."}), 403
    sb_insert("space_members", {"space_id": sid, "handle": user_handle(user), "role": "member"})
    return jsonify({"ok": True, "conv_id": "space-" + sid})


@app.post("/api/spaces/<sid>/members")
def api_space_add_member(sid):
    user = current_user()
    sp = get_space(sid)
    if not sp:
        return jsonify({"error": "no such space"}), 404
    if not user or sp.get("owner") != user_handle(user):
        return jsonify({"error": "Only the space owner can add members."}), 403
    h = ((request.json or {}).get("username") or "").strip().lstrip("@").lower()
    if not find_profile(h):
        return jsonify({"error": "No one found with that username."}), 404
    sb_insert("space_members", {"space_id": sid, "handle": h, "role": "member"})
    return jsonify({"ok": True, "added": "@" + h})


@app.delete("/api/spaces/<sid>")
def api_space_delete(sid):
    user = current_user()
    sp = get_space(sid)
    if not sp:
        return jsonify({"ok": True})
    me = user_handle(user)
    if not user or (sp.get("owner") != me and not (user or {}).get("admin")):
        return jsonify({"error": "Only the owner can delete this space."}), 403
    try:
        sb().table("messages").delete().eq("conversation_id", f"space:{sid}").execute()
        sb().table("spaces").delete().eq("id", sid).execute()  # cascades members
    except Exception as exc:
        return jsonify({"error": str(exc)[:160]}), 500
    return jsonify({"ok": True})


@app.post("/api/spaces/<sid>/leave")
def api_space_leave(sid):
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    try:
        sb().table("space_members").delete().eq("space_id", sid) \
            .eq("handle", user_handle(user)).execute()
    except Exception:
        pass
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Messages APIs
# ---------------------------------------------------------------------------

@app.get("/api/conversations/<conv_id>/messages")
def api_messages_get(conv_id):
    conv = resolve_conversation(conv_id, current_user())
    if not conv or not conv.get("allowed") or conv.get("local"):
        return jsonify({"messages": []})
    return jsonify({"messages": load_messages(conv["sid"], user_handle())})


@app.post("/api/conversations/<conv_id>/messages")
def send_message(conv_id):
    data = request.json or {}
    body = (data.get("body") or "").strip()
    kind = data.get("kind") if data.get("kind") in ("text", "file", "image", "voice", "system") else "text"
    meta = data.get("meta") or {}
    if not body:
        return jsonify({"error": "empty message"}), 400
    if kind == "text" and not meta.get("e2e") and len(body) > 4000:
        body = body[:4000]
    conv = resolve_conversation(conv_id, current_user())
    if not conv or not conv.get("allowed"):
        return jsonify({"error": "no access to this conversation"}), 403
    if conv.get("local"):
        return jsonify({"id": "local", "ok": True})  # stays client-side
    me = user_handle() or "me"
    row = {"conversation_id": conv["sid"], "author": me, "body": body,
           "kind": kind, "meta": meta}
    try:
        res = sb().table("messages").insert(row).execute()
        new_id = (res.data or [{}])[0].get("id")
    except Exception:
        new_id = uuid.uuid4().hex
    return jsonify({"id": new_id, "author": me, "body": body, "kind": kind, "meta": meta}), 201


@app.delete("/api/messages/<mid>")
def api_message_delete(mid):
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    rows = sb_rows(lambda c: c.table("messages").select("author").eq("id", mid).limit(1))
    if rows and rows[0]["author"] not in (user_handle(user), "me") and not user.get("admin"):
        return jsonify({"error": "You can only delete your own messages."}), 403
    try:
        sb().table("messages").delete().eq("id", mid).execute()
    except Exception:
        pass
    return jsonify({"ok": True})


@app.post("/api/conversations/<conv_id>/clear-request")
def api_clear_request(conv_id):
    conv = resolve_conversation(conv_id, current_user())
    if not conv or not conv.get("allowed") or conv.get("type") != "dm":
        return jsonify({"error": "clear-for-both only applies to direct messages"}), 400
    me = user_handle()
    # one pending request at a time
    try:
        sb().table("messages").delete().eq("conversation_id", conv["sid"])             .contains("meta", {"action": "clear_request"}).execute()
    except Exception:
        pass
    sb_insert("messages", {"conversation_id": conv["sid"], "author": me,
                           "body": "clear_request", "kind": "system",
                           "meta": {"action": "clear_request", "by": me}})
    return jsonify({"ok": True})


@app.delete("/api/conversations/<conv_id>")
def api_conversation_clear(conv_id):
    conv = resolve_conversation(conv_id, current_user())
    if not conv:
        return jsonify({"ok": True})
    scope = request.args.get("scope", "me")
    me = user_handle()
    if scope == "everyone":
        try:
            sb().table("messages").delete().eq("conversation_id", conv["sid"]).execute()
        except Exception:
            pass
    else:  # clear for me only — record a per-user marker
        try:
            sb().table("convo_clears").upsert({
                "handle": me, "conversation_id": conv["sid"], "cleared_at": time.time(),
            }).execute()
        except Exception:
            pass
    return jsonify({"ok": True})


@app.post("/api/assistant")
def assistant():
    data = request.json or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    if not message:
        return jsonify({"error": "empty message"}), 400
    me = user_handle() or "me"
    sid = f"ai:{me}"

    if not GEMINI_API_KEY:
        return jsonify({"reply": (
            "I'm not connected yet. Set GEMINI_API_KEY in your environment and redeploy. "
            "Keys are free at aistudio.google.com/apikey."), "offline": True})

    contents = []
    for turn in history[-20:]:
        role = "model" if turn.get("role") == "ai" else "user"
        text = (turn.get("text") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    last_error = None
    for model in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"):
        try:
            resp = gemini_client().models.generate_content(
                model=model, contents=contents,
                config={"system_instruction": ASSISTANT_SYSTEM, "temperature": 0.6})
            reply = (resp.text or "").strip() or "…I have nothing to add."
            sb_insert("messages", {"conversation_id": sid, "author": me, "body": message})
            sb_insert("messages", {"conversation_id": sid, "author": "ai", "body": reply})
            return jsonify({"reply": reply, "model": model})
        except Exception as exc:
            last_error = exc
            app.logger.warning("gemini %s failed: %s", model, exc)
    return jsonify({"reply": "Gemini is busy right now — give it a moment and ask again.",
                    "offline": True, "error": str(last_error)[:200]})


@app.get("/api/ice")
def api_ice():
    import requests as rq
    def _clean(v):
        return (v or "").strip().strip('"').strip("'").strip()
    dom = _clean(os.getenv("METERED_DOMAIN")).replace("https://", "").replace("http://", "").strip("/")
    key = _clean(os.getenv("METERED_API_KEY"))
    debug = request.args.get("debug")
    diag = {"domain_present": bool(dom), "key_present": bool(key), "tried": [], "ok": False}

    # Cloudflare TURN — the recommended free relay (1000 GB/mo). Generates
    # short-lived credentials per call. Set CF_TURN_KEY_ID + CF_TURN_API_TOKEN.
    cf_id = _clean(os.getenv("CF_TURN_KEY_ID"))
    cf_tok = _clean(os.getenv("CF_TURN_API_TOKEN"))
    if cf_id and cf_tok:
        try:
            resp = rq.post(
                f"https://rtc.live.cloudflare.com/v1/turn/keys/{cf_id}/credentials/generate",
                headers={"Authorization": "Bearer " + cf_tok},
                json={"ttl": 86400}, timeout=8)
            diag["tried"].append({"provider": "cloudflare", "status": resp.status_code})
            data = resp.json()
            if resp.ok and data.get("iceServers"):
                diag["ok"] = True
                if debug:
                    return jsonify(diag)
                return jsonify({"iceServers": [data["iceServers"],
                                               {"urls": "stun:stun.l.google.com:19302"}]})
        except Exception as exc:
            diag["tried"].append({"provider": "cloudflare", "error": type(exc).__name__})

    # underscores are invalid in hostnames — also try without it (phantom_.x -> phantom.x)
    candidates = []
    if dom:
        candidates.append(dom)
        if "_" in dom.split(".")[0]:
            candidates.append(dom.split(".")[0].replace("_", "") + "." + ".".join(dom.split(".")[1:]))

    if TURN_URLS:
        turn_servers = []
        for url in [u.strip() for u in re.split(r"[\s,]+", TURN_URLS) if u.strip()]:
            server = {"urls": url}
            if TURN_USERNAME and TURN_CREDENTIAL:
                server["username"] = TURN_USERNAME
                server["credential"] = TURN_CREDENTIAL
            turn_servers.append(server)
        if turn_servers:
            if debug:
                diag["direct_turn"] = True
                diag["turn_servers"] = turn_servers
            return jsonify({"iceServers": [{"urls": "stun:stun.l.google.com:19302"}] + turn_servers})

    if key:
        try:
            import urllib3
            urllib3.disable_warnings()
        except Exception:
            pass
        for d in candidates:
            # underscore hostnames fail Python's TLS hostname check; skip verify
            # for them (safe: WebRTC media is DTLS-encrypted regardless of TURN)
            for verify in ((False,) if "_" in d else (True,)):
                try:
                    resp = rq.get(f"https://{d}/api/v1/turn/credentials?apiKey={key}",
                                  timeout=8, verify=verify)
                    diag["tried"].append({"host": d, "status": resp.status_code, "verify": verify})
                    data = resp.json()
                    if isinstance(data, list) and data:
                        diag["ok"] = True
                        if debug:
                            return jsonify(diag)
                        return jsonify({"iceServers": data})
                except Exception as exc:
                    diag["tried"].append({"host": d, "error": type(exc).__name__, "verify": verify})

    ice = [{"urls": "stun:stun.l.google.com:19302"},
           {"urls": "stun:stun1.l.google.com:19302"},
           {"urls": "turn:openrelay.metered.ca:80", "username": "openrelayproject", "credential": "openrelayproject"},
           {"urls": "turn:openrelay.metered.ca:443", "username": "openrelayproject", "credential": "openrelayproject"},
           {"urls": "turn:openrelay.metered.ca:443?transport=tcp", "username": "openrelayproject", "credential": "openrelayproject"}]
    if debug:
        diag["fallback"] = "openrelay"
        return jsonify(diag)
    return jsonify({"iceServers": ice})


@app.post("/api/ghost")
def toggle_ghost():
    session["ghost"] = bool((request.json or {}).get("enabled"))
    return jsonify({"ghost": session["ghost"]})


@app.post("/api/language")
def set_language():
    lang = (request.json or {}).get("lang", "en")
    if lang not in LANGUAGES:
        return jsonify({"error": "unsupported language"}), 400
    session["lang"] = lang
    return jsonify({"lang": lang})


if __name__ == "__main__":
    app.run(debug=True, port=5000, extra_files=[".env"])