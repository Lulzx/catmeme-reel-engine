"""wrapped: a year-in-review story, one slide per stat, in the style of music-app wraps.

Each `slides` entry: `t`, two gradient `colors`, a small `label`, a `big` line
(or a numbered `list`), a `sub` line and a cat in a circle (`clip`). Segmented
progress bars run along the top. A soft synth pulse plays under everything.
Layout keeps to the Shorts safe area (engine/safe_zone.py): text ends above
y 860 and the circle sits at x 240..720, y 880..1370.
"""
import numpy as np
from PIL import Image, ImageDraw

from simple_render import Cat, window_bg, fit_font, ease, whoosh
from chat_render import W, H, SR, font, comp, wrap, draw_rich, circle_mask, ease_out_back, tone

BG = (0, 0, 0)
X0, X1 = 60, 1020
D, CX, CY = 490, 480, 1125                  # circle diameter and centre


def pulse(dur, bpm=96):
    out = np.zeros((int(dur * SR), 2), dtype=np.float32)
    step = 60 / bpm
    t = 0.0
    while t < dur - 0.3:
        k = tone(90, 50, 0.25, 0.22, 14)
        i0 = int(t * SR); seg = k[: len(out) - i0]
        out[i0:i0 + len(seg)] += seg
        h = tone(5200, 5200, 0.03, 0.03, 120)
        i1 = int((t + step / 2) * SR); seg = h[: max(0, len(out) - i1)]
        out[i1:i1 + len(seg)] += seg
        t += step
    return out


def gradient(c0, c1):
    g = np.linspace(0, 1, H)[:, None, None]
    a = np.array(c0, dtype=np.float32)[None, None, :]
    b = np.array(c1, dtype=np.float32)[None, None, :]
    arr = (a + (b - a) * g) * np.ones((1, W, 1), dtype=np.float32)
    return Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")


def PLAN(s, slug):
    track = [(0.0, pulse(s["end"]) * 0.8)]
    slides = s["slides"]
    for i, sl in enumerate(slides):
        until = slides[i + 1]["t"] if i + 1 < len(slides) else s["end"]
        sl["until"] = until
        sl["bgim"] = gradient(*sl["colors"])
        sl["cat"] = Cat(slug, f"slide{i:02d}", sl["clip"], sl["start"], until - sl["t"], int(D * 1.0))
        sl["cbg"] = window_bg(sl.get("bg", "livingroom.jpg"), D, D, blur=4)
        if i:
            track.append((sl["t"], whoosh()))
        if sl.get("sound", True):
            track.append((sl["t"] + 0.6, sl["cat"].audio(min(sl["cat"].dur, sl.get("sound_dur", 2.5))) * sl.get("vol", 1.0)))
    return dict(slides=slides), track, s["end"]


def DRAW(frame, t, s, P):
    slides = P["slides"]
    sl = [x for x in slides if x["t"] <= t][-1]
    i = slides.index(sl)
    age = t - sl["t"]
    frame.alpha_composite(sl["bgim"])
    d = ImageDraw.Draw(frame)
    # progress segments
    n = len(slides)
    gap = 10
    sw = (X1 - X0 - gap * (n - 1)) / n
    for k in range(n):
        x = X0 + k * (sw + gap)
        d.rounded_rectangle((x, 166, x + sw, 172), 3, fill=(255, 255, 255, 90))
        f = 1 if k < i else (min(1, age / (sl["until"] - sl["t"])) if k == i else 0)
        if f > 0:
            d.rounded_rectangle((x, 166, x + sw * f, 172), 3, fill=(255, 255, 255))
    ink = tuple(sl.get("ink", (255, 255, 255)))
    y = 290
    if sl.get("label"):
        lf = font(52, "Semibold")
        la = ease((age - 0.1) / 0.4)
        for ln in wrap(sl["label"], lf, X1 - X0 - 40)[:3]:
            lay = Image.new("RGBA", (W, 70), (0, 0, 0, 0))
            draw_rich(lay, X0 + 20, 0, [ln], lf, ink, 64)
            lay.putalpha(lay.getchannel("A").point(lambda v, la=la: int(v * la)))
            comp(frame, lay, 0, y + (1 - la) * 20)
            y += 64
        y += 24
    if sl.get("big"):
        ba = ease_out_back(min(1, max(0, (age - 0.6) / 0.45)))
        size = sl.get("big_size", 128)
        bf = fit_font(sl["big"], X1 - X0 - 40, size, "Heavy") if "\n" not in sl["big"] else font(size, "Heavy")
        lines = wrap(sl["big"], bf, X1 - X0 - 40)[:2]
        if ba > 0:
            lay = Image.new("RGBA", (W, int(bf.size * 1.15 * len(lines)) + 20), (0, 0, 0, 0))
            draw_rich(lay, X0 + 20, 0, lines, bf, ink, int(bf.size * 1.15))
            if ba != 1:
                sc = max(0.05, ba)
                lay = lay.resize((max(1, int(lay.width * sc)), max(1, int(lay.height * sc))))
            comp(frame, lay, (X0 + 20) * (1 - ba) + 0, y)
        y += int(bf.size * 1.15 * len(lines)) + 16
    if sl.get("list"):
        for k, item in enumerate(sl["list"]):
            ia = ease((age - 0.5 - k * 0.55) / 0.35)
            if ia <= 0:
                continue
            nf, tf = font(52, "Heavy"), font(46, "Bold")
            lay = Image.new("RGBA", (W, 76), (0, 0, 0, 0))
            ld = ImageDraw.Draw(lay)
            ld.text((X0 + 20, 6), f"{k + 1}", font=nf, fill=ink)
            draw_rich(lay, X0 + 90, 10, wrap(item, tf, X1 - X0 - 130)[:1], tf, ink, 60)
            lay.putalpha(lay.getchannel("A").point(lambda v, ia=ia: int(v * ia)))
            comp(frame, lay, (1 - ia) * 40, y)
            y += 80
        y += 10
    if sl.get("sub") and age >= sl.get("sub_t", 1.6):
        sa = ease((age - sl.get("sub_t", 1.6)) / 0.4)
        sf = font(48, "Semibold")
        lay = Image.new("RGBA", (W, 190), (0, 0, 0, 0))
        draw_rich(lay, X0 + 20, 0, wrap(sl["sub"], sf, X1 - X0 - 40)[:3], sf, ink, 60)
        lay.putalpha(lay.getchannel("A").point(lambda v, sa=sa: int(v * sa)))
        comp(frame, lay, 0, y)
    # the cat, in a circle
    ca = ease_out_back(min(1, max(0, (age - 0.2) / 0.4)))
    if ca > 0:
        sq = sl["cbg"].copy()
        cat = sl["cat"].at(age, loop=True)
        sc = min(D * sl.get("fit", 0.95) / cat.height, D * 1.2 / cat.width)
        cat = cat.resize((max(1, int(cat.width * sc)), max(1, int(cat.height * sc))), Image.BILINEAR)
        comp(sq, cat, (D - cat.width) / 2, D - cat.height + 4)
        sq.putalpha(circle_mask(D))
        ring = Image.new("RGBA", (D + 24, D + 24), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((0, 0, D + 23, D + 23), fill=ink)
        comp(ring, sq, 12, 12)
        if ca != 1:
            ring = ring.resize((max(1, int(ring.width * ca)), max(1, int(ring.height * ca))))
        comp(frame, ring, CX - ring.width / 2, CY - ring.height / 2)
