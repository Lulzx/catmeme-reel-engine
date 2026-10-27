# ff_debate

The [fframes](https://github.com/dmtrKovalenko/fframes) renderer for prime-time debate
reels (1080x1920 @ 30 fps, Skia on Metal). It draws what `engine/news_render.py`
prepares; normally you run that instead:

```sh
python3 engine/news_render.py data/news/<slug>.json      # prep + build + render
```

| file | what |
| --- | --- |
| `src/lib.rs` | the video: tiles, headline, quote box, ticker, stings, CCTV, colour bars |
| `src/main.rs` | the command line (`fframes::cli`), reading the media folder from `--work` / `FF_WORK` |
| `src/shaders/key.sksl` | GPU green-screen key (same maths as `engine/cutouts.py`) |

Reviewing a prepared episode without a full render:

```sh
export FF_WORK=../../work/news/<slug>/media
cargo run --release -- inspect              # missing fonts/media, clipped text, bad SVG
cargo run --release -- strip 10s,40s,80s    # contact sheet, writes strip.png
cargo run --release -- audio analyze        # loudness, peaks, clipping
cargo run --release -- preview 60s          # real-time window with sound
```

Fonts (Impact, Arial, Menlo) load from macOS. See `docs/21-prime-time-debate.md`.
