#!/usr/bin/env python3
"""Build a saga's manifest, render it locally to output/<slug>.mp4, and register
it in videos.db so it schedules + posts through the SAME YouTube pipeline as the
Shorts (engine/upload.py, the Calendar tab, fill_schedule, …).

Everything is local + $0: saga_build.py synthesises narration (Piper/Kitten) and
caption timing (whisper.cpp), then hyperframes/render.mjs renders on the Mac with
HyperFrames (HTML + GSAP). No cloud, no Lambda.

Progress streams to stdout so the web server can relay it over SSE
(GET /api/sagas/<slug>/build-render/stream).

  python3 engine/saga_render.py <slug>            # build + render + register
  python3 engine/saga_render.py <slug> --no-register   # build + render only
"""
from __future__ import annotations
import json
import os
import subprocess
import sys

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
for _p in (ENGINE, REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
import saga_build  # noqa: E402
from engine import db as DB  # noqa: E402
from engine import upload as UP  # noqa: E402

RENDER_MJS = os.path.join(REPO, "hyperframes", "render.mjs")


def _ffprobe_dur(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip() or 0), 1)
    except Exception:
        return 0.0


def _default_description(story):
    """A YouTube description for a saga, woven from its own metadata so authors
    don't have to write one. Chapter timestamps (if any) are appended at upload."""
    hook = story.get("logline") or story.get("title", "")
    return (f"{hook}\n\n"
            "A narrated cat saga from Meow and Then 🐾 — rendered start to finish on "
            "one little Mac, just for fun.\n\n"
            "#cats #catstory #narrated #catmemes #funnycats")


def register(con, story, slug, out_rel, duration):
    """Upsert a rendered saga into videos.db as a queued long-form video. Never
    downgrades one that's already scheduled/posted — just refreshes its file +
    duration so the upload still points at the latest render."""
    existing = DB.get_video(con, slug)
    if existing and existing.get("status") in ("scheduled", "posted"):
        DB.set_fields(con, slug, file=out_rel, kind="saga",
                      duration_sec=int(round(duration)))
        return existing["status"]

    title = story.get("title", slug)
    DB.upsert_video(con, {
        "slug": slug,
        "sort_order": (existing or {}).get("sort_order") or DB.max_sort_order(con) + 1,
        "pov": title,
        "title": title[:100],
        "description": story.get("description") or _default_description(story),
        "tags": story.get("tags") or
                ["cat story", "cat memes", "narrated", "wojak cat", "funny cats"],
        "file": out_rel,
        "status": "queued",
        "kind": "saga",
        "duration_sec": int(round(duration)),
        "chapters": story.get("chapters", []),
        "posted": (existing or {}).get("posted"),
        "publish_at": (existing or {}).get("publish_at"),
        "video_id": (existing or {}).get("video_id"),
    })
    return "queued"


def build_and_render(slug, do_register=True):
    spath = os.path.join(paths.SAGAS, slug + ".json")
    if not os.path.exists(spath):
        sys.exit(f"no saga '{slug}' at {spath}")
    story = json.load(open(spath))

    # 1) semantic JSON -> render manifest (narration, captions, geometry)
    print(f"── building manifest for {slug} ──", flush=True)
    manifest = saga_build.build(spath)

    # 2) render locally with HyperFrames -> output/<slug>.mp4
    out_rel = os.path.join("output", f"{slug}.mp4")
    out_abs = os.path.join(REPO, out_rel)
    print(f"── rendering {slug} locally (hyperframes) ──", flush=True)
    proc = subprocess.Popen(
        ["node", RENDER_MJS, manifest, out_abs],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
    proc.wait()
    if proc.returncode != 0:
        sys.exit(f"hyperframes render failed (code {proc.returncode})")
    if not os.path.exists(out_abs):
        sys.exit(f"render reported success but {out_rel} is missing")

    dur = _ffprobe_dur(out_abs)
    print(f"  rendered {out_rel} — {dur:.1f}s", flush=True)

    # 3) register in the DB so it joins the posting pipeline
    if do_register:
        con = DB.connect()
        DB.init(con)
        status = register(con, story, slug, out_rel, dur)
        UP.render_md(con)   # refresh youtube.md + data/videos.json (shows in Calendar)
        con.close()
        print(f"✓ {slug} registered as a saga ({dur:.0f}s, {status})", flush=True)
    else:
        print(f"✓ {slug} rendered (not registered)", flush=True)
    return out_rel


def main():
    args = [a for a in sys.argv[1:]]
    do_register = "--no-register" not in args
    args = [a for a in args if not a.startswith("--")]
    if not args:
        sys.exit("usage: python3 engine/saga_render.py <slug> [--no-register]")
    build_and_render(args[0], do_register=do_register)


if __name__ == "__main__":
    main()
