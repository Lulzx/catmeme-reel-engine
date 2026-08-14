# 17 — Growth research and next-batch decisions (2026-08-14)

This document records the evidence used to author the batch after the channel ran
out of scheduled uploads. It is a decision log, not a claim that correlation proves
causation. Very recent Shorts can still be inside YouTube's discovery test, and the
six-beat cohort is small.

## Inputs and method

- Refreshed the channel snapshot with `python3 -m engine.insights --no-comments`
  on 2026-08-14, then fetched the 40 available comment threads separately.
- Joined every live video's statistics to its story JSON and measured beat count,
  caption length, quoted-dialogue share, cast slots, multi-character beats, implied
  duration and POV length.
- Used `views/day` rather than raw views. For a less freshness-biased comparison,
  the script-feature comparison only included videos live for 10–40 days.
- Queried YouTube's Data API for four relevant searches, grouped results by channel,
  pulled channel statistics and the latest 50 uploads, and sampled seven public
  videos as contact sheets. The downloaded samples remain under `work/competitors/`
  for internal visual analysis only and are not publishing assets.
- Searched YouTube for short green-screen cat templates, downloaded eight candidates
  to `work/candidate-clips/`, and reviewed one frame per second before accepting any.

## Our channel: refreshed baseline

At collection time: **179 live reels, 159,192 views, 40 comments, 889 average
views/reel**.

The newest discovery cohort was led by:

| reel | views/day | like rate |
|---|---:|---:|
| i-gave-the-update | 379 | 3.59% |
| written-in-pen | 373 | 2.32% |
| i-was-also-there | 330 | 3.79% |
| hiccups-slide-twelve | 323 | **10.16%** |
| alarm-three-seats-down | 285 | 1.15% |
| second-cursor-in-the-doc | 245 | 3.70% |
| i-took-the-call-from-the-stairs | 239 | 5.37% |
| replied-with-a-question-mark | 237 | 3.92% |
| the-third-drawer | 227 | 5.09% |
| sorry-rishaba | 220 | 5.64% |

These are too fresh to rank as durable winners, but the group reinforces three
lanes: office/digital misunderstandings, family friction, and tiny physical failures
with a witness.

### Script-feature comparison

For videos live 10–40 days, the top and bottom 20 by views/day differed more in text
density than in beat count:

| feature | top 20 | bottom 20 |
|---|---:|---:|
| mean views/day | 78.45 | 16.54 |
| mean caption length | **28.33 chars** | **38.06 chars** |
| mean POV length | 53.95 chars | 63.30 chars |
| mean beats | 7.65 | 7.80 |
| mean implied duration | 34.90s | 36.45s |

Beat-count cohorts in the same window:

| beats | n | median views/day | mean like rate |
|---:|---:|---:|---:|
| 6 | 4 | **63.8** | **6.47%** |
| 7 | 33 | 30.4 | 3.44% |
| 8 | 63 | 29.5 | 3.99% |
| 9 | 10 | 48.1 | 4.53% |

The six-beat row is promising but only has four observations. The new batch treats
six beats and roughly 20–24 seconds as a test, not a permanent rule.

### Comment signal

- The two explicit AI-writing complaints remain on `fan-hot-air` and
  `final-day-schedule`; this keeps the human-voice gate in force.
- `second-cursor-in-the-doc` reached well but one viewer said the story was unclear.
  Reach alone is not enough; each new script must be understandable without inference.
- Comments on `auto-no-change`, `change-in-toffees`, `phone-showed-me-2016` and
  `stopped-the-second-i-reached` confirm that concrete, locally familiar situations
  invite riffs and “same” reactions.
- The user explicitly requested **no Indian personal names**. New scripts use roles
  such as `MOM`, `DAD`, `FRIEND`, `COWORKER`, and `SMALL CAT`. Local situations may
  still be used, but no Indian person name is introduced.

## Comparable channels

Statistics are a 2026-08-14 snapshot from the YouTube Data API.

| channel | subscribers | channel views | recent cadence | median recent Short |
|---|---:|---:|---:|---:|
| [Cat Memes Hub](https://www.youtube.com/channel/UCCGWAomYBjF297s9BcjNpHg) | 1.49M | 1.342B | 0.40/day | 41.5s |
| [El Catto Memes](https://www.youtube.com/channel/UCROIJWHma7Ma0_jwMuiF_pg) | 344K | 143.9M | 0.14/day | 52.5s |
| [OhCrayZ](https://www.youtube.com/channel/UC0URdxn-zazosQ0AnjAWi0Q) | 914K | 301.0M | **3.16/day** | **20.5s** |
| [CatMemeMadness](https://www.youtube.com/channel/UCCmYmmH_M-QoT-DfrGm6Azw) | 64.5K | 44.4M | 0.73/day | 28s |

Representative samples inspected:

- Cat Memes Hub: [mom is your teacher](https://www.youtube.com/watch?v=FzHaBe2HQyI)
  and [old crush after years](https://www.youtube.com/watch?v=j6OU70HNDio).
- El Catto Memes: [vacation with family](https://www.youtube.com/watch?v=5uLdlzaFdy0).
- OhCrayZ: [best places to sleep](https://www.youtube.com/watch?v=l6q5nh0tIoc)
  and [dad takes mom on a drive](https://www.youtube.com/watch?v=svtOdw3KD1s).
- CatMemeMadness: [blanket fortress](https://www.youtube.com/watch?v=ErXp2KdroFs)
  and [finally try to sleep](https://www.youtube.com/watch?v=XIrOPgMLwDg).

### What they consistently do

1. **One readable premise stays pinned at the top.** The viewer never has to remember
   the setup while the cats change.
2. **A visual change every 2–4 seconds.** Even when the background stays fixed, the
   cat, scale, pose, or number of characters changes.
3. **Family and friend roles beat anonymous solo observation.** Mom, dad, sibling,
   friend, partner and coworker create a person viewers can tag.
4. **The cutouts are intentionally crude and silly.** Tiny cats, oversized heads,
   sudden zoomed faces, and mismatched scale are features, not defects.
5. **Strong videos end on a visual turn.** A new character appears, the location
   changes, or the physical consequence is revealed. Text explains less than ours.
6. **They use repeatable series furniture.** Family trips, mom-vs-dad, “best places,”
   and recurring roles make a new premise feel familiar before it starts.
7. **There are two viable duration models.** Cat Memes Hub/El Catto build 40–60s
   mini-stories; OhCrayZ publishes several 11–34s units a day. Our current cadence and
   analytics make the shorter model the better experiment for this batch.

### What not to copy

- Do not reuse competitor scripts, watermarks, cutouts, or scene construction.
- Do not inherit their vague titles or grammatical errors merely because a video has
  views.
- Do not turn every concept into family/relationship content. Our own channel has a
  stronger demonstrated edge in concrete office, phone, weather and household friction.
- Do not add more words to imitate a 60-second competitor. Our own winners are shorter
  at the caption level.

## New silly clip pack

Eight internet candidates were downloaded and inspected. Six were accepted and added
to `data/descriptors-animals.json`, `data/catalog.json`, and `clips/archive.txt`:

| id | role | source |
|---:|---|---|
| 186 | tiny silly dance / absurd victory | [Sep--LlwvY8](https://www.youtube.com/watch?v=Sep--LlwvY8) |
| 187 | tiny boxing kitten / mock determination | [Y7WqiO-PNZA](https://www.youtube.com/watch?v=Y7WqiO-PNZA) |
| 188 | jumping cat / airborne overreaction | [y-FIqLUvtaE](https://www.youtube.com/watch?v=y-FIqLUvtaE) |
| 189 | karate cat / physical retaliation | [WxSsapieO_U](https://www.youtube.com/watch?v=WxSsapieO_U) |
| 190 | drinking then laughing / smug toast | [Qs888m0I1ro](https://www.youtube.com/watch?v=Qs888m0I1ro) |
| 191 | close-up laugh / sudden reaction | [lKaeUsIQRPQ](https://www.youtube.com/watch?v=lKaeUsIQRPQ) |

Rejected:

- `5tyAwI2THOU`: visible CapCut watermark.
- `wgl1BXVm_CI`: visible Footage Zone watermark.

All accepted clips are short, have clean green backgrounds, and were cataloged with a
specific physical role rather than generic `happy`/`funny` tags.

Rights note: source inspection did not expose a Creative Commons license for any of
the six accepted YouTube clips (`yt-dlp` reported no license metadata). Public
availability is not reuse permission. The files and renders are therefore editorial
candidates, not proof of publication rights; obtain creator permission or replace
them with owned/licensed equivalents before publishing any Short that uses them.

## Thumbnail decision

YouTube currently says that creators **cannot upload a custom thumbnail for a Short
as they can for long-form video**. A creator can select a frame during the mobile
Shorts upload flow, and that choice cannot be changed after upload. See
[YouTube Help: Add custom thumbnails](https://support.google.com/youtube/answer/72431?hl=en).
The general Data API has a [`thumbnails.set`](https://developers.google.com/youtube/v3/docs/thumbnails/set)
endpoint, but the Shorts product restriction still applies.

Therefore this repo does not pretend that an API-uploaded poster is attached to a
Short. The batch instead:

- puts a visually silly, high-contrast clip on the payoff beat;
- records that clip as `thumbnail_clip` in the story JSON;
- generates a 9:16 poster candidate from that beat after render for the local gallery
  and for manual/mobile uploads where frame selection is available.

## Batch strategy

- 12 new reels; mostly six beats, one seven-beat exception.
- Beat duration around 3.2 seconds; target runtime roughly 22–27 seconds including
  the end card.
- Captions kept near the 28-character winner average, with plain timestamp/setup beats.
- Every story contains clips 182 and 183 as speaking recurring characters, but neither
  is pasted into the payoff.
- Every payoff is physical, a callback, or a reversal. None ends with generic defeat.
- No Indian names. Roles only.
- New silly clips are deliberately spread; `engine.allocate --fix` globally assigns
  the remaining cast and `--check` verifies the batch.

## Editorial scoring

All scripts passed `engine.lint_voice` with zero errors. Scores use
`.claude/skills/make-reel/SCORING.md`; 75 is required, with separate hard gates for
hook, punchline and human voice.

| slug | hook | punch | surprise | voice | spec | pace | share | cast | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| one-minute-voice-note | 13 | 16 | 8 | 14 | 10 | 9 | 8 | 6 | 84 |
| doorbell-with-shampoo | 14 | 17 | 9 | 14 | 9 | 9 | 8 | 6 | 86 |
| fan-speed-two-and-half | 14 | 17 | 9 | 14 | 8 | 9 | 8 | 6 | 85 |
| wrong-lunchbox-lid | 13 | 15 | 8 | 14 | 10 | 9 | 8 | 6 | 83 |
| bluetooth-living-room | 14 | 17 | 10 | 14 | 8 | 9 | 9 | 6 | 87 |
| tea-reheated-four-times | 13 | 16 | 8 | 14 | 11 | 9 | 7 | 6 | 84 |
| sock-on-my-back | 15 | 18 | 9 | 14 | 10 | 9 | 9 | 6 | 90 |
| grocery-bag-at-the-door | 14 | 17 | 9 | 14 | 10 | 9 | 8 | 6 | 87 |
| not-my-water-bottle | 14 | 18 | 10 | 14 | 8 | 9 | 7 | 6 | 86 |
| wet-office-chair | 14 | 16 | 8 | 14 | 9 | 9 | 8 | 6 | 84 |
| front-camera-family-call | 14 | 17 | 9 | 14 | 8 | 9 | 9 | 6 | 86 |
| ketchup-at-my-shirt | 15 | 18 | 9 | 14 | 8 | 9 | 9 | 6 | 88 |

Every script clears 75 and every hard gate. No script was silently dropped.

## Verification commands

```bash
python3 -m engine.lint_voice --batch $(cat work/next_batch_slugs.txt)
python3 -m engine.allocate --check $(cat work/next_batch_slugs.txt)
python3 engine/render.py data/stories/<slug>.json
ffprobe -v error -show_entries format=duration -of csv=p=0 output/<slug>.mp4
ffmpeg -nostdin -i output/<slug>.mp4 -af volumedetect -f null -
```

The analytics snapshot is `work/insights.json`; competitor and candidate contact
sheets are under `work/competitors/contact-sheets/` and
`work/candidate-clips/contact-sheets/`.

## Completed production and QA

All 12 stories were rendered and registered as `queued` in the local posting
catalog. Nothing was uploaded to YouTube and no publish time was assigned.

- Output: `output/<slug>.mp4`, 1080×1920 H.264 video with AAC audio.
- Runtime: 11 videos are 22.22 seconds; `doorbell-with-shampoo` is 25.44 seconds.
- Audio: every file is non-silent; measured mean volume ranges from -19.8 dB to
  -17.6 dB.
- Posters: `work/posters/<slug>.mp4.jpg`, generated from each story's explicitly
  selected silly payoff clip rather than from a generic opening frame.
- Visual QA: the 12 poster candidates were reviewed together in
  `work/qa/next-batch-posters.jpg`; captions and POV lines remain readable and the
  selected frames carry a clear physical joke or exaggerated cat reaction.
- Casting: 73 narrative cast slots use 51 distinct clips. Clips 182 and 183 remain
  the recurring speakers, while the visual payoff clips rotate.
- Editorial: voice lint reports zero errors; all rubric scores are 83–90.

Before publishing approval, the local queue snapshot was exported to
`data/videos.json` and `youtube.md` as a production-ready handoff. The later upload
and scheduling action is recorded below.

## YouTube schedule applied

After review, the user authorized upload and specified the channel's established
six-hour publishing cadence. All 12 files were uploaded privately and placed on the
next available `:37 UTC` grid points:

| publishes (IST) | slug | YouTube |
|---|---|---|
| Aug 15, 02:07 | one-minute-voice-note | [35vYQjC8D7o](https://youtu.be/35vYQjC8D7o) |
| Aug 15, 08:07 | doorbell-with-shampoo | [d7oo8cptlBw](https://youtu.be/d7oo8cptlBw) |
| Aug 15, 14:07 | fan-speed-two-and-half | [Wk8XxHpdr9w](https://youtu.be/Wk8XxHpdr9w) |
| Aug 15, 20:07 | wrong-lunchbox-lid | [id-Ck_9ZWE8](https://youtu.be/id-Ck_9ZWE8) |
| Aug 16, 02:07 | bluetooth-living-room | [ej8eLq-fhnY](https://youtu.be/ej8eLq-fhnY) |
| Aug 16, 08:07 | tea-reheated-four-times | [e8itqFjj4Ds](https://youtu.be/e8itqFjj4Ds) |
| Aug 16, 14:07 | sock-on-my-back | [en0qsfN4Oj8](https://youtu.be/en0qsfN4Oj8) |
| Aug 16, 20:07 | grocery-bag-at-the-door | [CqM3Z_l5Sbo](https://youtu.be/CqM3Z_l5Sbo) |
| Aug 17, 02:07 | not-my-water-bottle | [e36RI0VFkIw](https://youtu.be/e36RI0VFkIw) |
| Aug 17, 08:07 | wet-office-chair | [JuIgBYqky4s](https://youtu.be/JuIgBYqky4s) |
| Aug 17, 14:07 | front-camera-family-call | [VmVA7tnebF8](https://youtu.be/VmVA7tnebF8) |
| Aug 17, 20:07 | ketchup-at-my-shirt | [6Mk1ZicS4QE](https://youtu.be/6Mk1ZicS4QE) |

A post-write remote audit queried YouTube for all 12 IDs and confirmed that every
video is private, every ID is unique, and every remote `publishAt` value matches the
local database. The tracked schedule views were then regenerated in
`data/videos.json` and `youtube.md`.

## Repository persistence note

The commit tracks story JSON, source URLs and descriptors, catalog entries,
analytics/decision logs, schedule snapshots, and poster/allocation code. By the
repository's existing policy, `clips/`, `output/`, `work/`, `data/videos.db`, OAuth
credentials, rendered MP4s, downloaded clip binaries, poster JPGs, and contact
sheets are gitignored and remain on the authoring machine. A deployment that needs
the six new clip binaries must use the project's separate media-sync mechanism;
their IDs and original source URLs are preserved above.
