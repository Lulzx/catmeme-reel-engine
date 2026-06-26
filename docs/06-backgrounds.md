# 6. Backgrounds — scene-relevant images

Each beat's green screen is replaced with a photo relevant to the narration ("office",
"bathroom", "starry sky"). This documents how images are sourced and the alternatives
that were tried and rejected.

## Resolution order (offline-first)

A beat's background is resolved in this priority, stopping at the first hit:

1. **`bg.image`** — an explicit local/AI-generated file path.
2. **`bg.place`** — a named scene from the bundled **local library**
   (`backgrounds/<place>.jpg`), e.g. `"place": "kitchen"`. Direct, deterministic.
3. **`bg.img` keyword match against the local library** — the free-text query is scored
   against each library scene's keyword set (`LIB_KW` in `render.py`); a clear hit wins.
4. **`bg.img` via Openverse** (web fetch, cached) — only when the library has no match.
5. **`bg.palette`** — painted gradient card, if everything above fails.

So the **bundled scene library is preferred over the web.** It's 33 AI-generated scene
backgrounds (kitchen, school, gym, beach, restaurant, park, rooftop, station, hospital,
library, …) sourced from the
[AICatMeme](https://github.com/Stickic-cyber/AICatMeme) project, downloaded into
`backgrounds/` and **optimized** (downscaled to just cover 1080×1920, recompressed
to progressive JPEG q82 — ~18 MB → ~10 MB).

Naming a scene with `bg.place` mirrors how AICatMeme picks backgrounds (an LLM chooses
from a closed set of scene-named files) — it's the most reliable way to get a specific,
consistent background. Use `bg.img` (keyword/web) when you want something the library
doesn't cover (a bathroom, a starfield, a specific office).

Available library scenes: `airport amusementpark bank beach cinema classroom concert
fantacy forest grassland gym highway home hospital kitchen lab library museum mountain
park playground pool port restaurant river rooftop school shop stage station theater
village` (+ `others`).

## Source: Openverse API (keyless)

`fetch_image(query)` in `render.py` calls:

```
https://api.openverse.org/v1/images/?q=<query>&page_size=8&mature=false&license_type=all
```

It walks the results, downloads the first that decodes as an image ≥ 320 px, and
**caches** it at `work/bg_cache/<query-slug>.jpg`. Subsequent renders reuse the cache,
so output is **stable and instant** (and the same query in two beats reuses one file).

Openverse indexes Creative-Commons images (Flickr, Wikimedia, museums, …) with real
tags, so keyword relevance is good: `"corporate office room interior desks"` → an actual
open-plan office; `"person at computer desk office"` → a desk with monitors; `"dark
starry night sky space"` → a starfield.

## Fallback chain

1. `bg.image` — an explicit local/AI-generated file path (used verbatim if it exists).
2. `bg.img` — an Openverse query (fetched + cached).
3. `bg.palette` — if no image is available, a painted **gradient scene-card** (with a
   faint giant watermark word) is generated instead, so a render never fails on a
   network hiccup.

## Making a photo legible behind text + cats

`make_background()` post-processes the fetched photo:

- center-crop to fill the canvas (`cover()`),
- overall dim ~21 % + a stronger dark gradient across the top band (so the white POV
  bubble and action caption stay readable),
- soft **contact shadows** under each cat's feet.

## Choosing good queries

Relevance depends heavily on the query. Lessons:

- **Be specific and concrete.** `"office"` alone returned a police car once; `"corporate
  office room interior desks"` reliably returns an office.
- **Add `interior` / `room`** for indoor scenes, or you may get exteriors/objects.
- **Describe the vibe** for abstract beats: "inside my head" → `"dark starry night sky
  space"`.
- If a fetched image is wrong, change the query and delete the stale
  `work/bg_cache/<slug>.jpg` (or just use a new query string → new cache key).
- To **lock** a background forever, download the one you like and point `bg.image` at it.

## Sources that were tried and rejected

| source | verdict |
|--------|---------|
| `loremflickr.com/WxH/<kw>` | keyless but **irrelevant** — returned a sheriff's car for "office", a cat statue for "car". Random Flickr tag roulette. Rejected. |
| `source.unsplash.com` | **dead** — returns HTTP 503 (Unsplash deprecated the endpoint). |
| `picsum.photos` | works but **no keyword support** — random images only. Fine as a generic fallback, useless for scene relevance. |
| Pexels / Unsplash / Pixabay APIs | high quality + relevant but **require an API key** (not available here). Good upgrade if you have keys. |
| Wikimedia Commons search API | keyless and relevant; viable alternative/secondary to Openverse. |

## Possible upgrades

- Plug in a **paid stock API** (Pexels/Unsplash) for higher-quality, more consistent
  photos — swap the `fetch_image` body, keep the cache.
- Plug in an **image generator** (point `bg.image` at generated files) for fully bespoke
  scenes — the reference channel appears to do this for some stylized backgrounds.
- Add a couple of **fetch fallbacks** (Openverse → Wikimedia → picsum) for robustness.
