# 16 — Clip diversity: not letting one cat carry the channel

*(Added 2026-07-30, after a usage audit of the first 126 videos.)*

## The problem

`clip_usage` over the first 126 reels:

| clip | videos | primary |
|---|---|---|
| 032 | 92 | cute happy dance |
| 008 | 40 | sad pleading |
| 058 | 38 | unimpressed puppet |
| 023 | 34 | intense stare |
| 016 | 30 | patient waiting |

One clip in 92 of 126 videos. With 179 clips in the catalog that isn't curation,
it's a bug, and it's visible in the feed: scroll three of our Shorts and the same
dancing cat is in all three.

Two causes, both in the matcher:

1. **The penalty was flat.** `match.match(penalize=…)` subtracted a constant
   −1.5 from any clip another video had used. The 1st repeat and the 91st cost
   the same, so once a clip was a broad match for a common emotion family
   ("cute", "happy", "dancing") nothing ever stopped it winning again.
2. **The matcher is greedy and per-beat.** It resolves beat 1 with no knowledge
   of beat 7. A beat with five equally good options can take the one clip a later
   beat has no substitute for, and there is no way to give it back.

## Fix 1 — fatigue instead of a flat penalty (`engine/match.py`)

`penalize` now accepts a mapping `clip_id -> how many videos already used it`,
and the cost grows with exposure:

```python
sc += penalty * math.log2(1 + uses)      # penalty defaults to -1.5
```

One prior use still costs −1.5 (unchanged behaviour), ten cost −5.2, ninety cost
−9.8. `engine/render.py` seeds this from the `clip_usage` table
(`_channel_usage()`), so a one-off render knows the channel's real history rather
than pretending it's the first video ever made. Passing a plain set still works.

## Fix 2 — batch allocation (`engine/allocate.py`)

Fatigue fixes the weighting but not the greediness. The allocator solves the
whole batch at once:

```bash
python3 -m engine.allocate --check slug ...   # report repeats / over-exposure
python3 -m engine.allocate --fix   slug ...   # write the clip pins back
python3 -m engine.allocate --report           # channel-wide usage table
```

1. **Slots.** Every cast member with `want`/`query` and no deliberate `clip` pin.
   Pins (mascots, recurring characters) are left alone unless `--repin-all`.
2. **Candidates + relevance floor.** Score every clip with `match.score`, keep
   only those at `max(FLOOR, best_fit - MAX_DROP)`. **This is what keeps the meme
   in context.** Diversity can only choose *among clips that genuinely fit the
   beat*; it can never push a beat onto an unrelated cat to avoid a repeat.
3. **Fatigue.** `value = fit − 0.9·log2(1 + prior_uses) + favourite_bonus`.
4. **Caps.** Each clip becomes `cap` assignable columns (default 1 per batch), so
   it can be used at most that many times. Clips in `data/favorites.json` are
   mascots and are exempt — those are *supposed* to recur.
5. **Global optimum.** Rectangular min-cost assignment
   (`scipy.optimize.linear_sum_assignment`) over slots × clip-columns. This is
   the part greedy can't do: it maximises total fit across the whole batch, so a
   contested clip lands on the beat with no equally good alternative.

**Forced repeats.** When the floored candidate set runs out, the slot reuses a
clip another *video* already has and is printed as `FORCED REPEAT` rather than
being silently pushed onto a bad match. Repeating across videos is fine; the same
cat twice inside **one** video is never allowed (it would play two characters),
so that fallback widens past the floor instead of duplicating.

## The mascots are the deliberate exception

`data/favorites.json` is the opposite lever: clips that *should* recur.

| id | clip | role |
|----|------|------|
| 182 | Yapapa cat | the one who won't stop talking |
| 183 | German cat | the small guy with the unhelpful tip |
| 184 | Muhehehe villain cat | DEREK |
| 185 | OIIA spinning cat | brain short-circuit / outro card |
| 041 | Laughing cat | mocking |

Since 2026-08 every reel in a batch casts **182 and 183** by name. They're pinned
in the story JSON, so the allocator treats them as spoken-for and works around
them.

## Ordinary usage check before shipping a batch

```bash
python3 -m engine.allocate --report                       # who's over-exposed
python3 -m engine.allocate --check <the batch's slugs>    # repeats in this batch
```

## Watch the *punchline* beats specifically

The allocator can only spread clips as far as the `want` tags let it. The failure
mode is subtle and it comes from the writing, not the solver: if you reach for the
same tag block on every payoff beat — `deadpan, blank, staring, done, flat` is the
tempting one — every reel's last beat competes for the same handful of clips and
the allocator reports `FORCED REPEAT` because there is nothing else to give.

On the 2026-08-03 batch that put clip **051 (deadpan stare) in 19 of 27 reels**,
all on the payoff beat, so the moment that carries each reel looked identical
across a week of the feed. Retagging each ending to its own register (stunned /
judging / grumpy / dead-inside / humiliated / exhausted, all of which exist in the
catalog) moved the batch from 99 distinct clips with a worst repeat of 19 to **113
distinct with a worst repeat of 5** — same allocator, better inputs.

Two practical notes:

- **Check the tag vocabulary exists before using it.** The catalog has 623 emotion
  tags but plenty of plausible words (`weary`, `dread`, `pained`, `frustrated`,
  `bitter`) are **not** among them, and an unmatched tag silently degrades to a
  poor pick rather than erroring. Grep `emotions` in `data/catalog.json` first.
- **`--repin-all` reassigns mascot pins too.** Plain `--fix` leaves anything
  already pinned alone, which is what you normally want; `--repin-all` will move
  182/183 off their lines. If you do use it, re-pin the mascots afterwards.
