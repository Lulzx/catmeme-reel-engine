# 10. How-to recipes

Copy-paste workflows. Run from the project root (`cat-videos/`).

## Render the current story

```bash
python3 engine/render.py data/stories/functional-adult.json     # -> output/final.mp4
```

## Make a new video

1. Edit `data/stories/functional-adult.json` (schema in [08-authoring-stories.md](08-authoring-stories.md)).
2. (Optional) dry-run the clip matching — see that doc's "Dry-run" snippet.
3. Render (above). The log prints chosen clips per beat.

Stories live in `data/stories/`; pass the path to render a specific one:

```bash
python3 engine/render.py data/stories/asking-for-a-raise.json
```

## See what clip an emotion resolves to

```bash
python3 engine/match.py screaming rage outburst
python3 engine/match.py smug confident rizz
```

## Rebuild the catalog (after adding/removing clips or editing emotion tags)

```bash
python3 engine/build_catalog.py        # re-probes, re-samples key-colors + bboxes
```

It **auto-extracts** each clip's representative frame into `work/frames/` if missing, so
it's self-contained. To add a new clip: drop the file in `clips/` (named `NN - Title
[id].ext`), add an emotion entry for `NN` in the `EMO` dict in `engine/build_catalog.py`
(and optional taxonomy tags in `TAX_ADD`), then rerun the build.

## Download the source playlist (already done once)

```bash
yt-dlp --no-update --ignore-errors --no-overwrites \
  --download-archive clips/archive.txt \
  -o "clips/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s" \
  "https://www.youtube.com/playlist?list=PLfO7PvU9iHnxdfs1LiAYg9dG9MlBKEDE5"
```

`--download-archive archive.txt` makes re-runs skip what's already downloaded.

## Force-refresh a background image

The fetched photo for a query is cached. To get a different one, either change the
`bg.img` text (new cache key) or delete the cached file:

```bash
rm "work/bg_cache/corporate_office_room_interior_desks.jpg"
```

To lock a background permanently, save the image you want and point the beat at it with
`"image": "/abs/path/to/it.jpg"`.

## Switch to landscape (16:9)

In `story.json` set `"canvas": { "w": 1920, "h": 1080, "fps": 30 }`. The renderer adapts
cat sizing and text scale automatically.

## Inspect intermediate artifacts

```bash
open work/bg_render/beat_03.png      # composited background + shadows for beat 3
open work/overlays/ov_03.png     # the transparent text overlay for beat 3
open work/beat_clips/beat_03.mp4     # the finished beat
ffprobe -v error -show_entries format=duration -of csv=p=0 final.mp4   # final length
```

## Verify audio isn't silent / is balanced

```bash
ffmpeg -nostdin -i final.mp4 -af volumedetect -f null - 2>&1 | grep volume
```
