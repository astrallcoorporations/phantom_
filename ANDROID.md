# Phantom on Android (Google Play)

Phantom is now an installable **PWA**. The fastest way onto the Play Store is a
**TWA** (Trusted Web Activity) — a thin Android app that runs your live site
full-screen, no browser bar. You don't write any Android code; **PWABuilder**
generates the signed package for you.

Everything on the server side is already done: `manifest.webmanifest`, a
service worker (`/sw.js`), maskable icons, and `/.well-known/assetlinks.json`.

---

## Step 1 — Generate the Android package (PWABuilder)

1. Go to **https://www.pwabuilder.com**
2. Paste your live URL (e.g. `https://phantom-git-main-arsh7.vercel.app`) → **Start**.
3. It scores the PWA, then click **Package For Stores → Android → Generate**.
4. Note the **Package ID** it shows (e.g. `chat.phantom.twa`) — you'll need it.
5. Download the zip. It contains:
   - `app-release-signed.aab`  ← upload this to Play
   - `signing.keystore` + passwords  ← **back this up, never lose it** (needed for every future update)
   - `assetlinks.json`  ← contains your SHA-256 fingerprint

## Step 2 — Verify the app owns the domain (hides the URL bar)

Open the downloaded `assetlinks.json`, copy the `sha256_cert_fingerprints`
value, then in **Vercel → Settings → Environment Variables** add:

```
ANDROID_PACKAGE        = chat.phantom.twa          # the Package ID from step 1
ANDROID_FINGERPRINTS   = AB:CD:EF:...              # the SHA-256 from assetlinks.json
```

Redeploy. Confirm it worked: open
`https://your-domain/.well-known/assetlinks.json` — your fingerprint should be
in there. (Without this the app still works but shows a URL bar.)

## Step 3 — Google Play Console

1. **https://play.google.com/console** → pay the **one-time $25** developer fee.
2. **Create app** → name "Phantom", app (not game), free.
3. **Production → Create release → upload the `.aab`**.
4. Fill the required bits:
   - **Store listing**: short + full description, app icon (512×512 — use
     `static/img/icon-512.png`), at least **2 phone screenshots** (open the
     site on your phone, screenshot the app and a chat).
   - **Privacy policy URL** (Play requires one — a simple page is fine).
   - **Data safety** form, **content rating** questionnaire, target audience.
5. **Send for review.** First review usually takes a few days.

## Updating later

Re-run PWABuilder with the **same signing key** (it'll ask for your keystore),
get a new `.aab` with a higher version code, upload a new release. The site
itself updates instantly on every Vercel deploy — only ship a new `.aab` when
you change the icon, name, or package config.

---

### Alternative: native build with Tauri

Tauri v2 can build a real Android app (`npm run tauri android build`) — but it
needs the Android SDK + NDK + Java + Rust installed locally. The TWA/PWABuilder
route above is far less setup and is the recommended path for a web app.
