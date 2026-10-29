"""Shaadi e-invite: a cream card on maroon, in pages. Each page has a round photo
(a live keyed cat) and lines that reveal one at a time; a page can end on a UPI
QR code. Laid out inside the Shorts safe zone (engine/safe_zone.py): the card
spans x 60..900, y 160..1410.

Script keys: pages[] of {t, photo {clip, start, bg, label}, swap? {t, clip, start,
bg, label}, lines[] of {t, text, style}, qr? {t, text}}, end.
styles: small | name | body | big | event (text "title | detail").
"""
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from simple_render import Cat, window_bg, fit_font, ease, whoosh, ding, tick
from chat_render import W, H, FPS, SR, font, emoji, wrap, draw_rich, line_w, comp, tone, circle_mask, \
    ease_out_back, SCRIPT

BG = (92, 14, 30)
CREAM, MAROON, GOLD, INK = (252, 244, 226), (128, 20, 32), (198, 152, 62), (60, 40, 36)
CX0, CX1, CY0, CY1 = 60, 900, 160, 1410
MID = (CX0 + CX1) // 2
PHOTO_D, PHOTO_Y = 340, 236

_S = {}


def script_font(size):
    if size not in _S:
        _S[size] = ImageFont.truetype(SCRIPT, size, index=1)
    return _S[size]


def melody(dur):
    """A slow shehnai-ish line: sines with vibrato over a drone, quiet enough to sit under the clips."""
    notes = [62, 64, 65, 67, 69, 67, 65, 64, 62, 60, 62, 64, 65, 64, 62, 62]
    out = np.zeros(int(dur * SR), dtype=np.float32)
    t, i = 0.0, 0
    while t < dur:
        n = int(1.1 * SR); x = np.arange(n) / SR
        f = 440 * 2 ** ((notes[i % len(notes)] - 69) / 12)
        w = np.sin(2 * np.pi * f * x + 0.6 * np.sin(2 * np.pi * 5.5 * x)) + 0.35 * np.sin(4 * np.pi * f * x)
        w *= np.minimum(1, x * 8) * np.exp(-x * 1.2) * 0.05
        i0 = int(t * SR); seg = w[: len(out) - i0]
        out[i0:i0 + len(seg)] += seg
        t += 1.1; i += 1
    x = np.arange(len(out)) / SR
    out += (np.sin(2 * np.pi * 146.8 * x) * 0.02).astype(np.float32)
    f = int(1.0 * SR)
    out[:f] *= np.linspace(0, 1, f); out[-f:] *= np.linspace(1, 0, f)
    return np.repeat(out[:, None], 2, axis=1)


def kaching():
    return np.concatenate([tone(2100, 2100, 0.05, 0.25, 30), tone(2800, 2800, 0.35, 0.22, 7)])


def qr_image(text, size=300):
    rnd = random.Random(text)
    n = 29
    cell = size // n
    im = Image.new("RGBA", (cell * n + 24, cell * n + 24), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    for yy in range(n):
        for xx in range(n):
            finder = any(fx <= xx < fx + 7 and fy <= yy < fy + 7 for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)))
            if finder:
                continue
            if rnd.random() < 0.5:
                d.rectangle((12 + xx * cell, 12 + yy * cell, 12 + xx * cell + cell - 1, 12 + yy * cell + cell - 1), fill=(0, 0, 0))
    for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)):
        x0, y0 = 12 + fx * cell, 12 + fy * cell
        d.rectangle((x0, y0, x0 + 7 * cell - 1, y0 + 7 * cell - 1), fill=(0, 0, 0))
        d.rectangle((x0 + cell, y0 + cell, x0 + 6 * cell - 1, y0 + 6 * cell - 1), fill=(255, 255, 255))
        d.rectangle((x0 + 2 * cell, y0 + 2 * cell, x0 + 5 * cell - 1, y0 + 5 * cell - 1), fill=(0, 0, 0))
    return im


def plan(s, slug):
    track, pages = [], []
    end_t = s["end"]
    for i, p in enumerate(s["pages"]):
        t1 = s["pages"][i + 1]["t"] if i + 1 < len(s["pages"]) else end_t
        pg = dict(p, t1=t1, photos=[])
        shots = [dict(p["photo"], t=p["t"])] + ([dict(p["swap"])] if p.get("swap") else [])
        for j, ph in enumerate(shots):
            u = shots[j + 1]["t"] if j + 1 < len(shots) else t1
            cat = Cat(slug, f"p{i}{j}", ph["clip"], ph.get("start", 0), u - ph["t"] + 0.2, PHOTO_D)
            pg["photos"].append(dict(ph, t1=u, cat=cat, bg=window_bg(ph.get("bg", "home.jpg"), PHOTO_D, PHOTO_D, blur=3)))
            track.append((ph["t"] + 0.1, cat.audio(min(cat.dur, u - ph["t"])) * ph.get("vol", 1.0)))
        if i:
            track.append((p["t"], whoosh() * 2))
        for ln in p["lines"]:
            track.append((ln["t"], tone(1760, 1760, 0.25, 0.05, 10)))
        if p.get("qr"):
            track.append((p["qr"]["t"], kaching()))
        pages.append(pg)
    track.append((0.0, melody(end_t)))
    return dict(pages=pages), track, end_t


def line_img(ln):
    """Render one invite line, centred, max width 740."""
    st, txt, mw = ln.get("style", "body"), ln["text"], 740
    if st == "event":
        title, detail = [x.strip() for x in txt.split("|", 1)]
        tf, df = font(40, "Bold"), font(32)
        dl = wrap(detail, df, mw - 60)[:2]
        h = 68 + 42 * len(dl)
        im = Image.new("RGBA", (mw, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, mw - 1, h - 1), 20, fill=(246, 232, 204), outline=GOLD, width=3)
        d.text(((mw - tf.getlength(title)) / 2, 12), title, font=tf, fill=MAROON)
        y = 62
        for l in dl:
            draw_rich(im, (mw - line_w(l)) / 2, y, [l], df, INK, 42); y += 42
        return im
    f = {"small": font(34, "Regular", italic=True), "name": script_font(82), "big": font(52, "Heavy"),
         "body": font(38)}[st]
    col = {"small": (120, 90, 80), "name": MAROON, "big": MAROON, "body": INK}[st]
    lines = wrap(txt, f, mw)[:2]
    lh = int(f.size * (1.25 if st != "name" else 1.05))
    im = Image.new("RGBA", (mw, lh * len(lines) + 10), (0, 0, 0, 0))
    y = 0
    for l in lines:
        draw_rich(im, (mw - line_w(l)) / 2, y, [l], f, col, lh); y += lh
    return im


def draw(frame, t, s, st):
    d = ImageDraw.Draw(frame)
    for k in range(0, H, 60):                       # gold dots on maroon, decoration
        for j in range(0, W, 60):
            if (k // 60 + j // 60) % 2 == 0:
                d.ellipse((j + 26, k + 26, j + 32, k + 32), fill=(130, 40, 46))
    pf = fit_font(s["pov"], W - 140, 40, "Bold")
    pl = wrap(s["pov"], pf, W - 140)[:1]
    draw_rich(frame, (W - line_w(pl[0])) / 2 + 0, 160, pl, pf, (255, 236, 200), 48)
    card_y0 = CY0 + 64
    d.rounded_rectangle((CX0, card_y0, CX1, CY1), 30, fill=CREAM, outline=GOLD, width=6)
    d.rounded_rectangle((CX0 + 14, card_y0 + 14, CX1 - 14, CY1 - 14), 22, outline=(230, 200, 140), width=2)
    for x, y in ((CX0 + 8, card_y0 + 8), (CX1 - 56, card_y0 + 8), (CX0 + 8, CY1 - 56), (CX1 - 56, CY1 - 56)):
        comp(frame, emoji("🌼", 48), x, y)
    pg = [p for p in st["pages"] if p["t"] <= t]
    if not pg:
        return
    p = pg[-1]
    age = t - p["t"]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    hf = font(28, "Semibold")
    head = "|| shree ganeshaya namah ||"
    ld.text((MID - hf.getlength(head) / 2, card_y0 + 34), head, font=hf, fill=MAROON)
    # photo
    ph = [x for x in p["photos"] if x["t"] <= t][-1]
    py = card_y0 + 84
    sq = ph["bg"].copy()
    cat = ph["cat"].at(t - ph["t"])
    sc = PHOTO_D * 0.95 / cat.height
    c = cat.resize((max(1, int(cat.width * sc)), max(1, int(cat.height * sc))), Image.BILINEAR)
    comp(sq, c, (PHOTO_D - c.width) / 2, PHOTO_D - c.height + 6)
    sq.putalpha(circle_mask(PHOTO_D))
    ld.ellipse((MID - PHOTO_D / 2 - 10, py - 10, MID + PHOTO_D / 2 + 10, py + PHOTO_D + 10), fill=GOLD)
    if ph is not p["photos"][0] and t - ph["t"] < 0.3:
        k = ease_out_back((t - ph["t"]) / 0.3)
        sq = sq.resize((max(1, int(PHOTO_D * k)), max(1, int(PHOTO_D * k))), Image.BILINEAR)
    comp(layer, sq, MID - sq.width / 2, py + (PHOTO_D - sq.height) / 2)
    lab = ph.get("label", "")
    if lab:
        lf = font(26, "Semibold")
        lw = lf.getlength(lab) + 36
        ld.rounded_rectangle((MID - lw / 2, py + PHOTO_D - 8, MID + lw / 2, py + PHOTO_D + 34), 20, fill=MAROON)
        ld.text((MID - lw / 2 + 18, py + PHOTO_D - 3), lab, font=lf, fill=(255, 255, 255))
    y = py + PHOTO_D + 56
    for ln in p["lines"]:
        if t < ln["t"]:
            break
        im = line_img(ln)
        a = ease((t - ln["t"]) / 0.45)
        im.putalpha(im.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(layer, im, MID - im.width / 2, y + (1 - a) * 16)
        y += im.height + 24
    q = p.get("qr")
    if q and t >= q["t"]:
        k = ease_out_back(min(1, (t - q["t"]) / 0.4))
        qr = qr_image(q["text"], 300)
        qs = max(1, int(qr.width * k))
        qr = qr.resize((qs, qs), Image.NEAREST)
        comp(layer, qr, MID - qs / 2, y + (qr_image(q["text"], 300).height - qs) / 2)
        tf = fit_font(q["text"], 740, 32, "Bold")
        ty = y + 334
        if t >= q["t"] + 0.4:
            ld.text((MID - tf.getlength(q["text"]) / 2, ty), q["text"], font=tf, fill=MAROON)
    a = min(1, age / 0.35, (p["t1"] - t) / 0.3) if p is not st["pages"][-1] else min(1, age / 0.35)
    if a < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v, a=a: int(v * a)))
    frame.alpha_composite(layer)


PLAN, DRAW = plan, draw
