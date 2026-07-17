"""Canonical project paths — single source of truth for every script.

Layout:
  clips/         source green-screen clips (input)
  backgrounds/   bundled AI scene library (input asset, preferred over the web)
  data/          committed text data
    catalog.json   the "describe once" clip library
    stories/*.json the narratives (short POV reels)
    sagas/*.json   long-form narrated cat stories (HyperFrames sagas)
  work/          regenerable artifacts (safe to delete; rebuilt on demand)
    frames/        one representative frame per clip
    overlays/      per-beat text-overlay PNGs
    bg_render/     per-beat composited background PNGs
    bg_cache/      web-fetched background photos (cached by query)
    beat_clips/    per-beat rendered mp4s + concat list
    manifests/     per-saga render manifests (HyperFrames input)
  output/        finished reels
"""
import os

ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS       = os.path.join(ROOT, "clips")
BACKGROUNDS = os.path.join(ROOT, "backgrounds")
DATA        = os.path.join(ROOT, "data")
CATALOG     = os.path.join(DATA, "catalog.json")
STORIES     = os.path.join(DATA, "stories")
SAGAS       = os.path.join(DATA, "sagas")
WORK        = os.path.join(ROOT, "work")
FRAMES      = os.path.join(WORK, "frames")
OVERLAYS    = os.path.join(WORK, "overlays")
BG_RENDER   = os.path.join(WORK, "bg_render")
BG_CACHE    = os.path.join(WORK, "bg_cache")
BEAT_CLIPS  = os.path.join(WORK, "beat_clips")
MANIFESTS   = os.path.join(WORK, "manifests")
OUTPUT      = os.path.join(ROOT, "output")

def ensure():
    for d in (CLIPS, BACKGROUNDS, DATA, STORIES, SAGAS, FRAMES, OVERLAYS,
              BG_RENDER, BG_CACHE, BEAT_CLIPS, MANIFESTS, OUTPUT):
        os.makedirs(d, exist_ok=True)
