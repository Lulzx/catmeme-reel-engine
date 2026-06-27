"""Scaffold a story JSON from a one-line POV premise.

This builds a watchable 8-beat escalation arc with broad emotion tags and a
chosen background scene. It's a *draft* — refine the captions/reactions in the
Stories editor (or ask Claude in chat) for the good stuff. Used by the web
"Generate batch" feature and importable as a helper.
"""
import json, os, re
from paths import STORIES

CANVAS = {"w": 1080, "h": 1920, "fps": 30}
OUTRO_CAST = [{"name": "", "want": ["cute", "dancing", "happy", "playful"], "size": 0.44}]

# a generic rise-and-fall arc that fits most "POV" escalation jokes
ARC = [
    ("*how it started*",        ["confident", "hopeful", "cheerful", "smug"]),
    ("*the first warning sign*", ["curious", "surprised", "wondering", "skeptical"]),
    ("*wait... what?*",          ["shocked", "startled", "stunned", "alarmed"]),
    ("*trying to stay calm*",    ["nervous", "awkward", "flustered", "uneasy"]),
    ("*it only gets worse*",     ["annoyed", "fed-up", "unamused", "done"]),
    ("*full panic mode*",        ["panicked", "frantic", "distressed", "freaking-out"]),
    ("*total defeat*",           ["defeated", "sad", "heartbroken", "broken"]),
    ("*how it ended*",           ["resigned", "deadpan", "blank-stare", "done"]),
]


def slugify(pov: str) -> str:
    s = re.sub(r"^\s*pov:\s*", "", pov.strip().lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return "-".join(s.split("-")[:6]) or "draft"


def make_story(pov: str, scene: str = "home") -> dict:
    pov = pov.strip()
    if not re.match(r"(?i)^pov:", pov):
        pov = "POV: " + pov
    beats = [{"action": cap, "bg": {"place": scene},
              "cast": [{"name": "ME", "want": list(w), "size": 0.5}]} for cap, w in ARC]
    beats[-1]["dur"] = 6.0
    return {
        "title": re.sub(r"(?i)^pov:\s*", "", pov).strip().title(),
        "output": f"{slugify(pov)}.mp4",
        "canvas": CANVAS, "max_beat_dur": 4.5, "baseline": 0.9,
        "pov": pov, "outro": "FOLLOW FOR MORE", "outro_cast": OUTRO_CAST,
        "beats": beats,
    }


def write_draft(pov: str, scene: str = "home") -> str:
    """Author a draft story to data/stories/<slug>.json; return the slug."""
    slug = slugify(pov)
    with open(os.path.join(STORIES, slug + ".json"), "w") as f:
        json.dump(make_story(pov, scene), f, indent=2, ensure_ascii=False)
        f.write("\n")
    return slug
