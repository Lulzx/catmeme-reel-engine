"""Scaffold a story JSON from a one-line POV premise.

Builds a watchable draft with a *varied* arc shape, beat count, scene and outro. The
old version emitted the same 8-beat ladder every time, which is a large part of why the
scripts started reading as machine-written (see docs/15-human-voice.md).

It's still only a *draft*: the captions here are structural placeholders, deliberately
bland so nobody ships them as-is. Rewrite them by hand in the Stories editor (or ask
Claude) following doc 15 before rendering. Used by the web "Generate batch" feature and
importable as a helper.

Placeholders are bare text, no `*asterisks*` — the caption is drawn to the frame
literally, so markdown emphasis would end up on screen (rule 18, doc 15). Write the
real captions as quoted speech ("i can jump this") or bare narration (it is 6pm.).
"""
import json, os, re
from paths import STORIES

CANVAS = {"w": 1080, "h": 1920, "fps": 30}
OUTRO_CAST = [{"name": "", "want": ["cute", "dancing", "happy", "playful"], "size": 0.44}]

# Three arc shapes, rotated per premise so a generated batch isn't uniform.
# Each entry: (placeholder caption, emotion tags). Lengths differ on purpose — 5 to 7.
ARCS = {
    # escalate steadily to a peak, then land
    "slow_burn": [
        ("setup",             ["confident", "hopeful", "cheerful", "smug"]),
        ("first sign",        ["curious", "surprised", "wondering", "skeptical"]),
        ("it's worse",        ["shocked", "startled", "stunned", "alarmed"]),
        ("trying to stay calm", ["nervous", "awkward", "flustered", "uneasy"]),
        ("not staying calm",  ["annoyed", "fed-up", "unamused", "done"]),
        ("peak",              ["panicked", "frantic", "distressed", "freaking-out"]),
        ("what i did after",  ["resigned", "deadpan", "blank-stare", "done"]),
    ],
    # build the tension, then nothing happens — the nothing is the joke
    "anticlimax": [
        ("setup",         ["confident", "hopeful", "cheerful", "smug"]),
        ("bracing",       ["nervous", "awkward", "uneasy", "waiting"]),
        ("here it comes", ["alarmed", "startled", "expectant", "anticipation"]),
        ("nothing",       ["blank-stare", "deadpan", "confused", "unamused"]),
        ("oh",            ["resigned", "deadpan", "done", "indifferent"]),
    ],
    # flat beats, one detonation, then a plain admission
    "flat_spike": [
        ("plain fact",     ["bored", "indifferent", "deadpan", "relaxed"]),
        ("plain fact",     ["bored", "distracted", "blank-stare", "unamused"]),
        ("still nothing",  ["bored", "deadpan", "indifferent", "done"]),
        ("the thing",      ["shocked", "stunned", "alarmed", "freaking-out"]),
        ("small reaction", ["defeated", "resigned", "sulking", "done"]),
        ("the admission",  ["deadpan", "blank-stare", "resigned", "done"]),
    ],
}
ARC_ORDER = ["slow_burn", "anticlimax", "flat_spike"]

# Rule 16: stop defaulting every beat to "home".
SCENES = ["home", "office", "shop", "station", "kitchen", "livingroom",
          "restaurant", "gym", "park", "classroom", "highway", "airport"]

OUTROS = ["FOLLOW IF THIS IS YOU", "FOLLOW FOR DAILY POVS", "FOLLOW FOR MORE",
          "FOLLOW FOR PART 2", "FOLLOW IF YOU'VE DONE THIS"]


def slugify(pov: str) -> str:
    s = re.sub(r"^\s*pov:\s*", "", pov.strip().lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return "-".join(s.split("-")[:6]) or "draft"


def _spread(pov: str, n: int) -> int:
    """Stable per-premise index: the same premise always drafts the same way, but
    different premises in one batch get different arcs / scenes / outros."""
    return sum(ord(ch) for ch in pov) % n


def make_story(pov: str, scene: str = None, arc: str = None) -> dict:
    pov = pov.strip()
    if not re.match(r"(?i)^pov:", pov):
        pov = "POV: " + pov
    arc = arc or ARC_ORDER[_spread(pov, len(ARC_ORDER))]
    scene = scene or SCENES[_spread(pov, len(SCENES))]

    beats = [{"action": cap, "bg": {"place": scene},
              "cast": [{"name": "ME", "want": list(w), "size": 0.5}]}
             for cap, w in ARCS[arc]]
    beats[-1]["dur"] = 6.0
    return {
        # rule 12: lowercase, not Title Case
        "title": re.sub(r"(?i)^pov:\s*", "", pov).strip().lower(),
        "output": f"{slugify(pov)}.mp4",
        "canvas": CANVAS, "max_beat_dur": 4.5, "baseline": 0.9,
        "pov": pov,
        "outro": OUTROS[_spread(pov, len(OUTROS))], "outro_cast": OUTRO_CAST,
        "beats": beats,
    }


def write_draft(pov: str, scene: str = None, arc: str = None) -> str:
    """Author a draft story to data/stories/<slug>.json; return the slug."""
    slug = slugify(pov)
    with open(os.path.join(STORIES, slug + ".json"), "w") as f:
        json.dump(make_story(pov, scene, arc), f, indent=2, ensure_ascii=False)
        f.write("\n")
    return slug
