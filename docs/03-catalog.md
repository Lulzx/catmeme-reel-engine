# 3. The catalog — "describe once"

`data/catalog.json` is the frozen, text-only description of every clip. Built by
`engine/build_catalog.py`. Rebuild only when the clip set changes.

## Why

Watching/analyzing 36 videos is slow and can't be done by reasoning over text. So we
do it **once**, encode the result as text, and never look at the pixels again when
authoring stories. An LLM can then hold the entire library in context.

## How it's built

For each clip in `clips/` (`NN - Title [id].ext`):

1. **Probe** duration, width, height → `orientation` (portrait/landscape/square),
   via `ffprobe`.
2. **Representative frame** — one frame is extracted at ~40 % of the clip (capped at
   8 s for the long compilation) into `work/frames/NN.jpg`, scaled to 320 px wide.
   This single frame drives the two computed visual fields below.
3. **`key_color`** — the dominant green is sampled from the *border region* of that
   frame: collect clearly-green pixels (`g>90 and g>1.25·r and g>1.25·b`), quantize to
   16-value buckets, take the modal bucket, average it → `0xRRGGBB`. Per-clip keying
   matters because the greens vary (`0x13ff09` … `0x5dd552`).
4. **`bbox`** — the subject's normalized bounding box `[x0,y0,x1,y1]`. Computed by
   counting non-green pixels per row and per column, then taking the extent of rows/
   cols whose count exceeds 12 % of the peak (this filters edge noise / JPEG fringing).
   Used by the renderer to **ground** the cat and place its **label** and **shadow**.
5. **Emotion descriptors** — hand-authored once (see taxonomy below), merged in by id.

## Schema (one entry)

```jsonc
{
  "id": "012",
  "file": "012 - Green Screen Screaming Cat Meme [rE9T7MgQT3A].webm",
  "title": "Green Screen Screaming Cat Meme",
  "duration": 5.1,
  "width": 1920, "height": 1080, "orientation": "landscape",
  "key_color": "0x13ff09",          // sampled green to chroma-key out
  "bbox": [0.31, 0.18, 0.69, 1.0],  // where the cat is, normalized (for grounding)
  "primary": "rage scream",          // one-phrase dominant feeling
  "emotions": ["screaming","rage","yelling","outburst","shouting","furious","explosion"],
  "action": "cat throws head back and screams",   // what it physically does
  "sound": "loud cat scream",        // character of the clip's own audio (kept in edit)
  "use_for": "explosive anger, screaming a line, losing it",  // NL match guide
  "quality": "good",                 // good | ok | partial | low | avoid
  "note": ""                          // caveats (e.g. "cartoon", "real bg")
}
```

## The emotion taxonomy

Fields an author / matcher reads:

- **`primary`** — the headline feeling, for humans skimming.
- **`emotions`** — the searchable tag list. These are what `want: [...]` matches
  against most strongly. Keep them lowercase, hyphenated for multiword
  (`zoning-out`, `dead-inside`). Each clip's hand-authored tags are **merged with a
  controlled 25-word cat taxonomy** (`TAXONOMY`/`TAX_ADD` in `build_catalog.py`, adopted
  from the AI_Reaction_bot study — `happy, sad, surprised, scared, unimpressed, playful,
  angry, content, loving, curious, indifferent, hungry, relaxed, confused, annoyed,
  excited, terrified, mischievous, pensive, jealous, nervous, affectionate, bored, proud,
  sleepy, resigned, disgusted`). A build assertion guarantees every taxonomy word maps to
  at least one clip, so an author can reliably reach a clip with any standard feeling word.
- **`use_for`** — a natural-language "drop this in when…" sentence. Gives weak
  matching signal and documents intent.
- **`sound`** — reminds the author that **the clip's own audio plays** (a meow,
  scream, keyboard clicks). The audio is part of the joke; pick clips whose sound fits.

### `quality` flags (and how the matcher treats them)

| flag | meaning | matcher bonus |
|------|---------|---------------|
| `good` | clean key, usable framing | +0.6 |
| `ok` | usable but lower-res / cartoon | +0.2 |
| `partial` | imperfect key / real (non-green) background | 0.0 |
| `low` | tiny or very blurry (e.g. clip 039 is 144×144) | −0.6 |
| `avoid` | not a single reaction (e.g. clip 001 is an 8-min compilation) | −3.0 |

So `avoid`/`low` clips are effectively suppressed unless nothing else matches.

## The current library

36 clips survived the playlist download (6 were deleted/private). They span a wide
emotional range — screaming, smug/rizz, sad, zoning-out, disgust, dancing, typing,
driving, sleeping, startled, furious, laughing, "huh?" deadpan, etc. A couple are dogs
or cartoons (flagged in `note`). Run `python3 engine/build_catalog.py` to print the
full list with key-colors and primaries.
