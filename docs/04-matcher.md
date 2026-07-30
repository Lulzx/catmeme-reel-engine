# 4. The matcher — emotion → clip

`engine/match.py`. Turns a beat's desired emotion (in words) into the best clip from
the catalog. **Deterministic, explainable, and needs no model call at match time** —
because the describing already happened in the catalog.

## Interface

```python
import match as M
catalog = M.load_catalog()
score, clip, matched = M.best(["smug","confident","rizz"], query="", catalog=catalog,
                              exclude=already_used_ids, orientation=None)
# best() returns the single top (score, clip, matched_terms)
# match() returns the full ranked list of (score, clip, matched_terms)
```

CLI for quick checks:

```bash
python3 engine/match.py screaming rage outburst
#   9.6  [012] rage scream            matched=['screaming', 'rage', 'outburst']
#   3.6  [027] furious glare          matched=['rage']
#   ...
```

## Scoring

For each candidate clip, every desired word in `want` contributes:

| condition | points |
|-----------|--------|
| word **is** one of the clip's `emotions` tags (exact) | **+3.0** |
| a token of the word hits a tag | +2.0 |
| tag contains / is contained by the word (fuzzy) | +1.3 |
| a token appears anywhere in `primary`/`use_for`/`action`/`title` | +1.0 |

Plus the free-text `query` (tokens: +1.0 if a tag, +0.4 if anywhere in the haystack),
plus the `quality` bonus (see [03-catalog.md](03-catalog.md)), minus 0.5 if an
`orientation` filter is requested and the clip doesn't match.

The list is sorted descending; `best()` takes the top. Because exact-tag hits dominate
(+3 each), a well-chosen `want` list lands on the obviously-right clip with a big score
gap — e.g. `["smug","confident","rizz"]` → clip 020 at 12.6 vs. 0.6 for everything else.

## `exclude` / avoiding repeats

`render.py` passes the set of clip ids already used in the video as `exclude`, so the
same cat isn't reused across beats (and not even twice within a single multi-cat
scene). With ~30 usable clips and typically <15 cast slots per story, this rarely
forces a bad pick. To deliberately allow reuse, pin the clip by id instead
(`"clip": "020"`).

## `penalize` — cross-video fatigue

`exclude` is a hard ban within one video. Across videos the lever is `penalize`,
a mapping `clip_id -> how many videos already used it`; each candidate takes
`penalty * log2(1 + uses)` (default `penalty = -1.5`). A plain set still works and
is read as one use each.

The log matters. This used to be a flat -1.5 no matter how exposed a clip was,
which is how clip 032 ended up in 92 of the first 126 videos. Now one prior use
costs 1.5, ten cost 5.2, ninety cost 9.8 — enough to lose to a fresh clip with a
weaker tag match, but not enough to beat a genuinely exact match.

`render.py` seeds this from the `clip_usage` table (`_channel_usage()`), so even a
single render is scored against the channel's real history. Clips listed in
`data/favorites.json` get a positive bonus that offsets the penalty, which is how
the recurring mascots keep winning. Batch-level allocation (the part per-beat
greedy scoring can't do) lives in `engine/allocate.py` —
see [16-clip-diversity.md](16-clip-diversity.md).

## Design notes / how to extend

- **Tags are the lever.** If a beat keeps mis-matching, the fix is almost always to
  add a tag to the clip's `emotions` in `build_catalog.py` (then rebuild), not to
  change the scoring weights.
- The scoring is intentionally simple (overlap + small fuzz) so results are
  predictable. A future upgrade could swap in embedding similarity, but that trades
  explainability for marginal recall and was not needed.
- `best()` returning the `matched` term list is used for the render log, so you can
  see *why* each clip was chosen.
