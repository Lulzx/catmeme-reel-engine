# 5. The renderer — story → video

`engine/render.py`. The only component that touches pixels and audio. It walks the
story's beats, builds two PNGs per beat (background + text overlay), composites the
cats with ffmpeg, then concatenates everything into `final.mp4`.

## Per-beat pipeline

```
beat
 ├─ resolve cast clips           (matcher, or pinned ids; exclude already-used)
 ├─ compute geometry per cat      (layout(): where each cat sits — see math below)
 ├─ duration = min(beat.dur, shortest cast clip)
 ├─ make_background(...)          (fetch photo OR gradient, dim, draw contact shadows)  -> work/bg_render/beat_NN.png
 ├─ make_overlay(...)             (POV bubble + action + name labels + card)            -> work/overlays/ov_NN.png
 └─ ffmpeg compositing            (bg + N keyed cats + overlay; audio mix)              -> work/beat_clips/beat_NN.mp4
```

Then a final concat pass joins the beat mp4s.

## Grounding math (`layout()`)

This is what makes cats sit *in* the scene instead of floating. For each cat we know,
from the catalog, its subject bounding box `bbox=[bx0,by0,bx1,by1]` (fraction of the
clip frame) and the frame aspect `cw/ch`.

Given the beat's canvas `W×H` and the cast member's `pos` (center-x fraction),
`size` (desired **visible cat height** as a fraction of `H`), and `baseline` (where the
feet land):

```
bbh    = by1 - by0                      # fraction of frame the cat occupies vertically
dispH  = size * H / bbh                  # scale the whole frame so the CAT is size*H tall
dispW  = dispH * (cw / ch)               # keep frame aspect
Y      = baseline*H - by1*dispH          # frame top so cat's feet (by1) hit the baseline
X      = pos*W - ((bx0+bx1)/2)*dispW     # frame left so cat's center sits at pos
```

Derived anchor points the overlay/shadows use:

```
cat center x = pos*W
cat top y    = Y + by0*dispH             # label is placed just above this
cat width    = (bx1-bx0)*dispW           # drives shadow ellipse size
feet y       = baseline*H                # shadow center
```

The keyed frame is often wider than the canvas (a landscape clip scaled until the cat
is tall enough) — that's fine, the off-canvas transparent margins are simply cropped by
`overlay`. Only the cat matters and it's centered on `pos`.

Default positions when `pos` is omitted: 1 cat → `[0.5]`, 2 → `[0.30, 0.70]`,
3 → `[0.22, 0.5, 0.78]`. Default `size`: 0.46 (solo) / 0.40 (multi). Default
`baseline`: story-level `baseline` (0.9).

## Chroma key

Each cat clip is keyed with its **own** sampled `key_color`, then **despilled**:

```
[k:v]chromakey=0xRRGGBB:0.12:0.08[,hflip],despill=type=green:mix=0.6:expand=0.4,scale=dispW:dispH
```

- similarity `0.12` (per-cast overridable via `key_similarity`) — kept **low on
  purpose**. A high value (we tried 0.19) over-keys dull-green clips and erases the
  cat itself: clip 033's green is desaturated, so 0.19 also matched the grey cat and
  the whole frame went transparent. 0.12 keeps every clip's subject.
- `despill=type=green` then removes the residual **green fringe** that a low similarity
  leaves on bright-green clips (e.g. the rizz cat). This is the key trick: *low
  similarity to keep the cat + despill to clean the edge*, instead of cranking
  similarity and losing cats.
- blend `0.08` softens the matte edge.
- `hflip` (cast `flip: true`) mirrors a cat so two characters can face each other.
- `chromakey` (YUV, blended) is used rather than `colorkey` (RGB, hard) for cleaner edges.

## Compositing graph (N cats)

```
[0:v] scale+crop to W×H                         -> [bg]
[1:v] chromakey,scale                            -> [c0]
[bg][c0] overlay=X0:Y0                            -> [t0]
[t0][c1] overlay=X1:Y1                            -> [t1]      (repeat per cat)
[t_last][OV:v] overlay=0:0, format=yuv420p        -> [v]       (OV = text overlay PNG)
```

Inputs are: `bg.png` (looped image), each cat clip (`-ss 0 -t dur`), the overlay PNG
(looped). The overlay is composited **last** so text sits above the cats.

## Text overlay (`make_overlay`) — Pillow, not ffmpeg

Remember: this ffmpeg has no `drawtext` (see [02-environment.md](02-environment.md)),
so all text is a transparent PNG drawn with Pillow:

- **POV bubble** — white `rounded_rectangle`, black **Arial Bold** text, wrapped to
  ~72 % width, top-centered. Constant across the whole video (`story.pov`).
- **action caption** — **Arial Bold Italic**, white with a black stroke. Positioned
  **down near the cat, just above the highest character's name label** (not pinned under
  the bubble) — matching the reference. Per beat (`*stage direction*` or `"dialogue"`).
- **name labels** — **Arial Black**, white with a thick black stroke, anchored
  bottom-center just above each cat's head (`cat top y`). Uppercased.
- **card** — big **Impact**, centered (used for the end `outro`).

Pillow's `stroke_width`/`stroke_fill` give the meme outline; `anchor` handles centering.

## Backgrounds & shadows (`make_background`)

See [06-backgrounds.md](06-backgrounds.md) for image fetching. Beyond the photo, this
function: dims the image (~21 %) + darkens the top band for caption legibility, then
draws a soft **contact shadow** ellipse (Gaussian-blurred) under each cat at its feet
position — baked into the background PNG before the cats are composited on top.

## Audio

Each cat keeps its own audio. For a multi-cat scene the audios are mixed:

```
[1:a][2:a]... amix=inputs=N:duration=longest:normalize=0, aresample=48000,
              loudnorm=I=-16:TP=-1.5:LRA=11   -> [a]
```

`loudnorm` equalizes loudness across clips (raw clip levels swing from −8 to −27 dB,
which would be jarring). Card beats with no cast get a silent `anullsrc` track so the
streams stay uniform for concat.

## Beat duration

`dur = min(beat.dur or story.max_beat_dur, shortest cast clip duration)`. Bounding by
the shortest clip avoids a cat "running out" and disappearing mid-scene. Set a beat's
`dur` to override (e.g. a 6 s finale).

## Concat

Per-beat mp4s are encoded with identical params, then joined with the concat demuxer
and **re-encoded once** (libx264 CRF 20, AAC 48 k, `+faststart`). Re-encoding at the
join avoids timestamp/keyframe glitches and gives a clean, streamable final file.

## Outputs you can inspect

- `work/bg_render/beat_NN.png` — the composited background (photo + dim + shadows).
- `work/overlays/ov_NN.png` — the transparent text overlay.
- `work/beat_clips/beat_NN.mp4` — the finished beat.
- `work/bg_cache/*.jpg` — downloaded scene photos (reused across renders).
