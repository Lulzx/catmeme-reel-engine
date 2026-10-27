# 20 · The group-chat format (2026-10-27)

A second reel format, built because every reel on the channel had the same shape
(doc 19: no outliers, max ÷ median = 3.2x). Instead of a POV bubble over cats on a
scene background, the whole reel is a phone screen showing a **family group chat
where every member is a cat**.

- Texts pop in with message sounds and a smooth scroll.
- The header shows live status: "Mummy is recording video…", "Papa is typing…".
- Cats appear as round **video notes** that play the keyed clip, with its own
  audio, over a background that fits the character (Mummy in the kitchen, Sharma
  ji's son at the gym).
- Reactions, deleted messages, forwards, "X added Y" and "You left" are all
  events, which gives the writer far more ways to land a joke than a caption.

First episode: `data/chats/i-got-the-job.json`, posted 2026-10-27 as
[youtu.be/23gG-ZnxyTk](https://youtu.be/23gG-ZnxyTk).

## Why this format

- **It looks nothing like the other 365 reels.** Someone scrolling past who has
  learned to skip the POV-bubble look gets a different first frame.
- **It fits the audience we have.** Comments respond to South Asian specifics
  (doc 19). The family group is the most shared experience in that audience:
  good morning forwards, "vgm", "package?", the forwarded health tip, the parent
  who adds the rival's son to the group.
- **The recurring cast fits the roles.** Yapapa (182) is the relative who sends a
  4:37 video note. DEREK (184) is Sharma ji's son and his laugh is the villain's
  sound. The small German cat (183) is the relative with the unhelpful forward.
- **Roles, not names.** Papa, Mummy, Chachu, Bua, Sharma ji's son. No personal
  names (doc 19: "who is ajay").

## Render and publish

```bash
python3 engine/chat_render.py data/chats/<slug>.json              # -> output/<slug>.mp4
python3 engine/chat_render.py data/chats/<slug>.json --register   # also queue in videos.db
python3 -m engine.upload <slug>                                   # publish now
```

A ~28s reel renders in about 15 seconds. `--register` adds the reel as `queued`,
using the script's `youtube` block for title, description and tags, and records
every clip it shows in `clip_usage`, so the diversity allocator (doc 16) sees chat
reels too. After that, `--next`, `--fill-schedule` and the Studio scheduler treat
it like any story reel.

## The script

`data/chats/<slug>.json` is a cast plus a timeline. One event per line keeps it
readable; copy the first episode as a template.

```jsonc
{
  "title": "told the family group i got the job",
  "output": "i-got-the-job.mp4",
  "group": { "name": "Family 🙏❤️", "members": "Papa, Mummy, Chachu, Bua, You",
             "avatars": ["146", "174", "091", "183"] },     // header collage, up to 4
  "clock": "9:41",                                           // status-bar time
  "youtube": { "pov": "...", "title": "... #shorts", "description": "...", "tags": [...] },
  "people": {
    "me":    { "name": "You" },                              // "me" is always the right side
    "papa":  { "name": "Papa", "color": "#1E73D8", "avatar": "146" }
  },
  "events": [ ... ]
}
```

### Events

Every event has a `t` in seconds. `t: -1` means already in the chat when the reel
starts (no pop-in, no sound), which is how the opening frame gets its context.

| type | fields | what it does |
|---|---|---|
| `chip` | `text` | centred white date chip ("TODAY") |
| `system` | `text` | centred yellow chip: "Papa added Sharma ji's son", "You left" |
| `text` | `from`, `text`, `time`, `forwarded?`, `id?` | message bubble; outgoing for `me`, incoming with avatar and coloured name otherwise |
| `image` | `from`, `card: "good-morning"`, `card_cat`, `forwarded?`, `time` | the forwarded good-morning image, with a cat sprite on it |
| `video` | `from`, `clip`, `start`, `dur`, `bg`, `label`, `fit?` | video note: keyed clip in a circle over a blurred `backgrounds/` image, playing its own audio, with a progress ring; `label` is the duration pill (it can lie: "4:37" on a 3s clip is a joke) |
| `compose` | `text`, `until` | types into the input bar letter by letter with key clicks; follow it with the matching `text` event |
| `status` | `text`, `until` | replaces the header subtitle ("Papa is typing…") |
| `typing` | `from`, `until` | three-dot typing bubble |
| `delete` | `target` | turns the message with that `id` into "🚫 This message was deleted" |
| `react` | `target`, `emoji`, `by?`, `sound?` | reaction badge under the message; with `by`, an iOS-style notification drops over the header; `sound: {clip, start, dur}` plays a clip's audio with it |
| `end` | | the reel's length |

`fit` (default 0.95) is the cat's height as a fraction of the circle. Use about
0.8 for clips framed as a big face (182, 184) so the head isn't cropped.

### Pacing that worked

- Sent and received texts: about 0.7s apart for a quick back-and-forth, about 1s
  when the reader needs to take in a longer line.
- A `status` or `typing` for 0.5s before each incoming message or video note. A
  long `typing` (1.5s) builds anticipation before a punchline.
- Video notes: 2–3.5s. Pick `start` from the clip's audio (`silencedetect`), so
  the note starts on the sound, not on silence.
- Hold the final event for about 1.3s before `end`.

## Writing one

Doc 15's voice rules still apply to every message: lowercase, specific ("40 LPA",
"4:37"), no em dashes, no noun-phrase punchlines. The chat adds a few of its own:

1. **The first frame sets the scene.** Start with `t: -1` history the audience
   recognises instantly (the good-morning forward, "vgm"), then the hook message
   being typed in the input bar.
2. **Escalate by adding people.** "Papa added Sharma ji's son" is the turn. A new
   member joining is this format's version of a two-cat climax beat.
3. **Use the chat mechanics as punchlines.** Deleting, "wrong chat", a reaction
   from the wrong person, "You left" then "Papa added you". The UI already makes
   these funny, so the text can stay plain.
4. **Video notes are the cats' lines.** Put the loudest clips (sobbing, laughing,
   yapping) in video notes; give the deadpan cats text and an avatar.
5. **Write the ending first**, same as the story format.

## How the renderer works

`engine/chat_render.py`, all Pillow + ffmpeg + numpy, same toolchain as the rest
of the engine:

- Every chat item is drawn once as an RGBA image (bubble, chip, card), with timed
  variants for `delete`. Video notes are drawn per frame from a keyed PNG sequence
  (`work/chat/<slug>/noteNN/`), extracted with the same crop and chroma chain as
  `cutouts.py`.
- Each frame stacks the visible items, scrolls so the newest is at the bottom
  (eased, 0.32 per frame), pops new items in with an ease-out-back scale, then
  draws the header, input bar and any notification banner. Raw RGB frames are
  piped to ffmpeg (x264, CRF 17).
- Text is SF Pro (`/System/Library/Fonts/SFNS.ttf`, weights picked via variation
  names). Emoji are Apple Color Emoji drawn at 160px and scaled down; text is
  split into word and emoji runs and wrapped by hand.
- Audio is mixed in numpy at 48 kHz: each clip segment RMS-normalised and faded,
  plus synthesised sounds (send, receive, system, delete, react, key clicks), then
  a soft `tanh` limiter. Peaks land around −1.3 dBFS.

### Gotchas

- Pillow's `get_variation_names()` returns **bytes**; `set_variation_by_name`
  needs `b"Semibold"`, not `"Semibold"`.
- Apple Color Emoji only renders at its bitmap sizes; 160 is the one to draw at.
- SF Pro has no glyph for `↪`, so the forward mark is drawn with lines.
- The renderer is macOS-only as written (SF Pro, Apple Color Emoji, Snell
  Roundhand paths).
