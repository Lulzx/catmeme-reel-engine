---
name: make-reel
description: Quickly author and render a cat-meme reel from a one-line premise using this repo's story → match → render pipeline. Use when asked to "make a video/reel/short", create a new meme video, or turn an idea/POV into a rendered clip. Produces a data/stories/<slug>.json and an output/<slug>.mp4.
---

# Make a cat-meme reel

Turn a premise into a rendered vertical reel. The pipeline is text-only authoring →
deterministic clip match → ffmpeg render. You never touch pixels or pick clip IDs by
hand — you write feelings, the matcher picks clips from `data/catalog.json`.

Run everything from the repo root (`cat-videos/`).

## Steps

### 1. Lock the premise
One relatable POV line that never changes, phrased as `POV: ...`
(e.g. "POV: you promised yourself you'd sleep early tonight"). Then sketch 6–9 **beats**,
each a single moment with a short caption — an `*action*` stage direction or a
`"line of dialogue"`. Arc it: setup → escalation → climax (often a two-cat scene) →
punchline. Name characters (`ME`, `MOM`, `BOSS`) and reuse the names across beats.

### 2. Write the story JSON
Create `data/stories/<slug>.json`. Minimal shape (full schema in
`docs/08-authoring-stories.md`):

```jsonc
{
  "title": "Human Title",
  "output": "<slug>.mp4",                          // -> output/<slug>.mp4
  "canvas": { "w": 1080, "h": 1920, "fps": 30 },   // 1920x1080 for landscape
  "pov": "POV: ...",                                 // constant top bubble
  "outro": "FOLLOW FOR PART 2",                      // optional end card
  "outro_cast": [ { "want": ["dancing","happy"], "size": 0.44 } ],
  "beats": [
    {
      "action": "*captioned moment*",                // or "\"dialogue\""
      "bg": { "img": "specific scene query interior night", "palette": "room" },
      "cast": [ { "name": "ME", "want": ["bored","scrolling"], "size": 0.5 } ]
    }
  ]
}
```

Rules of thumb:
- **`want` tags must exist in the catalog** — verify in step 3, don't guess.
- **Climax beat = two cats** in one beat: `pos` ~0.30 / ~0.70, `flip: true` on one so
  they face each other.
- **Specific `bg.img` queries** ("cozy dark bedroom night interior", not "bedroom").
  Reuse the same string across beats to reuse the cached background.
- `size` ≈ 0.4–0.52 (cat height as fraction of canvas). Defaults cover the rest.
- Pin an exact clip with `"clip": "178"` instead of `want` only when you must.

### 3. Dry-run the match (always, before rendering)
Confirms every beat resolves to a real clip and lets you see what got picked:

```bash
python3 - <<'PY'
import json,sys; sys.path.insert(0,"engine"); import match as M
s=json.load(open("data/stories/<slug>.json")); cat=M.load_catalog(); used=[]
for i,b in enumerate(s["beats"]):
    for c in b.get("cast",[]):
        _,clip,_=M.best(c.get("want",[]),c.get("query",""),cat,exclude=used); used.append(clip["id"])
        print(f"beat {i} {c.get('name','?'):5s} -> [{clip['id']}] {clip['primary']}  q={clip['quality']}")
PY
```

If a beat lands on a weak/`avoid`/`low` clip or the wrong vibe, adjust its `want` tags
(or check options with `python3 engine/match.py <tag> <tag> ...`) and re-run. Tags map to
the catalog's `emotions`/`primary`; browse `data/catalog.json` for the vocabulary.

### 4. Render
```bash
python3 engine/render.py data/stories/<slug>.json     # -> output/<slug>.mp4
```
The log prints each beat's duration, chosen clip id, character, and caption. Backgrounds
are fetched from Openverse and cached in `work/bg_cache/`; if offline, the `palette`
gradient is used as a fallback.

### 5. Verify
```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 output/<slug>.mp4
ffmpeg -nostdin -i output/<slug>.mp4 -af volumedetect -f null - 2>&1 | grep mean_volume  # not silent
ffmpeg -nostdin -v error -y -ss 6 -i output/<slug>.mp4 -frames:v 1 /tmp/check.png        # eyeball a frame
```
Then `open output/<slug>.mp4`.

## Notes
- `output/`, `clips/`, and `work/` are gitignored — the rendered video stays local; only
  the story JSON is committed.
- Add new clips/emotions: see `docs/10-how-to.md` (drop a `data/descriptors-*.json` pack,
  rerun `python3 engine/build_catalog.py`).
- Reference example: `data/stories/just-one-video.json` (a doomscroll spiral).
