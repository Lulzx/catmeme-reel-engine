"""Shared geometry + look presets for both the Shorts renderer and the long-form
wojak-style story pipeline.

`layout()` is the original full-frame compositing math (kept identical so the
Shorts pipeline can import it from here). `sprite_box()` is the long-form variant:
it positions a *tight-cropped* cat cutout as a grounded "bust", wojak-style.

MOODS turns a one-word emotion ("doomer", "bloomer", ...) into resolved CSS the
HyperFrames renderer applies verbatim — the brain stays in Python; the renderer
stays dumb.
"""
from __future__ import annotations


# ── original Shorts geometry (ported verbatim from render.py:292) ─────────────
def layout(cast_clips, positions, sizes, baselines, W, H):
    geos = []
    for clip, pos, size, base in zip(cast_clips, positions, sizes, baselines):
        bx0, by0, bx1, by1 = clip["bbox"]
        cw, ch = clip["width"], clip["height"]
        bbh = max(0.15, by1 - by0)
        dispH = size * H / bbh
        dispW = dispH * (cw / ch)
        Y = int(base * H - by1 * dispH)
        X = int(pos * W - ((bx0 + bx1) / 2) * dispW)
        cat_cx = int(pos * W)
        cat_top = int(Y + by0 * dispH)
        cat_w = (bx1 - bx0) * dispW
        geos.append(dict(X=X, Y=Y, dispW=int(dispW), dispH=int(dispH),
                         cx=cat_cx, top=cat_top, base_y=int(base * H), catw=cat_w))
    return geos


# ── long-form: place a tight-cropped cutout as a grounded bust ────────────────
def sprite_box(clip, W, H, size=0.74, pos=0.5, baseline=1.05):
    """Rect (px) for a cutout that was cropped to the clip's bbox.

    size     = cutout height as a fraction of canvas height (bust ~0.7–0.85)
    pos      = horizontal center (0..1)
    baseline = where the cutout's *bottom* sits (1.0 = canvas bottom; >1 runs off
               the bottom edge so the bust reads as standing, not cut off)
    """
    bx0, by0, bx1, by1 = clip["bbox"]
    cw, ch = clip["width"], clip["height"]
    crop_w = max(1.0, (bx1 - bx0) * cw)
    crop_h = max(1.0, (by1 - by0) * ch)
    disp_h = size * H
    disp_w = disp_h * (crop_w / crop_h)
    x = pos * W - disp_w / 2
    y = baseline * H - disp_h
    return {"x": round(x), "y": round(y), "width": round(disp_w), "height": round(disp_h)}


# default horizontal positions for N characters in a scene
DEFAULT_POS = {1: [0.5], 2: [0.30, 0.70], 3: [0.20, 0.5, 0.80]}


# ── mood → resolved CSS (Low Budget Stories style: lighting carries emotion) ──
def _mood(bg_filter, tint, tint_opacity, blend, vignette, char_filter):
    return {
        "bg": {"filter": bg_filter, "tint": tint, "tintOpacity": tint_opacity,
               "blend": blend, "vignette": vignette},
        "char": {"filter": char_filter},
    }


MOODS = {
    # cold, dim, hopeless
    "doomer": _mood("brightness(0.72) saturate(0.7) contrast(1.06)", "#0e1b3a", 0.42,
                    "multiply", 0.55, "brightness(0.78) saturate(0.7) contrast(1.05) sepia(0.25) hue-rotate(185deg)"),
    "sad": _mood("brightness(0.8) saturate(0.75) contrast(1.04)", "#15244a", 0.35,
                 "multiply", 0.45, "brightness(0.85) saturate(0.75) sepia(0.2) hue-rotate(185deg)"),
    # warm, bright, triumphant
    "bloomer": _mood("brightness(1.1) saturate(1.2) contrast(1.03)", "#ff9a3c", 0.26,
                     "soft-light", 0.22, "brightness(1.12) saturate(1.22) contrast(1.02) sepia(0.18) hue-rotate(-20deg)"),
    "happy": _mood("brightness(1.06) saturate(1.15)", "#ffb24d", 0.2,
                   "soft-light", 0.25, "brightness(1.08) saturate(1.18) sepia(0.12) hue-rotate(-15deg)"),
    # high-tension / dramatic
    "dramatic": _mood("brightness(0.9) saturate(1.1) contrast(1.12)", "#5a1414", 0.4,
                      "multiply", 0.5, "brightness(0.92) saturate(1.12) contrast(1.1) sepia(0.2) hue-rotate(-12deg)"),
    "tense": _mood("brightness(0.85) saturate(0.95) contrast(1.1)", "#2a0d0d", 0.38,
                   "multiply", 0.55, "brightness(0.9) saturate(1.0) contrast(1.08) sepia(0.15) hue-rotate(-10deg)"),
    # plain
    "neutral": _mood("brightness(0.98) saturate(1.0)", "#000000", 0.28,
                     "normal", 0.35, "none"),
}


def mood(name):
    return MOODS.get((name or "neutral").lower(), MOODS["neutral"])
