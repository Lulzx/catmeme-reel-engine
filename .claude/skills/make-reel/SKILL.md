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
(e.g. "POV: you promised yourself you'd sleep early tonight"). Then sketch 5–9 **beats**,
each a single moment with a short caption. Name characters (`ME`, `MOM`, `BOSS`) and
reuse the names across beats.

**Caption format — quotes or nothing.** Two forms only:

- a spoken line in double quotes: `"i can jump this"`
- narration as bare text, no markers: `it is 6pm.`

**Never `*asterisks*`** — the caption is drawn to the frame literally, so they end up
on screen as characters. That's rule 18 in `docs/15-human-voice.md` and
`engine/lint_voice.py` fails on it. Stories written before 2026-07-30 still use the
old `*action*` form; they're already posted, don't copy them.

**Write the ending first.** The last beat is the whole point of the reel: a reversal
(the precaution causes the damage), a callback, or an absurd escalation that stays
specific. A resigned shrug ("i closed the calendar.") is where a punchline goes, not
a punchline — it fails the scoring gate in step 5.

**Recurring cast.** Every reel casts clip **182** (yapapa cat — the one who won't stop
talking) and **183** (german cat — the small guy with the unhelpful tip), pinned by id.
`184` is DEREK. Give them lines that earn their place; don't paste them in.

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
      "action": "\"i can jump this\"",                // quoted line, or bare narration
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

### 4. Check the voice rules and the clip spread
```bash
python3 -m engine.lint_voice --batch <slug> ...   # errors gate the render
python3 -m engine.allocate --check <slug> ...     # clip repeats / over-exposure
python3 -m engine.allocate --fix   <slug> ...     # globally reassign the pins
```
`lint_voice` enforces `docs/15-human-voice.md`. `allocate` solves clip assignment
across the whole batch at once so one cat doesn't end up in everything — see
`docs/16-clip-diversity.md`.

### 5. Score it — MANDATORY GATE
**Read `SCORING.md` in this directory and score every script yourself before
rendering.** Eight metrics, 100 points, threshold **75**, plus hard gates on the
punchline, the hook, and the human-voice read. You are the scorer — there is no
scoring binary, because every metric is a judgement about whether something is
funny.

A script below 75, or failing any gate, is **not rendered and not queued**. Rewrite
it and score again. A batch of nine that clears the bar beats sixteen that don't.

### 6. Render
```bash
python3 engine/render.py data/stories/<slug>.json     # -> output/<slug>.mp4
```
The log prints each beat's duration, chosen clip id, character, and caption. Backgrounds
are fetched from Openverse and cached in `work/bg_cache/`; if offline, the `palette`
gradient is used as a fallback.

### 7. Verify
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
