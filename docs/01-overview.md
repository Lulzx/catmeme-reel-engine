# 1. Overview & architecture

## The four-stage pipeline

```
            ┌─────────────────────────────────────────────────────────────┐
            │  STAGE 0 — ACQUIRE (one time)                                 │
            │  yt-dlp downloads the playlist -> NN - Title [id].ext         │
            └─────────────────────────────────────────────────────────────┘
                                  │
            ┌─────────────────────▼───────────────────────────────────────┐
            │  STAGE 1 — DESCRIBE ONCE  (build_catalog.py)                  │
            │  • probe duration / resolution / orientation                 │
            │  • sample the green key-color from a real frame              │
            │  • compute the subject bounding box (where the cat is)        │
            │  • attach hand-authored emotion descriptors                   │
            │  ->  data/catalog.json                                      │
            └─────────────────────┬───────────────────────────────────────┘
                                  │      (never re-watches the videos again)
            ┌─────────────────────▼───────────────────────────────────────┐
            │  STAGE 2 — AUTHOR  (story.json, written by a human or LLM)    │
            │  a constant POV premise + beats; each beat = a scene with     │
            │  an *action* line and a cast of NAMED characters, each asking │
            │  for a desired emotion in words (no clip IDs needed)          │
            └─────────────────────┬───────────────────────────────────────┘
                                  │
            ┌─────────────────────▼───────────────────────────────────────┐
            │  STAGE 3 — MATCH + RENDER  (match.py + render.py)            │
            │  match : desired emotion -> best clip (text scoring)          │
            │  render: fetch background, chroma-key + ground each cat,      │
            │          draw POV bubble / labels / action, mix audio,        │
            │          concat beats                                         │
            │  ->  final.mp4                                                │
            └───────────────────────────────────────────────────────────────┘
```

The hard separation between **Stage 1 (describe once)** and **Stage 2/3 (author &
render many times)** is the whole point: video analysis is slow and expensive, so
it happens exactly once and is frozen into `catalog.json` as text. After that, an
LLM can write unlimited stories by reasoning over text alone.

## Directory map

```
cat-videos/
├── engine/                    # the code
│   ├── paths.py               # canonical paths (single source of truth)
│   ├── build_catalog.py       # STAGE 1
│   ├── match.py               # STAGE 3a — emotion -> clip
│   ├── render.py              # STAGE 3b — story -> video
│   └── README.md              # operational quick-reference
├── clips/                     # source green-screen clips + archive.txt  (input)
├── backgrounds/               # bundled AI scene library (kitchen, gym, …) (input)
├── data/                      # committed text data
│   ├── catalog.json           #   the "describe once" clip library
│   └── stories/*.json         #   the narratives (STAGE 2)
├── work/                      # regenerable artifacts (safe to delete)
│   ├── frames/                #   one representative frame per clip
│   ├── overlays/              #   per-beat text-overlay PNGs
│   ├── bg_render/             #   per-beat composited background PNGs
│   ├── bg_cache/              #   web-fetched scene photos (cached by query)
│   └── beat_clips/            #   per-beat rendered mp4s + concat list
├── output/                    # finished reels (final.mp4)
└── docs/                      # this documentation
```

`clips/`, `work/`, and `output/` are git-ignored (media / regenerable); `engine/`,
`data/`, `backgrounds/`, and `docs/` are tracked.

## Data flow in one sentence

`playlist → clips → catalog.json (text) → + story.json (text) → matcher picks clips →
ffmpeg composites cats over fetched backgrounds with labels/captions → output/final.mp4`.

## Why each piece exists

- **catalog.json** is the contract between "looking at videos" and "writing stories".
  It is plain text so an LLM can hold the whole library in context and reason about it.
- **match.py** keeps story authoring *declarative*: you say `want: ["smug","rizz"]`,
  not `clip: "020"`. Stories stay readable and portable to a different clip library.
- **render.py** is the only component that touches pixels/audio. All creative intent
  is expressed upstream as text.
