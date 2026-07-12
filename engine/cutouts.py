"""Extract keyed, tight-cropped, feathered cat cutouts for the wojak-style story
renderer — reusing each clip's catalog key_color + bbox.

Two products (the local ffmpeg's WebM alpha encoders are broken, so we use PNG):
  • sprite   — one feathered RGBA still per clip   -> work/sprites/<id>.png
  • sequence — feathered RGBA frame run (punchlines) -> work/seq/<id>/NNNN.png

The chroma chain matches the Shorts renderer (render.py:387) so cutouts look
identical to the Shorts.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys

try:
    from engine.paths import CLIPS, WORK, CATALOG
except ImportError:  # when engine/ is already on sys.path
    from paths import CLIPS, WORK, CATALOG

SPRITES = os.path.join(WORK, "sprites")
SEQ = os.path.join(WORK, "seq")

KEY_SIM = "0.12"
KEY_BLEND = "0.08"
DESPILL = "despill=type=green:mix=0.6:expand=0.4"


def load_catalog():
    c = json.load(open(CATALOG))
    return c if isinstance(c, list) else c.get("clips", c)


def get_clip(cid, catalog=None):
    catalog = catalog or load_catalog()
    return next(x for x in catalog if x["id"] == cid)


def _crop_expr(clip, pad):
    """ffmpeg crop=... for the clip's bbox, padded and clamped to the frame."""
    bx0, by0, bx1, by1 = clip["bbox"]
    pw, ph = pad, pad
    x0 = max(0.0, bx0 - pw); y0 = max(0.0, by0 - ph)
    x1 = min(1.0, bx1 + pw); y1 = min(1.0, by1 + ph)
    w, h = x1 - x0, y1 - y0
    return f"crop=iw*{w:.4f}:ih*{h:.4f}:iw*{x0:.4f}:ih*{y0:.4f}"


def _key_chain(clip):
    return f"chromakey={clip['key_color']}:{KEY_SIM}:{KEY_BLEND},{DESPILL},format=rgba"


def _feather(path, erode=True, blur=1.2):
    """Soften the cutout edge + strip the 1px green fringe (alpha erode + blur)."""
    from PIL import Image, ImageFilter
    im = Image.open(path).convert("RGBA")
    a = im.getchannel("A")
    if erode:
        a = a.filter(ImageFilter.MinFilter(3))
    if blur:
        a = a.filter(ImageFilter.GaussianBlur(blur))
    im.putalpha(a)
    im.save(path)


def _sharpness_fill(path):
    """Laplacian variance over the opaque subject (sharpness) + opaque fraction."""
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im.getchannel("A"), dtype="float32") / 255.0
    g = np.asarray(im.convert("L"), dtype="float32")
    lap = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1])
    mask = a[1:-1, 1:-1] > 0.5
    fill = float((a > 0.5).mean())
    sharp = float(lap[mask].var()) if mask.sum() > 500 else 0.0
    return sharp, fill


def _grab(src, vf, t, out):
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-ss", str(t), "-i", src,
                    "-vf", vf, "-frames:v", "1", out], check=True, capture_output=True)


def extract_sprite(clip, out=None, t=None, pad=0.06, feather=True):
    """Pick the sharpest (least motion-blurred) keyed frame as the sprite."""
    os.makedirs(SPRITES, exist_ok=True)
    out = out or os.path.join(SPRITES, f"{clip['id']}.png")
    src = os.path.join(CLIPS, clip["file"])
    vf = f"{_crop_expr(clip, pad)},{_key_chain(clip)}"
    if t is not None:
        _grab(src, vf, t, out)
    else:
        import shutil
        dur = clip.get("duration", 2)
        tmp = out + ".cand.png"
        best = -1.0
        for f in (0.2, 0.35, 0.5, 0.65, 0.8):
            _grab(src, vf, round(dur * f, 2), tmp)
            sharp, fill = _sharpness_fill(tmp)
            score = sharp * (0.4 + fill)
            if fill > 0.04 and score > best:
                best = score
                shutil.copy(tmp, out)
        if best < 0:  # nothing substantial — fall back to mid-clip
            _grab(src, vf, round(dur * 0.4, 2), out)
        if os.path.exists(tmp):
            os.remove(tmp)
    if feather:
        _feather(out)
    return out


def extract_sequence(clip, out_dir=None, start=0.0, dur=None, fps=18, pad=0.12,
                     scale_h=900, feather=False):
    cid = clip["id"]
    out_dir = out_dir or os.path.join(SEQ, cid)
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):  # clear stale frames
        if f.endswith(".png"):
            os.remove(os.path.join(out_dir, f))
    dur = dur if dur is not None else min(clip.get("duration", 3), 4.0)
    vf = f"fps={fps},{_crop_expr(clip, pad)},{_key_chain(clip)},scale=-1:{scale_h}"
    cmd = ["ffmpeg", "-y", "-nostdin", "-ss", str(start), "-t", str(dur),
           "-i", os.path.join(CLIPS, clip["file"]), "-vf", vf,
           os.path.join(out_dir, "%04d.png")]
    subprocess.run(cmd, check=True, capture_output=True)
    frames = sorted(f for f in os.listdir(out_dir) if f.endswith(".png"))
    if feather:
        for f in frames:
            _feather(os.path.join(out_dir, f), blur=0.8)
    return {"dir": out_dir, "count": len(frames), "fps": fps}


# Pixel motion/sharpness metrics don't separate "smears as a still" reliably
# across clips (texture + per-frame variance dominate). The human-curated catalog
# description is the dependable signal: animate motion-y actions, keep calm ones still.
MOTION_WORDS = ("danc", "dramatic", "recoil", "slap", "attack", "smack", "hit", "punch",
                "scream", "yell", "yap", "rant", "talk", "zoomies", "run", "chase", "jump",
                "spin", "shake", "flail", "pounce", "hype", "headbang", "bonk", "fight",
                "panic", "freak", "wiggle", "bounce", "throw", "vibing", "groov", "kick",
                "spaz", "wild", "chaos", "sprint", "leap", "hyper", "rage")
CALM_WORDS = ("dead-inside", "deadpan", "zoning", "blank", "stare", "staring", "sleep",
              "content", "sitting", "still", "frozen", "sad", "depress", "tired",
              "exhausted", "loaf", "nap", "deadpan", "unimpressed")


def should_animate(clip):
    """True if the clip's described action moves enough that a static still smears."""
    text = " ".join([clip.get("primary", ""), clip.get("action", ""), clip.get("use_for", ""),
                     " ".join(clip.get("emotions", []))]).lower()
    if any(w in text for w in CALM_WORDS):
        return False
    return any(w in text for w in MOTION_WORDS)


if __name__ == "__main__":
    cat = load_catalog()
    if sys.argv[1:2] == ["motion"]:
        for cid in sys.argv[2:]:
            c = get_clip(cid, cat)
            print(f"{cid}  animate={should_animate(c)}  ({c.get('primary')})")
    else:
        for cid in sys.argv[1:] or ["002", "003", "008"]:
            clip = get_clip(cid, cat)
            print("sprite", cid, "->", extract_sprite(clip))
