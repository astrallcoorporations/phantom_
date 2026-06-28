# Phantom on the Amazon Appstore (and Play)

This folder builds the Android app (a **TWA** — a thin wrapper that runs your
live PWA full-screen). It produces both an **`.aab`** (Play Store) and an
**`.apk`** (Amazon Appstore accepts either, APK is simplest).

You can't ship the binary straight from here — it has to be *built and signed*
on your machine (Android needs a keystore). Two ways, pick one:

## Option A — Bubblewrap CLI (uses `twa-manifest.json` in this folder)

1. Install once: `npm i -g @bubblewrap/cli` (needs Java 17 + Android SDK; Bubblewrap can install them: `bubblewrap doctor`).
2. Edit **`twa-manifest.json`** — replace every `REPLACE-WITH-YOUR-DOMAIN.vercel.app`
   with your real deployed domain.
3. From this `android/` folder:
   ```bash
   bubblewrap build
   ```
   First run creates a signing keystore (**back it up — you need it for every update**).
4. Outputs: **`app-release-bundle.aab`** and **`app-release-signed.apk`**.

## Option B — PWABuilder (no local Android toolchain)

1. Go to **https://www.pwabuilder.com**, paste your live URL.
2. **Package for stores → Android** → Download. You get the `.aab` + `.apk` + keystore.

## Upload to the Amazon Appstore

1. **https://developer.amazon.com** → Apps & Games → **Add New App → Android**.
   (Amazon's developer account is **free** — no $25 fee like Play.)
2. Upload the **`.apk`** (or `.aab`). Fill the listing: title, description,
   icon (use `static/img/icon-512.png`), at least 2 screenshots, a privacy
   policy URL.
3. Submit. Amazon reviews in ~1–3 days.

## Verify the app owns the domain (hides the URL bar)

After building, you get a SHA-256 fingerprint. Add it to Vercel env vars so
`/.well-known/assetlinks.json` confirms ownership:
```
ANDROID_PACKAGE      = chat.phantom.twa
ANDROID_FINGERPRINTS = AB:CD:EF:...   (the SHA-256 from the build/keystore)
```
Amazon also has its own app-linking (Amazon signs apps with its own cert) — in
the Amazon console, copy **their** SHA-256 into the same `ANDROID_FINGERPRINTS`
(comma-separated) so the link works for Amazon-signed installs too.

> The Play Store path is documented separately in `../ANDROID.md`. Same TWA,
> same manifest — just a different store upload.
