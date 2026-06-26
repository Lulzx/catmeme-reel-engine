# Cat-meme story engine

Turn the green-screen cat clips into narrated story videos. The cats are the
*reactions*; an LLM writes the *story*; the green screen becomes a *background*
relevant to each line; the clip's own audio is the soundtrack.

## The idea

1. **Describe the clips once** → `catalog.json`. Every clip gets emotion tags, a
   one-line "use this when…", its own sampled green key-color, and metadata. This
   is the analyze-once step — nothing re-watches the videos afterward.
2. **Write a story in words** → `story.json`. A constant `pov` premise, then beats;
   each beat is a scene with an `*action*` caption and a `cast` of named characters,
   each asking for the *emotion you want* (e.g. `["smug","rizz"]`). No clip IDs needed.
   Style: cat-meme reaction shorts (POV bubble, character labels,
   grounded cats on cozy backgrounds, multi-character scenes, end card).
3. **Match** → `match.py` scores the catalog by text overlap and picks the best
   cat for each beat (deterministic, explainable, avoids repeats).
4. **Render** → `render.py` paints a scene background + caption, chroma-keys the
   cat over it, keeps the clip audio, and concatenates beats into `final.mp4`.

## Files

| path | role |
|------|------|
| `engine/paths.py` | canonical project paths (imported by every script) |
| `engine/build_catalog.py` | builds `data/catalog.json` (run once; re-run if clips change) |
| `engine/match.py` | emotion → clip matcher (CLI: `python3 engine/match.py screaming rage`) |
| `engine/render.py` | story → video renderer |
| `data/catalog.json` | the clip library (emotions + key-color + bbox + metadata) |
| `data/stories/*.json` | the narratives (`functional-adult.json`, `asking-for-a-raise.json`) |
| `clips/` | source green-screen clips (+ `archive.txt`) |
| `backgrounds/` | bundled AI scene backgrounds (kitchen, gym, beach, …) — preferred over the web |
| `work/` | regenerable: `frames/ overlays/ bg_render/ bg_cache/ beat_clips/` |
| `output/` | finished reels (`final.mp4`) |

## Make a new video

Edit a story in `data/stories/` and run:

```bash
python3 engine/render.py data/stories/functional-adult.json     # writes output/final.mp4
```

### Story schema (POV format)

Top level:

```jsonc
{
  "canvas": { "w": 1080, "h": 1920, "fps": 30 },  // portrait reel
  "pov": "POV: you finally asked your boss for a raise", // constant top bubble
  "baseline": 0.9,            // where cats' feet land (fraction of height)
  "max_beat_dur": 4.5,
  "outro": "FOLLOW FOR PART 2",                   // optional end card
  "outro_cast": [ { "want": ["dancing","cute"], "size": 0.44 } ],
  "beats": [ ... ]
}
```

Each **beat** is a scene with 1-3 named characters:

```jsonc
{
  "action": "*walking in like I own the place*",  // italic caption (or "dialogue")
  "bg": {
    "img": "corporate office interior desks",      // fetched photo (Openverse), OR
    "image": "/path/to/local-or-ai.jpg",           // a local / AI-generated image, OR
    "palette": "office"                             // gradient fallback
  },
  "dur": 5.0,                                       // optional (default max_beat_dur)
  "cast": [
    { "name": "BOSS", "want": ["angry","glaring"], "pos": 0.67, "size": 0.46 },
    { "name": "ME",   "want": ["startled","nervous"], "pos": 0.30, "size": 0.40, "flip": true }
  ]
}
```

Cast member fields: `name` (label above the cat), `want`/`query`/`clip` (which cat —
matcher or pinned id), `pos` (center x, 0-1; auto-spread if omitted), `size` (cat
height as fraction of canvas), `baseline` (feet line), `flip` (mirror, e.g. to face
another cat), `key_similarity`. The renderer grounds each cat using its catalog
`bbox`, draws a contact shadow at its feet, and places the name label above its head.

Palettes: `bedroom office boss brain hallway mirror friday void neutral`.

### See what the matcher would pick (no render)

```bash
python3 engine/match.py screaming rage outburst
```

## Notes / knobs

- **Backgrounds** are real scene-relevant photos: each beat's `bg.img` query is
  fetched from Openverse (keyless CC image search), center-cropped to fill, and
  darkened for caption legibility. Downloads are cached in `bg/cache/` (keyed by
  query) so re-renders are instant and stable. Use `bg.image` for a local or
  AI-generated file, or omit both to fall back to a painted gradient card.
- **Format** is portrait 1080×1920 (reel/Shorts/TikTok) via `canvas`. Set it to
  `1920×1080` for landscape — the renderer adapts cat sizing and text scale to
  the aspect ratio automatically.
- **Captions** use Impact with an outline + banner. No `drawtext` in the local
  ffmpeg, so all text is rendered with Pillow then overlaid.
- **Audio** is loudness-normalized per beat (`loudnorm`) so clips don't jump in
  volume. The clip's original audio is what plays.
- **Quality flags** in the catalog: `good | ok | partial | low | avoid`. The
  matcher down-weights `low`/`avoid` (e.g. clip 001 is an 8-min compilation,
  039 is 144×144). `partial` = imperfect/real background (clip 007).
```
