# Fixing calls ("connection failed / no TURN relay")

Voice/video calls connect peer-to-peer. When both people are on the same
network or have friendly routers, that works with just STUN (free, built in).
But most real-world calls (mobile data, office/school firewalls, strict home
routers — "symmetric NAT") **need a TURN relay server** to pass the audio/video
through. Phantom has no built-in TURN, and the old free public ones
(`openrelay.metered.ca`) were shut down — that's why you see
**"NO TURN RELAY"** or **"connection failed"**.

Fix = give Phantom one working TURN provider. Pick **one** of the options below
and add the env vars in **Vercel → Settings → Environment Variables**, then
redeploy. The app already knows how to use all three.

## Option A — Cloudflare TURN (recommended, free 1000 GB/month)

1. Go to **https://dash.cloudflare.com** → **Calls** (under the left menu) →
   **TURN** → **Create**.
2. It gives you a **Turn Token ID** and an **API Token**.
3. In Vercel add:
   ```
   CF_TURN_KEY_ID      = <Turn Token ID>
   CF_TURN_API_TOKEN   = <API Token>
   ```
4. Redeploy. Done — Phantom generates fresh relay credentials per call.

## Option B — Metered (free 500 MB/month) — you already started this

You have a Metered project. The 401 means the key in Vercel is wrong. In the
Metered dashboard → **Developers**, click the **copy** button next to the
**SECRET KEY** (don't hand-type it), then set in Vercel:
```
METERED_DOMAIN    = yourapp.metered.live      # no underscore, no https://
METERED_API_KEY   = <the SECRET KEY>
```

## Option C — your own / any TURN provider

If you run coturn or use another host, set:
```
TURN_URLS         = turn:your.host:3478,turns:your.host:5349?transport=tcp
TURN_USERNAME     = <username>
TURN_CREDENTIAL   = <password>
```

## Check it worked

Open `https://your-domain/api/ice?debug=1` while logged in.
- `"ok": true` → a TURN provider answered; calls should connect.
- `"ok": false` → none configured/working; it's falling back to STUN only.

The on-call status line also tells you: if it ever shows **NO TURN RELAY**, the
browser never got a relay candidate → the provider isn't set up yet.
