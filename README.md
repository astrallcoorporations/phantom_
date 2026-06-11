# phantom_

Private conversations. Nothing else.

## Run

```
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 — start at `/onboarding` for the full first-run flow.

## Keys (.env)

| Variable | Purpose |
| --- | --- |
| `gemini_api_key` | Powers the Phantom AI assistant (aistudio.google.com/apikey) |
| `flask_secret_key` | Flask session signing |
| `supabase_url` / `supabase_key` | Optional cloud mirror — messages sync to your Supabase project |

## Map

| Route | View |
| --- | --- |
| `/` | Landing — animated hero, poster, worlds |
| `/auth` | Sign in — email, OAuth, passkey |
| `/onboarding` | First run — name → choose your world → preferences |
| `/app` | Home — greeting, pinned, active spaces, welcome panel |
| `/app/messages` | Messages — Phantom AI + local conversations, tabs |
| `/app/spaces` | Spaces — my spaces grid + explore with join |
| `/app/moments` | Moments — pins timeline with filters |
| `/app/people` | People — empty by default, invite link |
| `/app/calls` | Calls — idle call stage, controls |
| `/app/media` | Media — gallery + lightbox |
| `/app/settings` | Settings — account · privacy · appearance · AI · language · accessibility |

## Accounts

- **Sign up** with username + email + password (hashed with Werkzeug, stored in
  your Supabase `profiles` table), **Google** (needs `GOOGLE_CLIENT_ID` /
  `GOOGLE_CLIENT_SECRET` in .env with `http://127.0.0.1:5000/auth/google/callback`
  registered), or **continue as guest**.
- The app (`/app/*`) requires a session; guests get the full local experience.
- **Admin** is the handle `totoandhenry` — first sign-in password is
  `phantom-admin` (change it after claiming). Admins get a badge.
- **Add people by username** on the People page; contacts persist in Supabase
  and each contact gets a direct conversation.

## Built in

- **Phantom AI** — Gemini-backed assistant (`gemini-2.5-flash` with automatic
  fallback chain), chat history kept on-device, typing indicator, graceful errors.
- **Supabase sync** — schema lives in your project (`profiles`, `spaces`,
  `conversations`, `messages`, `moments`, RLS on). Messages mirror on send.
  Dev-phase note: anon write policies are permissive; tighten to `auth.uid()`
  checks before going multi-user (see Supabase linter 0024).
- **localStorage backend** — messages, drafts, reactions, pins, joins, profile,
  theme, every preference. Device is the source of truth.
- **Onboarding** — 3 quiet steps; the chosen world re-skins the entire app.
- **Themes** — 15 atmospheres (web-sourced photography from Unsplash + original
  renders, watermarks removed); switchable in Settings → Appearance.
- **Ghost mode, ⌘K command center, 7 languages with RTL, reactions & pins,
  local conversations, media lightbox.**
- **Four skins** — Dark, Onyx, Light, High contrast (Settings → Appearance),
  applied before first paint, persisted per device.
- **Troubleshoot** (Settings) — common-bug answers, one-click "Ask Phantom AI",
  and "Email the owner" (prefilled mail to the maintainer).
- **Video advertisement** — `static/video/phantom-ad.mp4` (18s, 720p), rendered
  from the HD photography by `make_ad.py`; plays on the landing page.
- **HD imagery** — all atmospheres re-sourced from Unsplash at 2560px.
- **Motion** — view transitions between pages, animated hero lines, aurora,
  scroll reveals, card tilt, breathing atmospheres, cube glint — all disabled
  under `prefers-reduced-motion`.
- The advertisement poster (`static/img/web/phantom-poster.jpg`) is generated
  from brand assets with Pillow.

## Stack

Flask + Jinja + vanilla CSS/JS · python-dotenv · google-genai · supabase-py.
No frontend build step. No trackers.
