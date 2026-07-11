# 14 — Performance analytics & trendy clip curation

*(Snapshot: 2026-07-11. Numbers move daily — re-pull `/api/analytics` before acting on them.)*

## Reading channel performance via the API

The deployed UI (cats.lulzx.space, basic auth) exposes two endpoints that together
give a full performance picture — no YouTube Studio needed:

- **`GET /api/schedule`** — the posting log from `data/videos.json`: slug, title,
  publish time, status, video_id, dominant background place.
- **`GET /api/analytics`** — live per-video `viewCount/likeCount/commentCount/privacy`
  for every uploaded video, batched 50 ids/call through the Data API
  (needs the `youtube.readonly` scope; re-auth with `python3 -m engine.upload --auth`).

Join the two on `video_id` and normalize by days-live — raw view totals favor older
posts, so **views/day** is the fair ranking for a young channel where every video
is still in its discovery window.

## Findings (first 54 reels, Jun 27 – Jul 10, 2026)

~56k total views, ~1,036 avg/reel, ~4 posts/day cadence, everything public.

**Three themes clearly outperform:**

1. **Social embarrassment with a witness** — card-declined (1,657), group-chat-joke-ignored
   (1,444 + best-in-class 3.3% like rate), outfit-matches-decor, neighbors-kid (1,659).
   The formula: a small humiliation happens *in front of someone*.
2. **Phone/internet life** — storage-almost-full (851 views on **day one**, best launch yet),
   just-one-video, research-rabbit-hole (5.3% like rate — top engagement on the channel),
   google-then-instagram.
3. **Work/office absurdity** — meeting-email (1,673, all-time #1), reply-all, zoom-camera-on.
   Never flops.

**What underperforms:** mundane solo observations with no social sting — package-truck
(412, worst), liked-old-photo, movie-trailers, missed-the-bus. The two husband-curfew
saga reels landed mid-to-low. Restaurant is the most-used setting (7 reels) but a
below-average performer — rotate away from it.

**Like-rate leaders** (engagement ≠ reach): research-rabbit-hole 5.3%,
boyfriend-losing-argument / tiny-detail 3.6%, outfit-matches-decor /
perfect-song-short-drive 3.5%.

## Trendy meme clips (favored in the matcher)

The user wants recognizable, currently-trendy meme cats appearing often. Boosts live
in `data/favorites.json` (see doc 04 — bonus offsets the −1.5 cross-video diversity
penalty in `engine/match.py`):

| id | clip | boost | source | beats it wins |
|----|------|-------|--------|---------------|
| 182 | Yapapa cat (mascot) | 1.6 | Zjso08bj1tg | yapping, narrating, vibing |
| 041 | Laughing cat | 1.2 | aCllAI2m6BI | mocking, bursting out laughing |
| 183 | German Cat | 1.2 | cd2c3-qlYy8 | tiny smug interjection |
| 184 | Muhehehe villain-laugh cat *(added 2026-07)* | 1.2 | gk2s1IoyN38 | gloating, evil-plan payoff |
| 185 | OIIA spinning cat *(added 2026-07)* | 1.2 | v2yUIWx6jY8 | brain short-circuit, spiraling, chaos |

A July 2026 web-trend check also surfaced Dark Cat in the Hat (dominant on TikTok but
copyrighted film footage + grim tone — rejected), Drooling Cat and Folk Valley Cat
(image-based, declined), Chipi Chipi Chapa Chapa and Longing Cat (declined for now).

## Sourcing gotchas (learned adding #184/#185)

- **Inspect frames before cataloging.** The top YouTube hit for "OIIA cat green screen"
  was actually a suggestive anime-catgirl overlay with a watermark. Tile a frame strip
  (`ffmpeg select= … tile=`) and *look* at it first.
- **Check for repeated-template loops** with `silencedetect` (the yapapa method, doc 09):
  #184 turned out to be three genuine distinct laugh bursts, not a loop — kept whole,
  with a descriptor note to trim one ~2.5s burst per beat.
- New clips: file into `clips/` as `NNN - Title [ytid].mp4`, add a descriptor object to
  `data/descriptors-animals.json` (fields + `tax` from the 25-word taxonomy), run
  `engine/build_catalog.py` (computes key color + bbox), then verify the chromakey by
  extracting a sprite via `engine.cutouts.extract_sprite`.
- Append the YouTube id to `clips/archive.txt` so yt-dlp re-download runs skip it
  (note: that file is gitignored with the rest of `clips/`).
