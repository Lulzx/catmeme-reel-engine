# 2. Environment, tooling & quirks

Documents the actual machine this was built on and the constraints that shaped the
design. If you move the project, re-check these.

## Tooling present

| tool | path | used for |
|------|------|----------|
| `yt-dlp` | `/opt/homebrew/bin/yt-dlp` | downloading the playlist & reference videos |
| `ffmpeg` / `ffprobe` | `/opt/homebrew/bin/` | all video probing & compositing |
| `python3` | `/opt/homebrew/bin/python3` (3.14) | catalog, matcher, renderer |
| **Pillow** | site-packages, **v12** | ALL text + background image work |
| `jq` | `/usr/bin/jq` | ad-hoc JSON poking |

Not present: **ImageMagick** (`magick`/`convert` missing) — not needed, Pillow covers it.

`yt-dlp` was a bit old (2026.03.17) and warns about it; it still worked. `pip install -U
yt-dlp` if future downloads fail.

## ⚠️ The big quirk: this ffmpeg has NO text/`drawtext`

The local ffmpeg build was compiled **without** `libfreetype`, `libass`, or
`fontconfig`, so these filters do not exist:

```
$ ffmpeg -filters | grep -E 'drawtext|subtitles|ass'   # -> (nothing)
```

Consequence: **we cannot burn text with ffmpeg.** Every caption, the POV bubble,
character labels, and scene backgrounds are instead rendered as **PNGs with Pillow**
and then **overlaid** with ffmpeg's `overlay` filter. This is actually nicer — full
typographic control, rounded boxes, stroke outlines, gradients — but it's a hard
constraint to remember: *if you want text on screen, draw it in Pillow, don't reach
for `drawtext`.*

If you ever get an ffmpeg with text support, you could simplify, but the Pillow path
is more capable, so there's little reason to.

## Fonts (macOS)

Pillow loads TTFs by absolute path. The ones used:

| role | file |
|------|------|
| POV bubble (black on white) | `/System/Library/Fonts/Supplemental/Arial Bold.ttf` |
| character labels (ME/BOSS) | `/System/Library/Fonts/Supplemental/Arial Black.ttf` |
| `*action*` caption | `/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf` |
| end card | `/System/Library/Fonts/Supplemental/Impact.ttf` |

`font()` in `render.py` falls back to `ImageFont.load_default()` if a path is missing,
so a different OS won't crash — but swap the paths for good-looking text on Linux.

Emoji do **not** render with these fonts (they'd show as boxes), so labels/cards are
kept ASCII. Add an emoji-capable font (e.g. Noto Color Emoji) if you want 🐱.

## Network

Outbound HTTPS works from both `Bash` (curl) and Python `urllib`. Notes:

- Background images come from the **Openverse API** (keyless). See
  [06-backgrounds.md](06-backgrounds.md).
- Python TLS in this env needed an **unverified SSL context**
  (`ssl.CERT_NONE`) to fetch reliably — fine for public CC images, don't reuse that
  pattern for anything security-sensitive.
- A descriptive `User-Agent` header is sent (some endpoints reject the default).

## Scratch space

Temporary analysis files (reference video downloads, contact sheets) were kept in the
session scratchpad, **not** in the project. Only the engine + outputs live in the repo.
