# 21 · The prime-time debate format (2026-10-27)

The third reel format, after POV stories and the group chat (doc 20). A tiny
household crime is covered like national breaking news on a shouting TV debate
show, the kind every Indian household has had on at 9 pm.

- A red **BREAKING NEWS** sting opens the reel, with a whoosh and a boom.
- An all-caps **headline** banner changes as the debate turns
  ("PAPA REFUSES TO COMMENT").
- The **panel grid** grows from the anchor alone to 2, then 4, then 6 tiles as
  family members and "experts" join. New tiles slide in from below and the grid
  re-flows.
- Whoever is speaking gets a yellow border and their clip's audio; the others
  dim and loop quietly.
- A **quote box** shows the current line, a **ticker** scrolls the running
  facts, and a **market strip** tracks the household economy (MAGGI ▼100%).
- **Crosstalk**: everyone shouts at once, the screen shakes and the ticker speeds up.
- An **EXCLUSIVE** sting cuts to night-vision **CCTV** with a running timestamp,
  REC light and an **ENHANCE** zoom onto the culprit's face.
- **Colour bars** with "TECHNICAL DIFFICULTY" and a 1 kHz beep can replace any
  tile, which is how a panelist walks off.

- A deadpan **announcer voice-over** (Fish Audio) opens the show, reads the anchor's
  calm lines and every absurd headline completely straight, and announces the reveal
  before the culprit's feed cuts to bars. The cats keep their own sounds.

First episode: `data/news/who-ate-the-last-maggi.json` (98.5s). The anchor is the
elder son hosting a debate about his own house, and the CCTV catches him.

## Length and pacing

Take your time. The first cut of the first episode ran 56 seconds and felt rushed:
lines changed before they could be read, and the escalation blurred together.
The published cut runs about 90 seconds (Shorts allow up to 3 minutes). Doc 19's
finding that shorter reels did better was for the POV-story format; a debate is
read, not glanced at.

- **Hold each quote for about 1.4s plus 0.4s per word, at least 2.2s.** A 9-word
  line holds about 4 seconds. Leave 0.4s between lines.
- **Pause about 1s after each layout change** before anyone speaks, so the viewer
  sees who just joined.
- **Give a headline that lands on its own about 2s** before the next line.
- **Stings last 1.4s.**
- The cat's audio plays for the whole time its line is up (from `start`, until
  `until` or the end of the clip), with a 0.25s fade-out. Don't size `dur` to
  the first burst of sound; that cuts the cat off mid-line.

## Render and publish

```bash
python3 engine/news_render.py data/news/<slug>.json              # -> output/<slug>.mp4
python3 engine/news_render.py data/news/<slug>.json --register   # also queue in videos.db
python3 -m engine.upload <slug>                                  # publish now
```

A 98s reel takes about a minute end to end: ~30s of ffmpeg prep, then ~27s of GPU
rendering (the first render after a build takes ~55s while decoders and shaders warm up).
Rendering needs Rust (`rustup`) and `brew install pkg-config x264 x265 opus nasm ninja`;
`news_render.py` builds `engine/ff_debate` on first use. `--register` works like the chat
renderer's: it queues the reel using the script's `youtube` block and records the
panel's clips in `clip_usage`.

## The script

```jsonc
{
  "title": "who ate the last maggi",
  "output": "who-ate-the-last-maggi.mp4",
  "clock": "9:00 PM",
  "market": "MAGGI ▼100% • PARLE-G ▲2% • ...",          // ▲ green, anything else red
  "voice": { "id": "0380b387bf9a4a8b8e5e2df81ecdc077", "model": "s2.1-pro-free" },  // Fish Audio "Breaking news"
  "youtube": { "pov": "...", "title": "... #shorts", "description": "...", "tags": [...] },
  "panel": {
    "anchor": { "name": "ANCHOR", "role": "ELDER SON • HOST", "clip": "170",
                "bg": "studio", "fit": 0.86, "idle": 0.0, "idle_span": 1.2, "loud": 2.08 }
  },
  "events": [ ... ]
}
```

Panelist fields:

| field | meaning |
|---|---|
| `name`, `role` | the two-line name plate (red name bar, white role bar) |
| `clip` | catalog id; the whole clip (up to 12s) is keyed once into `work/news/<slug>/<key>/` |
| `bg` | a `backgrounds/` image, or `"studio"` for the drawn news-studio backdrop |
| `fit` | cat height as a fraction of the tile (0.8 for big-face clips) |
| `idle`, `idle_span` | while not speaking, the tile ping-pongs through this window of the clip; pick a quiet stretch so the cat looks like it's listening |
| `loud` | where this panelist's clip starts during crosstalk |

### Events

| type | fields | what it does |
|---|---|---|
| `sting` | `text`, `until`, `style?: "exclusive"` | full-screen sting (red, or black and gold for exclusive) with whoosh and boom |
| `layout` | `tiles: [keys]` | which panelists are on screen, in order; 1, 2, 4 or 6 tiles, with an eased re-flow |
| `headline` | `text` | swaps the banner (slides in); write it in caps, it's the genre |
| `ticker` | `text` | sets the scrolling ticker |
| `speak` | `who`, `start`, `until`, `quote`, `silent?` | plays the clip from `start` with audio and spotlights the tile until `until` (audio stops early only if the clip runs out); `silent: true` shows the quote with no audio, for calm anchor lines |
| `chaos` | `until`, `name`, `quote` | crosstalk: every panelist's `loud` audio at once, shake, fast ticker |
| `cctv` | `who`, `start`, `dur`, `until`, `bg`, `label`, `clock`, `date`, `enhance?`, `zoom`, `face_y`, `name`, `quote` | night-vision footage in the tile area; holds the last frame after `dur`; `enhance` is the time the zoom starts |
| `bars` | `who`, `beep` | colour bars replace that panelist's tile from then on |
| `voice` | `text`, `speed?` | the announcer says `text` at `t`; everything else ducks 9 dB under it. Write numbers and times the way they should be read ("two fourteen A M") |
| `end` | | the reel's length |

The quote box keeps the most recent quote until the next one, so there's never
an empty box between lines.

## Writing one

The voice rules in doc 15 apply to every quote: lowercase, specific ("4 packets
on sunday", "2:14 am", "class 4"), no em dashes. Headlines are the exception and
stay in caps, because that's what the parody is of.

1. **The crime is tiny and specific.** The last Maggi, the geyser left on, the TV
   remote, the AC temperature, the missing charger. The show treats it like a
   national scandal.
2. **Cast by household role.** Papa, Mummy, Chhotu, the elder son, Sharma ji's
   son, a "forensic expert". Keep the recurring cast in their parts: yapapa (182)
   is Mummy in both new formats, DEREK (184) is Sharma ji's son, the small German
   cat (183) gives the useless expert opinion.
3. **Give one panelist a running line.** Papa answers everything with "huh?"
   (clip 004's flat meow) and the headline keeps reporting that he refuses to
   comment. Three times is the right number.
4. **Escalate in this order:** anchor alone, family joins, experts join,
   accusations, crosstalk, exclusive footage, reveal. The grid getting more
   crowded is the escalation.
5. **The reveal should turn on the show itself.** The anchor is the culprit, the
   expert is the culprit, or the footage shows something nobody expected. Then
   take the guilty party off air with colour bars.
6. **For the reveal, use the same clip** in the culprit's tile and the CCTV, so
   viewers recognise the cat even in night vision.
7. **End the ticker on a tease** for the next episode ("next at 10: who left the
   geyser on").

## How the renderer works

Two halves. `engine/news_render.py` prepares media with ffmpeg and numpy (no
drawing), then `engine/ff_debate` (Rust, [fframes](https://github.com/dmtrKovalenko/fframes))
draws every frame as an SVG tree on the GPU (Skia on Metal) and encodes it.

Prep, into `work/news/<slug>/media/`:

- `track_<who>.mp4` per panelist: the clip's green-screen crop, re-sequenced so frame
  *i* is exactly what that tile shows at reel frame *i* (the speaking segment,
  crosstalk, or a ping-pong loop of the `idle` window). Encoded 4:4:4 so the key sees
  full-resolution chroma.
- `bg_<who>.jpg` the tile background, pre-blurred; the studio backdrop is drawn in SVG.
- `cctv.mp4` the whole CCTV shot as an ffmpeg graph: keyed clip over its room,
  `zoompan` for ENHANCE, then grain, green tint, scanlines and vignette.
- `audio.wav` the mix: clip audio (RMS-normalised), synthesised sting/beeps/news bed,
  and the announcer lines from `engine/voice.py`, with everything else ducked under them.
- `timeline.json` the resolved script.

Render (`engine/ff_debate/src/lib.rs`): each frame picks the layout, eases tile rects
toward the grid, and per tile draws the background, the decoded track frame through
`shaders/key.sksl` (the same chromakey + despill maths as `cutouts.py`), the dim
overlay, name plate and border. Headline, quote, ticker, market strip, stings, CCTV
overlays and colour bars are plain SVG text and shapes in Impact, Arial and Menlo,
loaded from the system. Measured text layouts are cached per headline and quote.

Reviewing without rendering, from `engine/ff_debate` with `FF_WORK` pointing at the
prepared media folder:

```bash
export FF_WORK=../../work/news/<slug>/media
cargo run --release -- inspect               # missing fonts/media, clipped text, bad SVG
cargo run --release -- strip 10s,30s,70s     # contact sheet
cargo run --release -- audio analyze         # LUFS, peaks, clipping
cargo run --release -- preview 60s           # real-time window with sound
```

## Voice-over

`engine/voice.py` calls the Fish Audio TTS API and caches each line in
`work/voice/<hash>.wav` (keyed on text, voice, model and speed), trimming the model's
leading and trailing silence so lines land on their cue. The key comes from
`FISH_API_KEY` or `fish_api_key.txt` at the repo root (gitignored).

- The account has no paid API credit, so scripts use `s2.1-pro-free`; `s2.1-pro`
  returns 402 "Insufficient API credit" until credit is added at fish.audio/app/developers.
- The free model only accepts 8, 16, 24, 32 or 44.1 kHz; the client asks for 44.1 kHz
  and ffmpeg resamples to 48 kHz for the mix.
- Prep prints every line with its measured length and flags any that run into the next
  panelist; retime the script until none are flagged.

### Gotchas

- Events of different types are kept in separate lists. Anything that looks up
  "the latest event" across lists must sort by `t` first, or the last list wins
  (the first render showed the CCTV caption for the rest of the reel).
- Impact and SF have no glyph for some symbols (▬); stick to ▲ ▼ • in the
  ticker and market strip.
- The first cut sized each line's audio to the clip's first burst of sound
  (0.4–2.6s) while the quote held for 2–3s, so every cat went quiet mid-line.
  Audio now runs for the whole spotlight.
- The first renderer drew frames with Pillow: about 5 minutes for 90s single-process,
  98s across 12 processes, most of it re-resizing and re-blurring the same
  backgrounds. fframes on the GPU renders the same reel in about 27s.
- `--work` can't be a required global flag (fframes' CLI parses arguments more than
  once), so it's optional with the `FF_WORK` environment variable as the fallback.
- `frame.text_width` only measures strings that live as long as the video, so
  wrapping measures word by word from the script's own strings.
