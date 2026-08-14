#!/usr/bin/env python3
"""Batch-level meme allocator — stop the same cat carrying every video.

    python3 -m engine.allocate --check  slug [slug ...]     # report repeats
    python3 -m engine.allocate --fix    slug [slug ...]     # rewrite the pins
    python3 -m engine.allocate --report                     # channel-wide usage

## Why the per-beat matcher isn't enough

`engine/match.py` scores one beat at a time and applies a *flat* -1.5 penalty to
any clip another video already used. Two things go wrong with that:

* the penalty doesn't grow with use, so a clip that is a broad match for many
  emotions keeps winning. #032 ("cute happy dance") ended up in 92 videos;
* it's greedy. A beat that has five good options can grab the one clip a later
  beat desperately needs, and the matcher can never take it back.

## The algorithm

1. **Slots.** Every cast member in the batch that isn't a deliberate pin
   (mascots, recurring characters) is an open slot.
2. **Candidates + relevance floor.** Score every catalog clip against the slot's
   `want`/`query` with `match.score`. Keep only clips scoring at least
   `max(FLOOR, best_fit - MAX_DROP)`. **This is the constraint that keeps the
   meme in context** — diversity is never allowed to drop a slot onto a clip that
   doesn't fit the beat, it can only choose among clips that genuinely fit.
3. **Fatigue.** `value = fit - FATIGUE * log2(1 + prior_uses) + favour_bonus`,
   where `prior_uses` comes from the `clip_usage` table (every video posted so
   far). Unlike a flat penalty this keeps biting as a clip gets over-exposed:
   one prior use costs 0.9, ten cost 3.1, ninety cost 5.9.
4. **Caps.** Each clip is expanded into `cap` assignable columns, so it can be
   picked at most `cap` times in the batch (default 1). Clips in
   `data/favorites.json` are mascots and get `mascot_cap` columns instead — the
   user *wants* those recurring.
5. **Global optimum.** Rectangular min-cost assignment (Hungarian,
   `scipy.optimize.linear_sum_assignment`) over slots x clip-columns. This is
   what greedy can't do: it maximises total fit across the whole batch at once,
   so a contested clip lands on the beat that has no equally good alternative.

Slots whose candidate set is exhausted keep their best-fit clip and are reported
as forced repeats rather than being silently pushed onto a bad match.
"""
import argparse
import json
import math
import os
import sqlite3
import sys
from collections import Counter

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import match as M                                    # noqa: E402
from engine.paths import DATA, STORIES               # noqa: E402

DB = os.path.join(DATA, "videos.db")

FLOOR = 2.0        # absolute minimum fit — below this the clip isn't about the beat
MAX_DROP = 3.0     # how much fit a slot may trade away for freshness
FATIGUE = 0.9      # weight of log2(1 + prior_uses)
CAP = 1            # times one clip may appear across the batch
MASCOT_CAP = 99    # favourites are exempt — they're meant to recur


# ── inputs ──────────────────────────────────────────────────────────────────
def prior_uses(exclude_slugs=None):
    """clip_id -> uses outside the batch currently being inspected.

    Registered queued stories already have ``clip_usage`` rows. Excluding their
    slugs prevents a check from counting the same batch as both prior and current
    usage after registration.
    """
    if not os.path.exists(DB):
        return Counter()
    con = sqlite3.connect(DB)
    try:
        exclude_slugs = list(exclude_slugs or [])
        if exclude_slugs:
            marks = ",".join("?" for _ in exclude_slugs)
            sql = (f"select clip_id, count(*) from clip_usage "
                   f"where slug not in ({marks}) group by clip_id")
            return Counter(dict(con.execute(sql, exclude_slugs)))
        return Counter(dict(con.execute(
            "select clip_id, count(*) from clip_usage group by clip_id")))
    finally:
        con.close()


def load_stories(slugs):
    out = {}
    for s in slugs:
        p = os.path.join(STORIES, s.replace(".json", "") + ".json")
        with open(p) as f:
            out[s] = json.load(f)
    return out


def slots(stories, repin_all=False):
    """Open slots as (slug, beat_idx, cast_idx, member).

    A member with an explicit `clip` is a deliberate pin (a mascot, a recurring
    character) and is left alone unless --repin-all. A member with no `want` and
    no `query` can't be re-matched, so it's always left alone."""
    out = []
    for slug, s in stories.items():
        for bi, b in enumerate(s.get("beats", [])):
            for ci, m in enumerate(b.get("cast", [])):
                if m.get("clip") and not repin_all:
                    continue
                if not (m.get("want") or m.get("query")):
                    continue
                out.append((slug, bi, ci, m))
    return out


def pinned_counts(stories):
    """Clips already spoken for by explicit pins — they consume batch capacity.
    Returns (global counts, {slug: set of clips that story already holds})."""
    c = Counter()
    per = {}
    for slug, s in stories.items():
        for b in s.get("beats", []):
            for m in b.get("cast", []):
                if m.get("clip"):
                    c[m["clip"]] += 1
                    per.setdefault(slug, set()).add(m["clip"])
    return c, per


# ── the allocation ──────────────────────────────────────────────────────────
def allocate(open_slots, catalog, uses, taken, story_pins=None, cap=CAP,
             mascot_cap=MASCOT_CAP, floor=FLOOR, max_drop=MAX_DROP,
             fatigue=FATIGUE):
    """Return {(slug, bi, ci): (clip_id, fit, forced)}."""
    if not open_slots:
        return {}

    # 1-2. candidates per slot, filtered by the relevance floor
    cands, ranked_all = [], []
    for (_, _, _, m) in open_slots:
        scored = []
        for c in catalog:
            if c["id"] in M.BLOCKED:
                continue
            fit, _ = M.score(c, m.get("want", []), m.get("query", ""))
            scored.append((fit, c["id"]))
        scored.sort(reverse=True)
        best = scored[0][0] if scored else 0.0
        keep = [(f, cid) for f, cid in scored if f >= max(floor, best - max_drop)]
        cands.append(keep or scored[:1])
        ranked_all.append(scored)

    # 4. one column per allowed copy of each clip, minus what pins already spent
    columns, col_clip = [], []
    for cid in {cid for ks in cands for _, cid in ks}:
        limit = mascot_cap if cid in M.FAVORED else cap
        for _ in range(max(0, limit - taken.get(cid, 0))):
            col_clip.append(cid)
    if not col_clip:
        return {}
    col_of = {}
    for j, cid in enumerate(col_clip):
        col_of.setdefault(cid, []).append(j)

    # 3. value matrix (INF where the clip isn't a candidate for that slot)
    BIG = 1e6
    cost = np.full((len(open_slots), len(col_clip)), BIG)
    fits = {}
    for i, keep in enumerate(cands):
        for fit, cid in keep:
            value = (fit
                     - fatigue * math.log2(1 + uses.get(cid, 0))
                     + M.FAVORED.get(cid, 0.0))
            for j in col_of.get(cid, ()):
                cost[i, j] = -value
            fits[(i, cid)] = fit

    # 5. global min-cost assignment
    rows, cols = linear_sum_assignment(cost)
    out, unfilled = {}, []
    for i, j in zip(rows, cols):
        if cost[i, j] >= BIG:                       # no capacity left in-floor
            unfilled.append(i)
            continue
        slug, bi, ci, _ = open_slots[i]
        cid = col_clip[j]
        out[(slug, bi, ci)] = (cid, fits[(i, cid)], False)
    for i in set(range(len(open_slots))) - set(rows.tolist()):
        unfilled.append(i)

    # Forced repeats. Capacity inside the relevance floor ran out, so this slot
    # has to reuse a clip another video already has. Repeating across videos is
    # tolerable; repeating inside ONE video is not (the same cat would play two
    # characters), so the fallback skips anything that story already holds and
    # then prefers the least-exposed of what's left.
    in_story = {k: set(v) for k, v in (story_pins or {}).items()}
    for (slug, bi, ci), (cid, _, _) in out.items():
        in_story.setdefault(slug, set()).add(cid)
    for i in unfilled:
        slug, bi, ci, _ = open_slots[i]
        held = in_story.setdefault(slug, set())
        free = [(f, cid) for f, cid in cands[i] if cid not in held]
        if not free:
            # The floored candidate set is exhausted for this story. Reusing the
            # same cat twice inside one video is the one thing we never do (it
            # would play two characters), so widen past the floor rather than
            # duplicate, and take the best remaining fit.
            free = [(f, cid) for f, cid in ranked_all[i] if cid not in held][:1]
        fit, cid = max(free, key=lambda fc: fc[0] - fatigue * math.log2(1 + uses.get(fc[1], 0)))
        held.add(cid)
        out[(slug, bi, ci)] = (cid, fit, True)
    return out


# ── reporting ───────────────────────────────────────────────────────────────
def check(stories, uses, cap=CAP):
    """Repeats inside the batch + clips that are already over-exposed."""
    used = Counter()
    where = {}
    for slug, s in stories.items():
        for bi, b in enumerate(s.get("beats", [])):
            for m in b.get("cast", []):
                cid = m.get("clip")
                if not cid:
                    continue
                used[cid] += 1
                where.setdefault(cid, []).append(f"{slug}#{bi}")
    problems = []
    for cid, n in used.most_common():
        if cid in M.FAVORED:
            continue
        if n > cap:
            problems.append(f"repeat x{n}: [{cid}] {', '.join(where[cid])}")
    for cid, n in used.items():
        if cid not in M.FAVORED and uses.get(cid, 0) >= 15:
            problems.append(f"over-exposed: [{cid}] already in {uses[cid]} videos "
                            f"({', '.join(where[cid])})")
    return used, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--check", action="store_true", help="report only")
    ap.add_argument("--fix", action="store_true", help="write clip pins back")
    ap.add_argument("--report", action="store_true", help="channel-wide clip usage")
    ap.add_argument("--repin-all", action="store_true",
                    help="also reassign members that already have a pinned clip")
    ap.add_argument("--cap", type=int, default=CAP)
    ap.add_argument("--floor", type=float, default=FLOOR,
                    help="minimum semantic fit retained for allocation")
    ap.add_argument("--max-drop", type=float, default=MAX_DROP,
                    help="maximum fit traded for clip freshness")
    ap.add_argument("--fatigue", type=float, default=FATIGUE,
                    help="penalty weight for prior channel uses")
    a = ap.parse_args()

    uses = prior_uses(a.slugs)
    if a.report or not a.slugs:
        cat = {c["id"]: c for c in M.load_catalog()}
        print(f"{'clip':>5}  {'vids':>4}  primary")
        for cid, n in uses.most_common(30):
            tag = " (mascot)" if cid in M.FAVORED else ""
            print(f"{cid:>5}  {n:>4}  {cat.get(cid, {}).get('primary', '?')}{tag}")
        if not a.slugs:
            return

    stories = load_stories(a.slugs)
    used, problems = check(stories, uses, cap=a.cap)
    print(f"\n{len(stories)} stories · {sum(used.values())} cast slots · "
          f"{len(used)} distinct clips")
    for p in problems:
        print("  !", p)
    if not problems:
        print("  no repeats, nothing over-exposed")
    if a.check or not a.fix:
        return

    cat = M.load_catalog()
    open_ = slots(stories, repin_all=a.repin_all)
    taken, per_story = pinned_counts(stories)
    plan = allocate(open_, cat, uses, taken, story_pins=per_story, cap=a.cap,
                    floor=a.floor, max_drop=a.max_drop, fatigue=a.fatigue)
    by_id = {c["id"]: c for c in cat}
    for (slug, bi, ci), (cid, fit, forced) in sorted(plan.items()):
        stories[slug]["beats"][bi]["cast"][ci]["clip"] = cid
        flag = "  FORCED REPEAT" if forced else ""
        print(f"  {slug:34s} beat {bi} -> [{cid}] {by_id[cid]['primary']:26s} "
              f"fit {fit:4.1f}{flag}")
    for slug, s in stories.items():
        with open(os.path.join(STORIES, slug + ".json"), "w") as f:
            json.dump(s, f, indent=2)
            f.write("\n")
    print(f"\nrewrote {len(stories)} stories")


if __name__ == "__main__":
    main()
