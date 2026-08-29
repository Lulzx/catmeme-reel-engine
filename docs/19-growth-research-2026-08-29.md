# 19 — The reach ceiling, and the September batch (2026-08-29)

The scheduled queue ran out on 2026-08-28. This document records what the
channel's numbers actually say, why the previous framing ("which lanes win?")
was answering the wrong question, and how the next batch is built to test it.

## Snapshot

`python3 -m engine.insights --no-comments`, pulled 2026-08-29T04:09Z:

**235 live reels · 230,356 views · 7,249 likes · 60 comments.**

Before any of this was read, the DB had to be reconciled: **110 rows still said
`scheduled` for videos that had been public for weeks**. This is the same drift
doc 14 warned about, and it recurs after every `--fill-schedule` run because
nothing tells us when YouTube auto-publishes. Statuses were rewritten from the
snapshot's `privacy`/`published`, then `python3 -m engine.upload --sync`.
Backup at `data/videos.db.presync.bak`.

## The finding: there is no variance

| percentile | views |
|---|---:|
| p10 | 584 |
| p25 | 714 |
| **p50** | **913** |
| p75 | 1,132 |
| p90 | 1,446 |
| p99 | 2,631 |
| max | 2,929 |

**max ÷ median = 3.2x.** A growing Shorts channel is carried by 20–100x
outliers. This channel has never produced one. Every reel lands in a band
roughly 600–1,500 wide and stops.

Second half of the same finding — **views saturate by day 7**:

| age | n | median views |
|---|---:|---:|
| 0–3d | 10 | 1,108 |
| 3–7d | 16 | 1,116 |
| 7–14d | 28 | 1,101 |
| 14–21d | 20 | 743 |
| 21–35d | 53 | 784 |
| 35–50d | 54 | 738 |
| 50–70d | 54 | 1,072 |

A reel is finished after its first week. Nothing re-enters distribution.

Put together: **total channel views ≈ posts/day × ~1,000.** That is linear by
construction, which is exactly the flattening the log-scale audience graph shows.
Cadence is already at the account's practical ceiling (~38 uploads/day cap, doc
02), so more volume cannot fix it. The channel does not have a topic problem.
It has a problem where nothing ever escapes the initial test audience.

### Why views/day is misleading here

Ranking by `views/day` — what docs 14 and 17 used — makes the newest cohort look
like it is winning by 5-10x:

| publish week | n | median views/day | median views | median age |
|---|---:|---:|---:|---:|
| 2026-06-22 | 9 | 20.9 | 1,319 | 62.3d |
| 2026-07-20 | 26 | 19.5 | 712 | 37.0d |
| 2026-08-17 | 28 | 145.4 | 1,098 | 8.7d |
| 2026-08-24 | 19 | 507.5 | 1,132 | 2.8d |

Because views arrive almost entirely in week one, `views/day` is mostly
`1 / age`. The **median views** column is the honest one, and it is flat across
every cohort. Recent scripts are better written, but they are not reaching
materially more people. Use views/day only inside a narrow age band.

## What the length evidence does and does not support

Real rendered durations (not implied beat counts) against views:

| duration | n | median views | p90 |
|---|---:|---:|---:|
| 0–24s | 55 | **1,106** | **1,841** |
| 24–30s | 8 | 784 | 1,285 |
| 30–36s | 48 | 868 | 1,217 |
| 36–42s | 108 | 840 | 1,354 |
| 42s+ | 16 | 765 | 821 |

Seven of the top ten reels are 22–25s. Mean caption length also separates the
top and bottom 35 by views in the 7–45 day window (25.1 vs 34.1 chars).

**The honest caveat:** the six-beat/22s switch happened on 2026-08-17, so short
reels are also the newest reels. Inside narrow age bands where both shapes exist
the gap shrinks to 797 vs 775 (16–25d) and 917 vs 726 (25–35d) — same direction,
much weaker, small n. Short is the best-supported lever available, not a
demonstrated cause. The no-outlier finding above is the one that is not
confounded.

## Comment signal

60 comments across 235 reels — thin, and itself a symptom. What is there:

- The audience is South Asian and responds to local specifics: *"Plot twist: You
  pay with Gpay"*, *"Mere ko 5 de na"*, the toffees-as-change reel.
- **The AI-script complaints have stopped.** Nothing since `fan-hot-air` and
  `final-day-schedule`. The doc 15 gate is working and stays in force.
- The recurring cast is landing by name: *"The small cat came in clutch"*,
  *"I go meow was epic"*, *"Darek the goat?"*.
- Two viewers asked *"who is ajay"* on separate reels. Personal names cost
  comprehension and buy nothing. Roles only.

## The September batch — a portfolio, not a format

If every reel is the same shape, every reel gets the same result. The batch is
deliberately split so something has room to break out.

**27 new stories, plus the 29 already rendered, scheduled 4/day on the existing
six-hour grid from 2026-08-30.**

| lane | n | what it tests |
|---|---:|---|
| proven | 10 | the 22s / six-beat shape, unchanged control group |
| DEREK series | 4 | does a named recurring villain bring viewers back |
| hard-local | 4 | auto meter, 4am water, power cut, landlord — no names, roles only |
| question ending | 4 | last beat asks the viewer a real question, to lift comments |
| ultra-short | 5 | `max_beat_dur: 3.0`, four beats, ~14.6s |

The ultra-shorts are the sharpest test: at 4.5s/beat a four-beat reel still runs
20.6s, which is not meaningfully different from the 22s control, so
`max_beat_dur` was dropped to 3.0 to make the format actually distinct.

### `max_beat_dur` is what actually sets the format, not the beat count

The first render pass produced **29.6s** reels from six beats, because
`engine/author.py`'s scaffold default is `max_beat_dur: 4.5`. The Aug 17+ batch that
produced seven of the current top ten uses **3.4**, which is what makes a six-beat
reel land at ~22s. Beat count alone does not control duration.

All 22 six-beat stories were re-rendered at `3.4` (23.0s). The five ultra-shorts use
`3.0` (14.6s). **Check the rendered duration with `ffprobe`, not the beat count**, before
queueing a batch — otherwise a batch written to the short format silently ships in the
36–42s bucket, which is the worst-performing one in the table above.

### Editorial gates

All 27 cleared `engine.lint_voice` with **zero errors** and were scored against
`.claude/skills/make-reel/SCORING.md`. Five were rewritten before rendering:

- `one-ear-at-a-time` — closer was a shrug ("i listened to the whole song like
  that"), replaced with a reversal ("the song ended. the next one played in both").
- `the-third-switch`, `the-drawer-with-the-key`, `still-on-page-four` — the
  question ending was carrying the punchline on its own. Beat 4 now lands a real
  turn so the question is a bonus rather than the joke.
- `socket-is-under-the-bed` — outro restated beat 2.

### A casting bug worth remembering

The first allocation pass put clip **176 on the closing beat of 11 of 27 reels**.
Cause: the same `want` set (`speechless / blank / stunned / what / vacant`) had
been written for nearly every punchline, so the allocator's candidate pool was
identical every time. The fix was at the authoring end — give each closer its own
reaction register (grief, rage, humiliation, disgust, side-eye, dead-inside) —
which dropped 176 to 2 uses and forced repeats from 11 to 6.

**The allocator can only diversify across the candidates the writing allows.**
Varied captions with identical emotion tags will still produce a visually
identical batch. Check `--check` output for a clip stacking on the same beat
index before rendering.

## What to measure on the next pass

The batch is a bet on variance, so judge it on the tail, not the average:

1. **Does anything clear 5,000 views?** That is the only number that changes the
   growth curve. A batch median of 1,000 with no outlier is a failed batch even
   if every reel is well made.
2. **Comments per reel on the four question endings** vs the batch median (which
   is currently ~0.25).
3. **Do the four DEREK reels outperform their neighbours**, and does reel 4 beat
   reel 1 — that is returning-viewer signal, not just a good premise.
4. **Ultra-short vs the 22s control at matched age.** This is the first time both
   shapes exist in the same cohort, so it is the first unconfounded read on length.
