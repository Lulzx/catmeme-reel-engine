# 8. Authoring stories (`story.json`)

A story is pure text — premise, beats, named characters, desired emotions, background
queries. No clip IDs, no pixel work. This is the file a human or an LLM writes.

## Full schema

```jsonc
{
  "title": "Asking My Boss For A Raise",        // metadata
  "output": "final.mp4",                          // output path (project-root relative)
  "canvas": { "w": 1080, "h": 1920, "fps": 30 }, // portrait reel (use 1920x1080 for landscape)
  "max_beat_dur": 4.5,                            // default per-beat cap (seconds)
  "baseline": 0.9,                                // default feet line (fraction of height)
  "pov": "POV: you finally asked your boss for a raise",  // constant top bubble
  "outro": "FOLLOW FOR PART 2",                   // optional end card (omit to skip)
  "outro_cast": [ { "want": ["cute","dancing"], "size": 0.44 } ],  // optional cat on the card

  "beats": [
    {
      "action": "*walking in like I own the place*", // italic caption ("dialogue" also ok)
      "dur": 5.0,                                     // optional override of max_beat_dur
      "bg": {
        "img": "corporate office room interior desks", // Openverse query (fetched+cached)
        "image": "/abs/path/to/local.jpg",             // OR pin a local/AI image
        "palette": "office"                             // gradient fallback if no image
      },
      "cast": [
        {
          "name": "BOSS",                  // label drawn above this cat (uppercased)
          "want": ["angry","glaring"],     // desired emotion -> matcher picks the clip
          "query": "optional free text",   // extra weak matching signal
          "clip": "027",                   // OR pin an exact clip id (skips the matcher)
          "pos": 0.67,                     // center-x 0..1 (auto-spread if omitted)
          "size": 0.46,                    // cat height as fraction of canvas height
          "baseline": 0.9,                 // this cat's feet line (overrides beat/story)
          "flip": true,                    // mirror horizontally (e.g. to face another cat)
          "key_similarity": 0.19           // chroma-key tolerance override
        }
      ]
    }
  ]
}
```

### Required vs optional

- **Required per beat:** `cast` (≥1 member, unless it's a card beat) and a `bg`.
- **Required per cast member:** one of `want` / `query` / `clip`, and usually `name`.
- Everything else has sensible defaults (see [05-renderer.md](05-renderer.md)).

## How to write a good one (lessons from the reference)

1. **One constant `pov` premise.** Phrase it as a relatable POV: "POV: mom calls you
   for no reason". It never changes during the video.
2. **Each beat is a moment**, captioned with an `*action*` (stage direction) or a line
   of `"dialogue"`. Keep them short — they're small on screen.
3. **Name your characters** (`ME`, `MOM`, `BOSS`). Reuse names across beats; the cat
   clip can differ each time (the reaction changes, the character doesn't).
4. **Use two-character scenes for the climax** — put both cats in one beat with
   `pos` ~0.30 / ~0.70 and `flip: true` on one so they face each other.
5. **Pick `want` tags that exist in the catalog.** Check with
   `python3 engine/match.py <tags...>`. If nothing fits, add a tag to the clip in
   `build_catalog.py` and rebuild.
6. **Write background queries that are specific** ("cozy bedroom interior night", not
   "bedroom"). See [06-backgrounds.md](06-backgrounds.md).
7. **Reuse a background** across consecutive beats by using the same `bg.img` string
   (the cache returns the same file) — mirrors the reference's "same room, new action".
8. **End with the punchline + an `outro` card.**

## Dry-run the matching before rendering

```bash
python3 - <<'PY'
import json, sys; sys.path.insert(0,"system"); import match as M
s=json.load(open("data/stories/functional-adult.json")); cat=M.load_catalog(); used=[]
for i,b in enumerate(s["beats"]):
    for c in b.get("cast",[]):
        _,clip,_=M.best(c.get("want",[]),c.get("query",""),cat,exclude=used); used.append(clip["id"])
        print(f"beat {i} {c.get('name','?'):6s} -> [{clip['id']}] {clip['primary']}")
PY
```

## Render

```bash
python3 engine/render.py data/stories/functional-adult.json     # -> output/final.mp4
```

The render log prints, per beat: duration, chosen clip id(s), character names, and the
action line — your at-a-glance confirmation that the story resolved correctly.
