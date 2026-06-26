# Cat-meme reel engine — documentation

This project turns a library of green-screen cat clips into **narrated POV story
reels** in the style of cat-meme reaction shorts.

![How the engine works](how-it-works.png)

The core idea: **describe every clip once** (emotion, sound, where the cat is in
frame), then let an author (a human or an LLM) write a story purely in *words and
desired emotions*. The system matches each story beat to the best cat, drops it
onto a scene-relevant background, labels it, and renders a finished vertical video.

## Read in this order

| # | doc | what's in it |
|---|-----|--------------|
| 1 | [01-overview.md](01-overview.md) | the four-stage pipeline, directory map, data flow |
| 2 | [02-environment.md](02-environment.md) | tooling, the ffmpeg/`drawtext` quirk, fonts, network |
| 3 | [03-catalog.md](03-catalog.md) | the "analyze once" clip library + emotion taxonomy + bbox |
| 4 | [04-matcher.md](04-matcher.md) | how a desired emotion resolves to a clip (scoring) |
| 5 | [05-renderer.md](05-renderer.md) | compositing: chroma-key, grounding math, text, audio, concat |
| 6 | [06-backgrounds.md](06-backgrounds.md) | scene-relevant image fetching (Openverse) + fallbacks |
| 7 | [07-design-study.md](07-design-study.md) | **the design study — how the on-screen style was reverse-engineered** |
| 8 | [08-authoring-stories.md](08-authoring-stories.md) | full `story.json` schema + how to write a good one |
| 9 | [09-decisions-and-gotchas.md](09-decisions-and-gotchas.md) | choices made, dead-ends, things that don't work here |
| 10 | [10-how-to.md](10-how-to.md) | copy-paste recipes (download, rebuild catalog, render) |
| 11 | [11-prior-art.md](11-prior-art.md) | learnings from similar projects (AICatMeme, AI_Reaction_bot) |

## TL;DR

```bash
# 1. clips already downloaded into the project root (NN - Title [id].ext)
# 2. catalog describing each clip is built once:
python3 engine/build_catalog.py        # -> data/catalog.json
# 3. write/edit a story, then render:
python3 engine/render.py data/stories/functional-adult.json   # -> output/final.mp4
```

Everything operational also lives in [`engine/README.md`](../engine/README.md); these
docs are the deeper "why / how / what I learned" companion.
