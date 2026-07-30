# 14 — Performance analytics & trendy clip curation

*(Snapshot: **2026-07-30**, 125 live reels, 113,502 views. Numbers move daily —
re-pull before acting on them.)*

## Pulling the truth

Two ways in, both hitting the same YouTube Data API:

```bash
python3 -m engine.insights              # stats table, ranked by views/day
python3 -m engine.insights --comments   # every comment thread, newest first
python3 -m engine.insights --json       # machine-readable dump
```

It writes a snapshot to `work/insights.json` so analysis doesn't re-burn quota.
The deployed UI (cats.lulzx.space, basic auth) exposes the same data as
`GET /api/schedule` (posting log) and `GET /api/analytics` (live per-video stats),
joined on `video_id`. Either path needs the `youtube.readonly` scope
(`python3 -m engine.upload --auth`).

**The DB drifts from reality and has to be re-synced.** `--schedule-queue` writes
rows as `scheduled`; when YouTube auto-publishes them nothing tells us. On
2026-07-30, 123 rows still said `scheduled` for videos that had been public for
days. Fix: take `privacy`/`published` from the insights snapshot, write
`status='posted'` + the real publish date back into `data/videos.db`, then
`python3 -m engine.upload --sync` to regenerate `youtube.md` and `data/videos.json`.
Do this before any analysis — otherwise "which should I post next?" answers from
a fiction.

Always normalise by days-live. Raw totals favour older posts; **views/day** is
the fair ranking while every video is still inside its discovery window.

## Findings — 125 reels, Jun 27 – Jul 30 2026

908 avg views/reel, ~4 posts/day, 22 comments channel-wide.

**The newest cohort is outperforming the old one by a wide margin.** Top ten by
views/day are all from the last two weeks:

| reel | views/day | like % |
|---|---|---|
| cat-explains-the-universe | 1,100 | 3.9 |
| auto-no-change | 673 | 3.6 |
| push-door-pull | 632 | **8.6** |
| no-rush-four-minutes | 600 | 7.2 |
| at-your-gate-sir | 546 | 3.7 |
| only-one-who-is-hot | 532 | 5.3 |
| empty-bottle-back | 432 | 7.5 |

Against a channel median nearer 50/day for the June cohort. Some of that is
YouTube pushing recent uploads, but the like-rate gap is real and not
recency-driven: 7-8% on the new ones vs 1.5-2.5% on the June batch.

**What the winners have in common — a very small physical friction, described
concretely.** push-door-pull, no-rush-four-minutes, empty-bottle-back,
fan-remote-two-feet, holding-the-lift. No stakes, no escalation ladder, no
"relatable millennial" framing. This is the same shift doc 15 forced on the
writing, and the numbers moved with it.

**The audience is Indian.** The clearest signal in the data. auto-no-change (673
/day) is about an auto driver having no change; at-your-gate-sir is a delivery
driver at the wrong gate; a top comment is *"Plot twist: You pay with Gpay"*.
Heat/AC reels (only-one-who-is-hot, ac-bill-arrives 7.4% likes,
fan-remote-two-feet) all landed. Write for that audience specifically — ₹, autos,
the lane's power cut, the building's water. It's the cheapest relevance available
and it's what the like rate rewards.

**Still-reliable lanes** (unchanged from the last snapshot): social embarrassment
with a witness; phone/internet life; work/office absurdity. **Still weak:**
mundane solo observations with no witness (package-truck, 16/day, remains the
worst reel on the channel).

**Two anomalies worth watching:**

- `dont-open-that-closet` — 18 views in 8.8 days, public, 22% like rate on those
  18. Every other reel cleared 400. This looks like suppressed distribution
  rather than a bad reel; check it in Studio.
- `asking-for-a-raise` — row 1 in the DB, marked posted, but has no `video_id`
  and the API doesn't return it. It was posted before the DB tracked ids.

## What the comments say

22 comments, overwhelmingly positive ("I love you vids keep it up", "Fr tho").
Two are the AI-script complaint that produced doc 15 (`fan-hot-air` → *"Hey
chatgpt"*, `final-day-schedule` → *"Holy AI script"*). One asks for a song name,
one riffs on DEREK (*"Darek the goat?"*) — the recurring-character bet is working
and is worth extending.

## Trendy meme clips (favored in the matcher)

Boosts live in `data/favorites.json`; see [16-clip-diversity.md](16-clip-diversity.md)
for how they interact with the fatigue penalty.

| id | clip | boost | source | role |
|----|------|-------|--------|------|
| 182 | Yapapa cat (mascot) | 1.6 | Zjso08bj1tg | the one who won't stop talking |
| 041 | Laughing cat | 1.2 | aCllAI2m6BI | mocking, bursting out laughing |
| 183 | German Cat | 1.2 | cd2c3-qlYy8 | the small guy with the unhelpful tip |
| 184 | Muhehehe villain-laugh cat | 1.2 | gk2s1IoyN38 | DEREK |
| 185 | OIIA spinning cat | 1.2 | v2yUIWx6jY8 | brain short-circuit, outro card |

Since the 2026-08 batch, **182 and 183 are cast in every reel** as named side
characters rather than left to the matcher.

A July 2026 web-trend check surfaced Dark Cat in the Hat (dominant on TikTok but
copyrighted film footage + grim tone — rejected), Drooling Cat and Folk Valley Cat
(image-based, declined), Chipi Chipi Chapa Chapa and Longing Cat (declined for now).

## Sourcing gotchas (learned adding #184/#185)

- **Inspect frames before cataloging.** The top YouTube hit for "OIIA cat green
  screen" was a suggestive anime-catgirl overlay with a watermark. Tile a frame
  strip (`ffmpeg select= … tile=`) and *look* at it first.
- **Check for repeated-template loops** with `silencedetect` (the yapapa method,
  doc 09): #184 turned out to be three genuine distinct laugh bursts, not a loop.
- New clips: file into `clips/` as `NNN - Title [ytid].mp4`, add a descriptor to
  `data/descriptors-animals.json`, run `engine/build_catalog.py`, then verify the
  chromakey via `engine.cutouts.extract_sprite`.
- Append the YouTube id to `clips/archive.txt` so yt-dlp re-download runs skip it.
