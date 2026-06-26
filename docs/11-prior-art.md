# 11. Prior art — learnings from similar projects

Two open-source projects in the same space were studied. This records what they do,
what validated our design, and what we borrowed (or could).

## AICatMeme — https://github.com/Stickic-cyber/AICatMeme

An AI-driven cat-meme generator (Chinese; live at ai.stickic.asia). Nearly the same
problem as ours. Its current V2 is `app.py` + `core/` + `services/`.

**Validated our approach:**
- **Green-screen keying = `colorkey` + `despill`.** Their preprocessor uses
  `colorkey=0x00FF4B:0.25:0.02,despill=green`. This independently confirms the despill
  fix we landed — despill is the edge-quality trick, not a high key tolerance. (They use
  `colorkey`/RGB on a single sampled green; we use per-clip `chromakey`/YUV + despill,
  which handles our clips' varying greens.)
- **Each clip keeps its own audio**; multi-cat ("dialogue") scenes mix the two cats'
  audio (they sequence left-then-right; we `amix`).
- **Name label above each cat; POV/title as a top banner.** Same as ours.
- **Background = a closed set of scene-named files** (`backgrounds/<place>.jpg`), the
  LLM picks the `place`. → We adopted this directly as `bg.place` + the bundled library
  ([06-backgrounds.md](06-backgrounds.md)); their `backgrounds/` is literally the image
  set we now ship.
- `force_original_aspect_ratio=increase,crop,setsar=1` to fill the canvas — same as ours.

**Ideas worth adopting later:**
- **Pre-bake keyed clips to transparent PNG sequences offline** (`meme/<emotion>/frames/
  %04d.png` + `audio.mp3`). Heavy keying done once; render-time is pure compositing →
  faster, deterministic. We key at render time; pre-baking would speed re-renders.
- **Schema-as-prompt**: they inject a Pydantic `model_json_schema()` (with a closed
  enum of emotions/places) into the LLM system prompt + JSON mode, so the model can't
  pick a clip/scene that doesn't exist. Our matcher is fuzzier (free `want` tags scored
  over many clips) — more flexible, but the schema-constraint trick is a clean way to
  guarantee valid output if we add an LLM authoring front-end.
- **Concat with `-c copy`** (no re-encode) since every scene uses identical encode
  params → sub-second stitch. We re-encode at concat for glitch-safety; copy is faster
  if we guarantee uniform params.
- **Parallel scene rendering** via a thread pool (we render beats sequentially).
- **Dialogue turn-taking in one ffmpeg pass** using `overlay=...:enable='lt(t,{dur})'`
  to animate one cat while the other holds a frame — no sub-clip cutting.

**Their limitations we already beat:** 1 clip per emotion (hard 33-class folders, no
per-emotion variety or selection) — our catalog has many clips with overlapping tags and
a scoring matcher, so we get variety and avoid repeats.

## AI_Reaction_bot — https://github.com/dromech/AI_Reaction_bot

Generates "two cats react to a meme video" clips. Its reactions are **synthesized**
(avatar PNG + Polly TTS), not a green-screen clip library — so it's weakest exactly
where we're strong (no clip retrieval). Still useful patterns:

- **Closed-vocabulary inline emotion tags as asset keys** — the LLM emits a tag from a
  fixed list inline with the script; the tag both marks the beat and selects the asset.
  Same spirit as our `want` → matcher.
- **A 25-word cat emotion taxonomy** — *Happy, Sad, Surprised, Scared, Unimpressed,
  Playful, Angry, Content, Loving, Curious, Indifferent, Hungry, Relaxed, Confused,
  Annoyed, Excited, Terrified, Mischievous, Pensive, Jealous, Nervous, Affectionate,
  Bored, Proud, Sleepy, Resigned, Disgusted.* **ADOPTED** — merged into every clip's tags
  via `TAXONOMY`/`TAX_ADD` in `build_catalog.py` (a build assertion guarantees every word
  maps to a clip). See [03-catalog.md](03-catalog.md).
- **Audio-driven timing** — TTS length defines each segment's duration. We derive beat
  duration from clip length instead (no TTS), which is the analogous idea.
- **Single canonical JSON timeline**; each compositing stage is an idempotent
  `main(in, json, out)`. Our `story.json` + per-beat pipeline is the same shape.
- **Per-speaker caption color/side** and **fallback-by-filename-convention** (missing
  `S-Happy.png` → `S-Default.png`) — cheap robustness ideas.
- **Karaoke captions** (one word at a time) — a styling option we could add.

## Net changes we made from this study

- Adopted **scene-named background library, preferred over the web** (`bg.place` +
  bundled optimized images from AICatMeme).
- Confirmed the **despill** keying decision was right.
- Logged the rest (pre-baking, schema-as-prompt, parallel render, richer taxonomy,
  karaoke captions, copy-concat) as candidate upgrades in
  [09-decisions-and-gotchas.md](09-decisions-and-gotchas.md).
