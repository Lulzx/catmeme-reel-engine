#!/usr/bin/env python3
"""Emotion -> clip matcher.

A story beat asks for a feeling in plain words (e.g. want=["screaming","rage"]
or a free-text query "boss losing his temper"). This scores every catalog clip
against that request by overlap with its emotion tags / primary / use_for, and
returns the best match. Deterministic and explainable — no model call needed at
match time, because the describing was already done once in catalog.json.
"""
import json, re
from paths import CATALOG

def load_catalog(path=None):
    with open(path or CATALOG) as f:
        return json.load(f)

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

def match(want, query="", catalog=None, exclude=None, orientation=None):
    catalog = catalog or load_catalog()
    exclude = set(exclude or [])
    ranked = []
    for c in catalog:
        if c["id"] in exclude:
            continue
        sc, matched = score(c, want, query)
        if orientation and c["orientation"] != orientation:
            sc -= 0.5
        ranked.append((sc, c, matched))
    ranked.sort(key=lambda r: r[0], reverse=True)
    return ranked

def best(want, query="", catalog=None, exclude=None, orientation=None):
    ranked = match(want, query, catalog, exclude, orientation)
    return ranked[0] if ranked else (0, None, [])

if __name__ == "__main__":
    import sys
    cat = load_catalog()
    want = sys.argv[1:] or ["screaming", "rage"]
    print(f"want: {want}\n")
    for sc, c, m in match(want, catalog=cat)[:5]:
        print(f"  {sc:5.1f}  [{c['id']}] {c['primary']:32s} matched={m}")
