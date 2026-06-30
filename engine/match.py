#!/usr/bin/env python3
"""Emotion -> clip matcher.

A story beat asks for a feeling in plain words (e.g. want=["screaming","rage"]
or a free-text query "boss losing his temper"). This scores every catalog clip
against that request by overlap with its emotion tags / primary / use_for, and
returns the best match. Deterministic and explainable — no model call needed at
match time, because the describing was already done once in catalog.json.
"""
import json, os, re
from paths import CATALOG, DATA

def load_catalog(path=None):
    with open(path or CATALOG) as f:
        return json.load(f)

def load_blocklist():
    """Clip IDs that must never be picked (cursed AI human-hybrid clips, etc.)."""
    p = os.path.join(DATA, "blocklist.json")
    try:
        with open(p) as f:
            return set(json.load(f).get("blocked", {}))
    except FileNotFoundError:
        return set()

def load_favored():
    """Clip IDs to softly PREFER: id -> score bonus. Counteracts the cross-video
    diversity `penalty` so a recurring mascot (e.g. the yapapa cat #182) keeps
    winning whenever it's a reasonable match. Mirror of the blocklist."""
    p = os.path.join(DATA, "favorites.json")
    try:
        with open(p) as f:
            return {k: float(v) for k, v in json.load(f).get("favored", {}).items()}
    except FileNotFoundError:
        return {}

BLOCKED = load_blocklist()
FAVORED = load_favored()

_WORD = re.compile(r"[a-z0-9']+")
def toks(s):
    return set(_WORD.findall(s.lower()))

QUALITY_BONUS = {"good": 0.6, "ok": 0.2, "partial": 0.0, "low": -0.6, "avoid": -3.0}

def score(clip, want, query=""):
    """want: list of desired emotion keywords. query: optional free text."""
    want = [w.lower() for w in (want or [])]
    tags = set(t.lower() for t in clip["emotions"])
    haystack = toks(" ".join([clip["primary"], clip["use_for"], clip["action"], clip["title"]])) | tags
    s = 0.0
    matched = []
    for w in want:
        wt = toks(w)
        if w in tags:                       # exact tag hit — strongest
            s += 3.0; matched.append(w); continue
        if wt & tags:                       # token hits a tag
            s += 2.0; matched.append(w); continue
        if wt & haystack:                   # token appears in description
            s += 1.0; matched.append(w); continue
        # fuzzy: tag contains/contained-by the wanted word
        if any(w in t or t in w for t in tags):
            s += 1.3; matched.append(w)
    for q in toks(query):
        if q in tags: s += 1.0
        elif q in haystack: s += 0.4
    s += QUALITY_BONUS.get(clip["quality"], 0)
    return s, matched

def match(want, query="", catalog=None, exclude=None, orientation=None,
          penalize=None, penalty=-1.5):
    """exclude: clip ids removed from contention entirely (repeats within one
    video + the cursed-clip blocklist). penalize: clip ids softly discouraged
    (used by OTHER videos) — they score `penalty` lower so unused clips win when
    quality is comparable, but a strong match still beats a weak unused clip.
    Keeps the channel diverse WITHOUT digging into broken/low-quality clips once
    the good ones are spent. Clips in data/favorites.json get a positive bonus
    (loaded into FAVORED) so a recurring mascot keeps winning relevant beats even
    after it's been used elsewhere — it offsets `penalty`."""
    catalog = catalog or load_catalog()
    exclude = set(exclude or []) | BLOCKED
    penalize = set(penalize or [])
    ranked = []
    for c in catalog:
        if c["id"] in exclude:
            continue
        sc, matched = score(c, want, query)
        if orientation and c["orientation"] != orientation:
            sc -= 0.5
        if c["id"] in penalize:
            sc += penalty
        if c["id"] in FAVORED:              # mascot boost — survives the diversity penalty
            sc += FAVORED[c["id"]]
        ranked.append((sc, c, matched))
    ranked.sort(key=lambda r: r[0], reverse=True)
    return ranked

def best(want, query="", catalog=None, exclude=None, orientation=None,
         penalize=None, penalty=-1.5):
    ranked = match(want, query, catalog, exclude, orientation, penalize, penalty)
    return ranked[0] if ranked else (0, None, [])

if __name__ == "__main__":
    import sys
    cat = load_catalog()
    want = sys.argv[1:] or ["screaming", "rage"]
    print(f"want: {want}\n")
    for sc, c, m in match(want, catalog=cat)[:5]:
        print(f"  {sc:5.1f}  [{c['id']}] {c['primary']:32s} matched={m}")
