# 12 · Uploading to YouTube

Rendered reels are pushed to the **Meow and Then** channel
(https://www.youtube.com/@meowandthen) with `engine/upload.py`, which reads
metadata from `youtube.json` and writes posting status back into it.

## One-time setup

These steps happen in the Google Cloud console under the Google account that
owns the channel. You only do them once.

1. **Create / pick a project** at https://console.cloud.google.com → project picker → *New Project* (e.g. "meow-and-then").
2. **Enable the API:** APIs & Services → Library → search *YouTube Data API v3* → **Enable**.
3. **OAuth consent screen:** APIs & Services → OAuth consent screen.
   - User type: **External**.
   - Fill app name ("Meow and Then uploader"), your email for support + developer contact. Save.
   - **Test users:** add your own Google address (the channel owner). While the app is in "Testing" only test users can authorize it — that's all you need.
   - You do **not** need Google verification for personal uploads.
4. **Create credentials:** APIs & Services → Credentials → *Create credentials* → **OAuth client ID** → Application type **Desktop app** → Create.
   - **Download JSON**, rename to `client_secret.json`, and drop it in the repo root.
   - (`client_secret.json` and `token.json` are gitignored — never commit them.)
5. **Install deps:** `pip install -r requirements.txt`
6. **Authorize once:** `python -m engine.upload --auth`
   - A browser opens; sign in as the channel owner and grant the YouTube upload scope.
   - A `token.json` is written and reused on every later run (auto-refreshed).

## Day-to-day

```bash
python -m engine.upload --status            # see what's posted / queued / next
python -m engine.upload --next              # upload the next queued video, public
python -m engine.upload where-to-eat        # upload a specific slug
python -m engine.upload --next --privacy unlisted   # safe test upload
python -m engine.upload --sync              # regenerate youtube.md from youtube.json
```

On success the script:
- uploads the mp4 named in `youtube.json` (`file`, e.g. `output/where-to-eat.mp4`),
- sets it to `categoryId` 15 (Pets & Animals), not made-for-kids,
- marks the video `posted` with today's date and its `video_id`,
- regenerates `youtube.md`.

The `#shorts` tag in the title/description plus the vertical <60s aspect makes
YouTube classify it as a Short automatically.

## Notes & limits

- **Quota:** the YouTube Data API gives ~10,000 units/day; each upload costs ~1,600, so ~6 uploads/day. Fine for this cadence.
- **First-upload privacy:** new/unverified API clients sometimes have uploads forced to *private* until the channel is in good standing. If a video lands private, flip it to public once in YouTube Studio, or upload that first one manually. Use `--privacy unlisted` to test the pipeline without publishing.
- **Re-running:** uploading the same slug again creates a *new* video (YouTube has no idempotency); the script guards against re-posting an already-posted slug unless you name it explicitly.
- Thumbnails/captions aren't set by the API here — Shorts use a frame by default, which is fine for this format.
