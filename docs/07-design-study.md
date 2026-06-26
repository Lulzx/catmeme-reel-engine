# 7. Design study — @theRaccoon1 cat-meme shorts

This is the reference that drove the renderer redesign. I downloaded **all 11 shorts**
from [youtube.com/@theRaccoon1/shorts](https://www.youtube.com/@theRaccoon1/shorts) and
extracted 6 evenly-spaced frames from each to study the design system frame-by-frame.

## The 11 videos studied

| id | title | views |
|----|-------|-------|
| f2Z4qWfmtyk | Using phone at 2am | 39k |
| QkP_dgb0kEQ | Mom calls you for no reason | **179k** |
| 8W_yHvEE8dY | Dad teaches me how to drive | 33k |
| ydftGORMrEA | Mom asks you to find something | 46k |
| ind0nnF13jo | Grandma comes to visit | 22k |
| -qON8yL3M5Y | Going to visit grandma | 22k |
| bH8RMV9pKoc | Having sleepover with friends | 28k |
| -U6dn-23W1I | Baby banana cat goes to school trip | 7.9k |
| rDI8CHp_Nr4 / z0FfHjPJLBQ / 8MqdhAvks2Y | First Day at School (Parts 1–3) | ~30k each |

Format across all: **1080×1920 portrait, ~37–43 s, ~6–9 beats.**

## The design system (what every video shares)

### 1. Constant top header
- Usually a **white rounded speech bubble** with **black bold text**: `POV: <premise>`
  (e.g. "POV: Mom calls you for no reason"). It does **not** change during the video.
- Alternatively a **series banner**: `🎒 FIRST DAY AT SCHOOL 🎒` (decorative emoji) with
  a **`PART N`** label at the bottom-center.

### 2. Named characters
- **Every cat carries a name label** placed right above/beside it: `Me`, `Mom`, `Dad`,
  `Grandma`, `Sis`, `James`, `David`, `Teacher`, `My Friend`.
- Style: **bold white text with a black outline.** Case is inconsistent across videos
  (some ALL-CAPS, some Title/lowercase) — the outline is the constant.
- **1–3 cats per scene.** Two characters commonly **face each other** (Me ↔ Mom/Dad).
  Family stories field three at once (Me + Sis + Grandma).

### 3. Per-beat action / dialogue captions
- Small **white text with black outline**, lower/mid screen, changing every beat.
- Two flavors: **stage directions in asterisks** (`*getting ready for school*`,
  `*scared for my life*`, `*Peacefully Sleeping*`) and **dialogue in quotes**
  (`"Now start the car"`, `"we need your parents signature"`, `"I dont like any"`).

### 4. Cats are grounded, not floating
- Each cat is keyed and **placed on a surface** — on the bed, the couch, a car seat,
  the stairs, the floor — at a believable size (head+body ≈ **30–45 % of frame height**)
  and a distinct horizontal position. They read as *in* the room.

### 5. Cozy, photoreal backgrounds
- Warm, specific interiors: bedroom, living room, kitchen, car interior, staircase,
  dining room, house exterior, shops. A few look **AI-generated/stylized** (the very
  colorful bag shop in "First Day at School").
- Backgrounds are used two ways:
  - **Reused across consecutive beats** within one location (e.g. the kitchen for
    "*making breakfast*" then "*having breakfast*") — only the action + cat change.
  - **Changed to show movement** through a space (bedroom → stairs → living room) and
    **travel scenes** (a road, a car interior) used as connective tissue ("*on the way
    to grandma's*").

### 6. Props
- Small object cut-outs are composited in to tell the story: a **phone** on the bed,
  a **bowl of snacks**, **spaghetti**, **luggage**, a **school bag**, **corn**.

### 7. Macro-structure & extras
- Arc: **premise → setup beats → escalation → climax (often two characters together)
  → punchline/resolution.**
- Occasional **mid-video title card** (`THE ANNOUNCEMENT`, `TIME TO ASK PARENTS`).
- Frequent **end "SUBSCRIBE" card**; multi-part stories cross-promote (`PART 2`).
- Pacing: beats ~3–6 s. Mostly hard cuts; one video used a "blanket pulled over the
  camera" wipe as a transition.

### 8. Audio
- The cats' own meow/scream sounds are kept, typically over a light background music
  bed. (We currently keep clip audio + loudness-normalize; a music bed is a TODO.)

## What we adopted (and where it lives)

| Raccoon1 element | our implementation |
|------------------|--------------------|
| POV speech bubble | `make_overlay()` white `rounded_rectangle` + Arial Bold, from `story.pov` |
| character labels | `make_overlay()` labels list, Arial Black + stroke, positioned above each cat via `bbox` |
| `*action*` captions | `make_overlay()` action text, Arial Bold Italic + stroke, placed **near the cat just above its label** (as in the reference), per beat |
| grounded cats | `layout()` grounding math using catalog `bbox` + per-cat `size`/`pos`/`baseline` |
| contact shadows | `make_background()` blurred ellipses at each cat's feet |
| multi-character scenes | beat `cast: [...]`, default position spread, `flip` to face each other |
| cozy backgrounds | Openverse fetch by query ([06](06-backgrounds.md)) |
| facing each other | cast `flip: true` (horizontal mirror) |
| end card | `story.outro` → appended card beat (Impact, centered) |

## What we have NOT done yet (gaps vs. the reference)

- **Prop cut-outs** (phone/food/bag PNGs) — would need a small transparent-PNG library
  and per-beat placement; straightforward to add.
- **Background music bed** — needs a royalty-free source; would mix under the cat audio.
- **Mid-video title cards** and **transition wipes** — easy to add as beat types.
- **Same-cat-as-recurring-character** consistency — the reference reuses *different*
  reaction cats for "Me" each scene (so do we); true character consistency isn't a goal.
