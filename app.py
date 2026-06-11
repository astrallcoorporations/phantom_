"""
phantom_ — private conversations. nothing else.

Flask server. Secrets in .env, Gemini for the assistant, Supabase for
profiles / contacts / message mirroring. No trackers, no noise.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import (Flask, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

GEMINI_API_KEY = (os.getenv("gemini_api_key") or "").strip()
SUPABASE_URL = (os.getenv("supabase_url") or "").strip()
SUPABASE_KEY = (os.getenv("supabase_key") or "").strip()
GOOGLE_CLIENT_ID = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
GOOGLE_CLIENT_SECRET = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()

OWNER_EMAIL = "pencil.insurance.buisness@gmail.com"
ADMIN_HANDLE = "totoandhenry"
ADMIN_FIRST_PASSWORD = (os.getenv("admin_first_password") or "phantom-admin").strip()

app = Flask(__name__)
app.secret_key = (os.getenv("flask_secret_key") or "").strip() or "phantom-dev-key"

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

_supabase = None


def supabase():
    global _supabase
    if _supabase is None and SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def sb_insert(table, row):
    """Fire-and-forget cloud mirror; never blocks or breaks the app."""
    try:
        client = supabase()
        if client:
            client.table(table).insert(row).execute()
    except Exception:
        pass


def sb_find_profile(identity):
    """Look a profile up by handle or email. Returns dict or None."""
    client = supabase()
    if not client:
        return None
    ident = identity.strip().lstrip("@").lower()
    for col in ("handle", "email"):
        try:
            resp = client.table("profiles").select("*").eq(col, ident).limit(1).execute()
            if resp.data:
                return resp.data[0]
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Gemini — the Phantom AI assistant
# ---------------------------------------------------------------------------

ASSISTANT_SYSTEM = (
    "You are Phantom AI, the built-in assistant of phantom_ — a private, "
    "minimal messaging app. Voice: calm, concise, helpful, a little quiet. "
    "Answer plainly in a few short sentences unless asked for depth. "
    "Never use emoji. You run locally for this one user; their messages are "
    "private and never used for anything else. If asked about phantom bugs or "
    "problems, walk through them step by step; the owner can be reached at "
    f"{OWNER_EMAIL}."
)

_gemini_client = None


def gemini_client():
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


# ---------------------------------------------------------------------------
# Atmospheres — HD, web-sourced
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

SPACES = {
    "moon-horizon": {"id": "moon-horizon", "name": "Moon Horizon", "atmosphere": "moon-horizon",
                     "tagline": "The quiet default.", "members": 12},
    "developers":   {"id": "developers", "name": "Developers", "atmosphere": "orbit",
                     "tagline": "Build calm software.", "members": 24},
    "study-group":  {"id": "study-group", "name": "Study Group", "atmosphere": "cloud-sea",
                     "tagline": "Focus, together.", "members": 8},
    "design-circle": {"id": "design-circle", "name": "Design Circle", "atmosphere": "glass-desert",
                      "tagline": "Form follows silence.", "members": 15},
    "photography":  {"id": "photography", "name": "Photography", "atmosphere": "frozen-peaks",
                     "tagline": "Light, captured quietly.", "members": 10},
}

EXPLORE_SPACES = [
    {"id": "deep-space-devs", "name": "Deep Space Devs", "atmosphere": "deep-space", "members": "1.2K"},
    {"id": "creative-minds", "name": "Creative Minds", "atmosphere": "nebula", "members": "896"},
    {"id": "tech-enthusiasts", "name": "Tech Enthusiasts", "atmosphere": "starfield", "members": "923"},
]


def _msg(author, body, minutes_ago=0, kind="text", meta=None):
    return {
        "id": uuid.uuid4().hex[:8],
        "author": author,
        "body": body,
        "ts": time.time() - minutes_ago * 60,
        "kind": kind,
        "meta": meta or {},
    }


CONVERSATIONS = {
    "ai": {
        "id": "ai", "type": "ai", "title": "Phantom AI", "atmosphere": "night",
        "sub": "your private assistant",
        "messages": [
            _msg("ai", "Hello. I'm Phantom AI — ask me anything, it stays between us.", 1),
        ],
    },
}

MEDIA = [
    {"src": a["src"], "title": a["label"], "kind": "image",
     "source": "atmosphere", "atmosphere": key}
    for key, a in ATMOSPHERES.items()
]

LANGUAGES = ["en", "hi", "es", "fr", "de", "ja", "ar"]

TROUBLESHOOT = [
    {"q": "Phantom AI says it isn't connected",
     "a": "Open .env in the project folder, paste your key into gemini_api_key=\"\" and restart phantom. Free keys: aistudio.google.com/apikey."},
    {"q": "Gemini replies 'busy right now'",
     "a": "Google's servers are briefly overloaded (503). Phantom already retries two fallback models — wait a few seconds and send again."},
    {"q": "My messages disappeared",
     "a": "Messages live in your browser's localStorage under phantom.db.v1. They vanish if you clear site data or switch browsers. With Supabase keys set, they also mirror to your cloud project."},
    {"q": "Theme or language didn't stick",
     "a": "Preferences save per browser. If localStorage is blocked (private windows sometimes do this), phantom can't remember between visits."},
    {"q": "Can't sign in with Google",
     "a": "Google sign-in needs valid GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env, with http://127.0.0.1:5000/auth/google/callback registered as a redirect URI in Google Cloud Console."},
    {"q": "Adding a person says 'no one found'",
     "a": "You can only add people who have signed up — search by their exact username. Ask them to create an account first."},
]


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def current_user():
    return session.get("user")


@app.before_request
def guard_app():
    if app.config.get("FREEZE"):  # static export renders everything as guest
        return None
    if request.path.startswith("/app") and not current_user():
        return redirect(url_for("auth"))
    return None


def login_as(profile):
    session["user"] = {
        "handle": "@" + profile["handle"],
        "name": profile.get("display_name") or profile["handle"],
        "email": profile.get("email") or "",
        "admin": bool(profile.get("is_admin")),
        "guest": False,
    }


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

def greeting():
    h = datetime.now().hour
    if h < 5:
        return "Up late"
    if h < 12:
        return "Good morning"
    if h < 18:
        return "Good afternoon"
    return "Good evening"


def base_context(view):
    user = current_user() or {"handle": "@guest", "name": "Guest", "email": "", "admin": False, "guest": True}
    return {
        "view": view,
        "atmospheres": ATMOSPHERES,
        "spaces": SPACES,
        "explore_spaces": EXPLORE_SPACES,
        "conversations": list(CONVERSATIONS.values()),
        "ghost": session.get("ghost", False),
        "lang": session.get("lang", "en"),
        "ai_ready": bool(GEMINI_API_KEY),
        "sb_ready": bool(SUPABASE_URL and SUPABASE_KEY),
        "owner_email": OWNER_EMAIL,
        "troubleshoot": TROUBLESHOOT,
        "user": user,
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def landing():
    return render_template("landing.html", lang=session.get("lang", "en"))


@app.route("/auth")
def auth():
    return render_template("auth.html", lang=session.get("lang", "en"),
                           google_ready=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
                           error=request.args.get("error"))


@app.route("/auth/guest")
def auth_guest():
    session["user"] = {"handle": "@guest", "name": "Guest", "email": "", "admin": False, "guest": True}
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
    return render_template("home.html", **ctx)


@app.route("/app/messages")
@app.route("/app/messages/<conv_id>")
def messages(conv_id=None):
    ctx = base_context("messages")
    conv = CONVERSATIONS.get(conv_id) if conv_id else None
    if conv is None and conv_id:
        if conv_id.startswith("local-"):
            conv = {"id": conv_id, "type": "local", "atmosphere": "dark-ridge",
                    "title": request.args.get("t", "New conversation"),
                    "sub": "on this device only", "messages": []}
        elif conv_id.startswith("dm-"):
            handle = conv_id[3:]
            conv = {"id": conv_id, "type": "dm", "atmosphere": "halo",
                    "title": request.args.get("t", handle),
                    "sub": "@" + handle, "messages": []}
    ctx["active"] = conv
    return render_template("messages.html", **ctx)


@app.route("/app/spaces")
def spaces_view():
    return render_template("spaces.html", **base_context("spaces"))


@app.route("/app/moments")
def moments_view():
    return render_template("moments.html", **base_context("moments"))


@app.route("/app/people")
def people_view():
    ctx = base_context("people")
    contacts = []
    client = supabase()
    me = ctx["user"]["handle"].lstrip("@")
    if client and not ctx["user"]["guest"]:
        try:
            rows = client.table("contacts").select("contact").eq("owner", me).execute().data or []
            handles = [r["contact"] for r in rows]
            if handles:
                profs = client.table("profiles").select("handle, display_name, is_admin").in_("handle", handles).execute().data or []
                contacts = profs
        except Exception:
            pass
    ctx["contacts"] = contacts
    return render_template("people.html", **ctx)


@app.route("/app/calls")
def calls_view():
    return render_template("calls.html", **base_context("calls"))


@app.route("/app/media")
def media_view():
    ctx = base_context("media")
    ctx["media"] = MEDIA
    return render_template("media.html", **ctx)


@app.route("/app/settings")
def settings_view():
    return render_template("settings.html", **base_context("settings"))


# ---------------------------------------------------------------------------
# Auth APIs — email/password + Google OAuth
# ---------------------------------------------------------------------------

@app.post("/api/signup")
def api_signup():
    data = request.json or {}
    username = (data.get("username") or "").strip().lstrip("@").lower()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not username or not email or len(password) < 6:
        return jsonify({"error": "Username, email and a password of 6+ characters are required."}), 400
    client = supabase()
    if not client:
        return jsonify({"error": "Cloud profiles need supabase keys in .env."}), 503
    if sb_find_profile(username):
        return jsonify({"error": "That username is taken."}), 409
    if sb_find_profile(email):
        return jsonify({"error": "That email already has an account."}), 409
    profile = {
        "handle": username,
        "display_name": data.get("name") or username,
        "email": email,
        "password_hash": generate_password_hash(password),
        "is_admin": username == ADMIN_HANDLE,
    }
    try:
        client.table("profiles").insert(profile).execute()
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
    profile = sb_find_profile(identity)
    if not profile:
        return jsonify({"error": "No account found for that username or email."}), 404

    stored = profile.get("password_hash")
    if not stored and profile["handle"] == ADMIN_HANDLE:
        # first claim of the admin account
        if password != ADMIN_FIRST_PASSWORD:
            return jsonify({"error": "Wrong password."}), 401
        try:
            supabase().table("profiles").update(
                {"password_hash": generate_password_hash(password)}
            ).eq("handle", ADMIN_HANDLE).execute()
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
    return url_for("google_callback", _external=True)


@app.route("/auth/google")
def google_auth():
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        return redirect(url_for("auth", error="Google sign-in needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."))
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
    }
    return redirect(GOOGLE_AUTH_URL + "?" + urlencode(params))


@app.route("/auth/google/callback")
def google_callback():
    import requests as rq
    code = request.args.get("code")
    if not code:
        return redirect(url_for("auth", error="Google sign-in was cancelled."))
    try:
        token = rq.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        }, timeout=15).json()
        info = rq.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": "Bearer " + token["access_token"],
        }, timeout=15).json()
    except Exception:
        return redirect(url_for("auth", error="Google sign-in failed — check the credentials in .env."))

    email = (info.get("email") or "").lower()
    if not email:
        return redirect(url_for("auth", error="Google did not return an email address."))
    profile = sb_find_profile(email)
    if not profile:
        handle = email.split("@")[0].replace(".", "")[:24]
        if sb_find_profile(handle):
            handle = handle + uuid.uuid4().hex[:4]
        profile = {
            "handle": handle,
            "display_name": info.get("name") or handle,
            "email": email,
            "is_admin": handle == ADMIN_HANDLE,
        }
        try:
            supabase().table("profiles").insert(profile).execute()
        except Exception:
            pass
    login_as(profile)
    return redirect(url_for("onboarding"))


# ---------------------------------------------------------------------------
# People APIs — find by username, add contacts
# ---------------------------------------------------------------------------

@app.get("/api/users/find")
def api_users_find():
    q = (request.args.get("q") or "").strip().lstrip("@").lower()
    if len(q) < 2:
        return jsonify({"results": []})
    client = supabase()
    if not client:
        return jsonify({"results": [], "error": "cloud not configured"})
    me = (current_user() or {}).get("handle", "").lstrip("@")
    try:
        resp = client.table("profiles").select("handle, display_name, is_admin") \
            .ilike("handle", f"%{q}%").limit(8).execute()
        results = [r for r in (resp.data or []) if r["handle"] != me]
        return jsonify({"results": results})
    except Exception as exc:
        return jsonify({"results": [], "error": str(exc)[:120]})


@app.post("/api/contacts")
def api_contacts_add():
    user = current_user()
    if not user or user.get("guest"):
        return jsonify({"error": "Sign in to add people."}), 401
    contact = ((request.json or {}).get("contact") or "").strip().lstrip("@").lower()
    if not contact:
        return jsonify({"error": "No username given."}), 400
    if not sb_find_profile(contact):
        return jsonify({"error": "No one found with that username."}), 404
    try:
        supabase().table("contacts").insert({
            "owner": user["handle"].lstrip("@"), "contact": contact,
        }).execute()
    except Exception:
        pass  # duplicate adds are fine
    return jsonify({"ok": True, "contact": "@" + contact})


# ---------------------------------------------------------------------------
# Chat APIs
# ---------------------------------------------------------------------------

@app.post("/api/assistant")
def assistant():
    data = request.json or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    if not message:
        return jsonify({"error": "empty message"}), 400

    if not GEMINI_API_KEY:
        return jsonify({"reply": (
            "I'm not connected yet. Open the .env file in the project root and put "
            "your Google AI Studio key into gemini_api_key=\"\" — then restart phantom. "
            "Keys are free at aistudio.google.com/apikey."
        ), "offline": True})

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
                model=model,
                contents=contents,
                config={"system_instruction": ASSISTANT_SYSTEM, "temperature": 0.6},
            )
            reply = (resp.text or "").strip() or "…I have nothing to add."
            sb_insert("messages", {"conversation_id": "ai", "author": "me", "body": message})
            sb_insert("messages", {"conversation_id": "ai", "author": "ai", "body": reply})
            return jsonify({"reply": reply, "model": model})
        except Exception as exc:
            last_error = exc
            app.logger.warning("gemini %s failed: %s", model, exc)
    return jsonify({"reply": (
        "Gemini is busy right now — give it a moment and ask again."
    ), "offline": True, "error": str(last_error)[:200]})


@app.post("/api/conversations/<conv_id>/messages")
def send_message(conv_id):
    body = (request.json or {}).get("body", "").strip()
    if not body:
        return jsonify({"error": "empty message"}), 400
    msg = _msg("me", body)
    conv = CONVERSATIONS.get(conv_id)
    if conv:
        conv["messages"].append(msg)
    author = (current_user() or {}).get("handle", "me")
    sb_insert("messages", {"conversation_id": conv_id, "author": author, "body": body})
    return jsonify(msg), 201


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