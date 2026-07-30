"""Check story captions against the human-voice rules in docs/15-human-voice.md.

    python3 -m engine.lint_voice                     # lint every story
    python3 -m engine.lint_voice slug [slug ...]     # lint specific ones
    python3 -m engine.lint_voice --batch a b c       # also check batch-level repetition

Exit code 1 if any error-level rule is violated, so it can gate a render.
Warnings are judgement calls; errors are the tells viewers actually named.
"""
import glob
import json
import os
import re
import sys
from collections import Counter

from engine.paths import STORIES

# Emotion tags that leaked into captions in the flagged scripts (rule 5).
TAG_WORDS = {"deadpan", "resigned", "defeated", "blank-stare", "unamused", "smug",
             "panicked", "flustered", "stunned", "indifferent", "dissociating"}

# Abstract-noun closers banned by rule 9.
METAPHOR_WORDS = {"soul", "void", "chaos", "buffering", "personality", "existence",
                  "demise", "essence", "aura", "trauma", "era"}

# Rule 4: a caption ending in a bare labelling noun phrase, e.g. "peak desperation."
NOUN_PUNCHLINE = re.compile(
    r"(?:^|\.\s+)(?:peak|pure|total|absolute|full|complete|genuine|certified)\s+"
    r"[a-z\- ]{3,30}[.!]?\*?$", re.I)


def captions(story):
    return [b["action"] for b in story.get("beats", []) if b.get("action")]


def strip(c):
    return c.strip().strip("*").strip()


def lint(slug, story):
    errs, warns = [], []
    caps = captions(story)
    body = " ".join(caps)
    n = len(caps)

    # ── shape ────────────────────────────────────────────────────────────
    if not 5 <= n <= 9:
        warns.append(f"rule 1: {n} beats (want 5-9)")

    # ── the tells that got named ────────────────────────────────────────
    for c in caps:
        s = strip(c)
        if NOUN_PUNCHLINE.search(s):
            errs.append(f"rule 4 noun-phrase punchline: {c}")
        low = s.lower()
        for t in TAG_WORDS:
            # an emotion tag as its own sentence/fragment is the leak
            if re.search(rf"(?:^|[.,]\s*){re.escape(t)}[.!]?$", low):
                errs.append(f"rule 5 emotion tag in caption ('{t}'): {c}")
                break
        if "—" in c:
            errs.append(f"rule 7 em dash: {c}")
        if "*" in c:
            # the caption is drawn literally, so an asterisk ends up on screen
            errs.append(f"rule 18 asterisk in caption (quote it or drop the "
                        f"markers): {c}")
        for w in METAPHOR_WORDS:
            if re.search(rf"\b{w}\b", low):
                errs.append(f"rule 9 metaphor noun ('{w}'): {c}")

    # rule 6: most beats should be a single clause
    welded = sum(1 for c in caps if len(re.findall(r"[.!?]\s+\S", strip(c))) >= 1)
    if n and welded / n > 0.5:
        warns.append(f"rule 6: {welded}/{n} beats weld 2+ clauses (keep under half)")

    # rule 8: at most one ellipsis per script
    ell = len(re.findall(r"\.\.\.|…", body))
    if ell > 1:
        errs.append(f"rule 8: {ell} ellipses (max 1)")

    # rule 11: at most one shouted word
    caps_words = [w for w in re.findall(r"\b[A-Z]{3,}\b", body)
                  if w not in {"POV", "AC", "OK"}]
    # a recurring character name (DEREK) is a proper noun, not emphasis
    names = {m["name"] for b in story.get("beats", []) for m in b.get("cast", []) if m.get("name")}
    shouted = [w for w in caps_words if w not in names]
    if len(set(shouted)) > 1:
        warns.append(f"rule 11: {len(set(shouted))} shouted words {sorted(set(shouted))} (max 1)")

    # rule 12: lowercase title
    title = story.get("title", "")
    if title != title.lower():
        errs.append(f"rule 12: title is not lowercase: {title!r}")

    # rule 3: a third of beats should be flat (no joke punctuation, short)
    flat = sum(1 for c in caps if len(strip(c).split()) <= 5)
    if n and flat / n < 0.25:
        warns.append(f"rule 3: only {flat}/{n} short/flat beats (want ~a third)")

    return errs, warns


def lint_batch(stories):
    """Batch-level checks: repeated furniture across a run (rules 15-16)."""
    out = []
    outros = Counter(s.get("outro", "") for s in stories.values() if s.get("outro"))
    for o, c in outros.items():
        if c > 3:
            out.append(f"rule 15: outro {o!r} reused {c}x in batch (max 3)")
    scenes = [next((b.get("bg", {}).get("place") for b in s.get("beats", [])), None)
              for s in stories.values()]
    for a, b in zip(scenes, scenes[1:]):
        if a and a == b:
            out.append(f"rule 16: scene {a!r} repeats back-to-back in batch order")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    batch_mode = "--batch" in sys.argv
    if args:
        paths = [os.path.join(STORIES, a.replace(".json", "") + ".json") for a in args]
    else:
        paths = sorted(glob.glob(os.path.join(STORIES, "*.json")))

    stories, n_err = {}, 0
    for p in paths:
        slug = os.path.basename(p)[:-5]
        try:
            story = json.load(open(p))
        except Exception as exc:
            print(f"✗ {slug}: unreadable ({exc})")
            n_err += 1
            continue
        stories[slug] = story
        errs, warns = lint(slug, story)
        n_err += len(errs)
        if errs or warns:
            print(f"\n{'✗' if errs else '·'} {slug}")
            for e in errs:
                print(f"    ERROR  {e}")
            for w in warns:
                print(f"    warn   {w}")

    if batch_mode:
        for msg in lint_batch(stories):
            print(f"\n    BATCH  {msg}")

    print(f"\n{len(stories)} stories linted · {n_err} error(s)")
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
