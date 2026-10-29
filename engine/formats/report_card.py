"""report_card: a school marksheet on the desk, revealed one row at a time. Marks
count up, the grade is stamped, anything under 40 gets circled in red pen, and
Papa (a cat, in a window below) reacts to each row with a line of his own.

Script: `school`, `exam`, `rows` [{subject, max, marks, grade, clip, start, bg,
say, who, result}] where `result: true` rows sit in the result block below the
subjects; see data/formats/*.json.
"""
import math
from PIL import Image, ImageDraw

from simple_render import (Cat, cat_window, window_bg, name_chip, fit_font, ease, tick, thunk,
                           whoosh, W, H)
from chat_render import font, emoji, wrap, draw_rich, line_w, comp, ease_out_back, cover, circle_mask

BG = (78, 54, 38)
PAPER, NAVY, PEN, INKC, GREYC = (253, 249, 236), (24, 44, 110), (210, 30, 40), (30, 30, 34), (120, 116, 104)
CARD = (60, 220, 960, 720)                       # x, y, w, h; everything inside the Shorts safe zone
WIN = (60, 1010, 820, 400)                       # clear of the like/share rail
ROW_H, ROW_Y0, RES_Y0 = 62, 416, 760
COLS = {"subject": 100, "max": 560, "marks": 700, "grade": 860}
ROW_DUR = 4.4


def PLAN(s, slug):
    track, rows = [(0.2, whoosh() * 2)], []
    t = 1.4
    for i, r in enumerate(s["rows"]):
        p = dict(r, t0=t, t1=t + r.get("dur", ROW_DUR))
        p["cat"] = Cat(slug, f"row{i:02d}", r["clip"], r["start"], p["t1"] - t + 0.5, 680)
        p["bg"] = window_bg(r.get("bg", "livingroom.jpg"), WIN[2], WIN[3], blur=5)
        track.append((t + 0.1, p["cat"].audio(min(p["cat"].dur, p["t1"] - t))))
        if isinstance(r["marks"], int):
            for k in range(8):
                track.append((t + 0.1 + k * 0.08, tick()))
        if r.get("grade"):
            track.append((t + 0.9, thunk()))
        if isinstance(r["marks"], int) and r["marks"] < 40:
            track.append((t + 1.2, whoosh()))
        rows.append(p)
        t = p["t1"]
    return {"rows": rows}, track, t + 0.3


def red_circle(d, cx, cy, rx, ry, k):
    """Hand-drawn pen loop, drawn on over k in [0, 1]."""
    pts = []
    n = int(60 * k)
    for i in range(n + 1):
        a = -math.pi / 2 + 2.15 * math.pi * i / 60
        wob = 1 + 0.06 * math.sin(i * 0.7)
        pts.append((cx + rx * wob * math.cos(a), cy + ry * wob * math.sin(a)))
    if len(pts) > 1:
        d.line(pts, fill=PEN, width=6, joint="curve")


def draw_card(frame, t, s, rows):
    x0, y0, cw, chh = CARD
    slide = ease((t - 0.0) / 0.9)
    y0 = y0 + (1 - slide) * 900
    card = Image.new("RGBA", (cw, chh), PAPER + (255,))
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, cw - 1, chh - 1), outline=(200, 190, 160), width=4)
    hf = font(46, "Bold")
    d.text(((cw - hf.getlength(s["school"])) / 2, 22), s["school"], font=hf, fill=NAVY)
    ef = font(30)
    d.text(((cw - ef.getlength(s["exam"])) / 2, 80), s["exam"], font=ef, fill=GREYC)
    d.line((40, 126, cw - 40, 126), fill=NAVY, width=3)
    bf = font(28, "Bold")
    for key, lab in (("subject", "subject"), ("max", "max"), ("marks", "marks"), ("grade", "grade")):
        d.text((COLS[key] - x0, 140), lab, font=bf, fill=NAVY)
    d.line((40, 182, cw - 40, 182), fill=(200, 190, 160), width=2)
    subj = [r for r in rows if not r.get("result")]
    res = [r for r in rows if r.get("result")]
    if res:
        d.line((40, RES_Y0 - y0 - 20 - (CARD[1] - y0), cw - 40, RES_Y0 - CARD[1] - 20), fill=NAVY, width=3)
    rf, mf = font(38), font(42, "Semibold")
    for i, r in enumerate(rows):
        if t < r["t0"]:
            continue
        ry = (ROW_Y0 + subj.index(r) * ROW_H if r in subj else RES_Y0 + res.index(r) * (ROW_H + 8)) - CARD[1]
        age = t - r["t0"]
        a = ease(age / 0.25)
        f = font(42, "Bold") if r.get("result") else rf
        d.text((COLS["subject"] - x0 - (1 - a) * 20, ry), r["subject"], font=f, fill=INKC)
        if r.get("max"):
            d.text((COLS["max"] - x0, ry), str(r["max"]), font=rf, fill=GREYC)
        m = r["marks"]
        if isinstance(m, int):
            shown = int(m * ease((age - 0.1) / 0.65)) if age > 0.1 else 0
            d.text((COLS["marks"] - x0, ry - 2), str(shown), font=mf, fill=PEN if m < 40 and age > 0.8 else INKC)
            if m < 40 and age > 1.2:
                red_circle(d, COLS["marks"] - x0 + 26, ry + 24, 56, 32, min(1, (age - 1.2) / 0.5))
        elif age > 0.3:
            lf = font(50, "Bold")
            draw_rich(card, COLS["marks"] - x0, ry - 6, wrap(m, lf, 300), lf, PEN if r.get("red") else NAVY, 56)
        g = r.get("grade")
        if g and age > 0.9:
            k = ease_out_back(min(1, (age - 0.9) / 0.25))
            gf = font(int(46 * (1.6 - 0.6 * k)), "Bold")
            col = PEN if g in ("D", "E", "F") else NAVY
            gw = gf.getlength(g)
            d.text((COLS["grade"] - x0 + 30 - gw / 2, ry + 22 - gf.size * 0.6), g, font=gf, fill=col)
        d.line((40, ry + ROW_H - 8, cw - 40, ry + ROW_H - 8), fill=(232, 224, 200), width=2)
    sh = Image.new("RGBA", (cw + 30, chh + 30), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle((14, 18, cw + 14, chh + 18), fill=(0, 0, 0, 70))
    comp(frame, sh, x0, y0)
    comp(frame, card, x0, y0)


def DRAW(frame, t, s, P):
    rows = P["rows"]
    pf = fit_font(s["pov"], W - 160, 44, "Bold")
    lines = wrap(s["pov"], pf, W - 160)
    y = 162
    for ln in lines:
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, (255, 255, 255), 58); y += 58
    draw_card(frame, t, s, rows)
    cur = next((r for r in rows if r["t0"] <= t < r["t1"]), rows[0] if t < rows[0]["t0"] else rows[-1])
    age = max(0.0, t - cur["t0"])
    x, wy, w, h = WIN
    if cur.get("circle"):                                  # big-face clips with cut sides: frame them round
        D = h - 20
        sq = cover(cur["bg"], D, D)
        cat = cur["cat"].at(age)
        sc = max(D * cur.get("fit", 0.9) / cat.height, D * 1.04 / cat.width)   # fill the circle edge to edge
        cat = cat.resize((int(cat.width * sc), int(cat.height * sc)), Image.BILINEAR)
        comp(sq, cat, (D - cat.width) / 2, D - cat.height + 4)
        sq.putalpha(circle_mask(D))
        ImageDraw.Draw(frame).ellipse((x + (w - D) / 2 - 8, wy + 2, x + (w + D) / 2 + 8, wy + D + 18), fill=(255, 255, 255))
        comp(frame, sq, x + (w - D) / 2, wy + 10)
    else:
        win = cat_window(cur["bg"], cur["cat"].at(age), w, h, fit=cur.get("fit", 0.9))
        comp(frame, win, x, wy)
    comp(frame, name_chip(cur.get("who", "papa")), x + 30, wy + 30)
    say = cur.get("say")
    if say and t >= cur["t0"] + 1.4:
        k = ease_out_back(min(1, (t - cur["t0"] - 1.4) / 0.3))
        sf = font(38, "Semibold")
        ls = wrap(say, sf, 460)
        bw = max(line_w(l) for l in ls) + 56
        bh = 52 * len(ls) + 40
        b = Image.new("RGBA", (int(bw), int(bh) + 26), (0, 0, 0, 0))
        bd = ImageDraw.Draw(b)
        bd.rounded_rectangle((0, 0, bw - 1, bh), 30, fill=(255, 255, 255, 245))
        bd.polygon([(40, bh - 2), (80, bh - 2), (34, bh + 24)], fill=(255, 255, 255, 245))
        draw_rich(b, 28, 20, ls, sf, INKC, 52)
        sc = 0.7 + 0.3 * k
        b = b.resize((max(1, int(b.width * sc)), max(1, int(b.height * sc))), Image.BILINEAR)
        comp(frame, b, x + w - b.width - 24, wy + 24)
