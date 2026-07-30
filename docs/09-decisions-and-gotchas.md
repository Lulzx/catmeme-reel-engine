# 9. Decisions, dead-ends & gotchas

The reasoning behind non-obvious choices, and the things that *don't* work in this
environment — so they aren't rediscovered the hard way.

## Key decisions

- **Describe clips once, then author over text.** Video analysis is the expensive part
  and can't be done by reasoning over text. Freezing it into `catalog.json` lets an LLM
  hold the whole library in context and write unlimited stories cheaply. This is the
  central architectural bet.
- **Declarative stories (`want`, not `clip`).** Beats ask for an emotion; the matcher
  resolves it. Stories stay readable and portable to a different clip library.
- **Deterministic matcher (overlap scoring), not embeddings.** Predictable and
  explainable (it reports *why* it picked a clip). Recall was plenty good; embeddings
  would add a dependency and opacity for little gain.
- **Per-clip green key-color.** The greens genuinely vary (`0x13ff09` … `0x5dd552`);
  sampling each clip's actual border green keys far cleaner than one global color.
- **Grounding via subject bbox.** Computing where the cat is in-frame (once, in the
  catalog) is what lets the renderer place feet on a surface, put the label above the
  head, and size the *cat* (not the frame) consistently. This single field is what made
  the output stop looking like floating stickers.
- **Re-encode at concat.** Slightly slower than stream-copy but avoids
  timestamp/keyframe glitches at beat joins; worth it for a clean final file.
- **`loudnorm` per beat.** Raw clip loudness swings −8 to −27 dB; without normalization
  the reel is jarring. Normalizing to −16 LUFS makes it flow.

## Gotchas (environment)

- **No `drawtext` / `subtitles` / `ass` in this ffmpeg build.** All on-screen text is
  drawn with **Pillow** and overlaid as PNGs. If you add text, do it in Pillow. See
  [02-environment.md](02-environment.md).
- **No ImageMagick.** Pillow covers everything; don't reach for `convert`/`magick`.
- **Python TLS needed an unverified SSL context** to fetch images reliably here. Fine
  for public CC images; don't copy that pattern into anything sensitive.
- **Send a real `User-Agent`** on image requests; some endpoints reject the default.
- **`uploadLimitExceeded` — the per-account daily video cap, not the API quota.** Batch
  scheduling dies partway with:

  ```
  googleapiclient.errors.ResumableUploadError: <HttpError 400 when requesting None
  returned "The user has exceeded the number of videos they may upload.".
  Details: "[{'message': 'The user has exceeded the number of videos they may upload.',
  'domain': 'youtube.video', 'reason': 'uploadLimitExceeded'}]">
  ```

  This is **not** the API quota — that's separate and this project's is raised to ~100
  uploads/day. YouTube *also* caps how many videos the **account** may upload per calendar
  day. Observed 2026-07-30: it fired after **38 uploads in one day** (a 27-reel batch plus
  11 of the next). Plan on **~35–40/day**, and split month-sized batches across days.

  `engine/upload.py --fill-schedule` handles the quota error but **not this one** — it
  exits 1 with the traceback above. The failure is safely resumable, because the DB is
  written per-upload: reels already up are `scheduled` with a `publish_at`, the rest stay
  `queued` with `publish_at` NULL. Re-running the same command on a later day continues the
  6-hour grid from the last scheduled reel, with no gap and no double-upload. Confirm with:

  ```bash
  sqlite3 data/videos.db "SELECT status, count(*) FROM videos GROUP BY status;"
  sqlite3 data/videos.db "SELECT date(publish_at), count(*) FROM videos \
      WHERE status='scheduled' GROUP BY 1 ORDER BY 1;"      # find days under 4
  sqlite3 data/videos.db "SELECT count(*) FROM videos \
      WHERE status='queued' AND publish_at IS NOT NULL;"    # must be 0
  ```

  Full detail in [12-youtube-upload.md](12-youtube-upload.md).

## Dead-ends (tried, rejected)

- **`source.unsplash.com`** — dead (HTTP 503; Unsplash retired it).
- **`loremflickr.com`** — keyless but returns essentially random tag matches (a
  sheriff's car for "office"). Unusable for scene relevance.
- **`picsum.photos`** — no keyword support; random images only.
- **ffmpeg `drawtext`** — not compiled in (see above).
- **Batch `yt-dlp` with many URLs where some IDs start with `-`** — the leading-dash IDs
  were parsed as flags and silently skipped. Fix: download per-URL with a `--`
  separator (`yt-dlp ... -- "https://..."`).

## Quirks of the source clips

- **Resolutions/orientations are mixed** (1920×1080, portrait 1080×1920, oddballs like
  144×144, 852×480). The renderer normalizes everything onto the story canvas, but very
  low-res clips (039, 144×144) are flagged `low` and suppressed by the matcher.
- **Clip 001 is an 8-minute compilation**, not a single reaction — flagged `avoid`.
- **A few "cats" aren't** — clip 040 is a corgi, 037/042 are cartoons — flagged in
  `note`; still usable when the emotion fits.
- **6 playlist entries were deleted/private** at download time, hence gaps in the
  numbering (014, 015, 028, 029, 034, 038).
- **`size` is a *height* fraction, so wide-bbox clips overflow sideways.** In
  `layout()` the visible width is `(bx1-bx0) * size*H/bbh * (cw/ch)` — nothing clamps
  it to the canvas. Clip **183** (the german cat) has a bbox aspect of ~1.3, so the
  usual `size: 0.44` renders it **951px wide on a 1080 canvas**. Fine for a solo
  close-up (that's its signature look), but in a **two-cat beat it completely covers
  its scene partner** — `pos` 0.30/0.72 is nowhere near enough separation. For any
  two-cat beat involving a wide clip, size it by *target width* instead: 183 at
  `size: 0.24` is ~496px, which pairs with a ~420px partner at `pos` 0.26/0.74. Check
  before rendering rather than after — the story JSON looks completely reasonable.
- **Clip 007 ("driving") has a real car interior**, not full green — flagged `partial`;
  it keys imperfectly.
- **Dull-green clips erase under an aggressive chroma key.** Clip 033's green is
  desaturated, so a high `chromakey` similarity (0.19) matched the grey cat too and the
  whole frame went transparent (the cat vanished). Fix: keep similarity **low** (0.12)
  to preserve every subject, and add the **`despill`** filter to remove the green fringe
  that a low similarity leaves on bright-green clips. Low-sim + despill beats high-sim.

## Known limitations / TODO

- No **prop cut-outs** (phone/food) yet — a clear next step toward the reference look.
- No **background music** bed (needs a royalty-free source + ducking under cat audio).
- No **title cards / transition wipes** (easy to add as beat types).
- Label placement is good but approximate for extreme close-up clips (the bbox includes
  ears/body, so the label can sit slightly low on the cat).
- Background relevance depends on query quality and Openverse's catalog; a paid stock
  API or an image generator would raise consistency. (Mitigated: a bundled scene library
  is now preferred over the web — see [06](06-backgrounds.md).)

### Candidate upgrades borrowed from prior art ([11-prior-art.md](11-prior-art.md))

- **Pre-bake keyed clips to transparent PNG sequences** offline → faster, deterministic
  re-renders (AICatMeme does this).
- **Schema-as-prompt** for an LLM authoring front-end: inject a closed enum of clips/
  scenes so the model can't pick a missing asset.
- **Parallel beat rendering** (thread pool) and **`-c copy` concat** (uniform params) to
  cut render time.
- ~~Enrich the emotion taxonomy with the 25-word cat set from AI_Reaction_bot~~ —
  **done** (merged via `TAXONOMY`/`TAX_ADD` in `build_catalog.py`).
- **Karaoke captions** (one word at a time) as a styling option.
