"""Receipt: a delivery receipt prints line by line out of a thermal printer, and
the items tell the story. A cat watches from a window below.

Script: `lines` (each {text | item+price | rule | blank}, optional `style`,
`gap` = seconds before it prints) and `cats` ({at_line, clip, start, bg, who}).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from chat_render import W, H, SR, font, comp, wrap, draw_rich, line_w
from simple_render import Cat, cat_window, window_bg, name_chip, ease, noise, ding

BG = (24, 20, 18)
MONO = "/System/Library/Fonts/Menlo.ttc"
_M = {}

PAPER_X0, PAPER_X1 = 100, 980
SLOT_Y, VIEW_TOP = 872, 244
CAT_X, CAT_Y, CAT_W, CAT_H = 60, 990, 840, 420      # inside the Shorts safe zone (engine/safe_zone.py)
LH = 58


def mono(size, bold=False):
    k = (size, bold)
    if k not in _M:
        _M[k] = ImageFont.truetype(MONO, size, index=1 if bold else 0)
    return _M[k]


def buzz():
    a = noise(0.22, 0.05, 11)
    a *= (0.6 + 0.4 * np.sign(np.sin(np.arange(len(a)) / SR * 2 * np.pi * 90)))[:, None]
    fade = int(0.02 * SR)
    a[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    return a.astype(np.float32)


def line_h(ln):
    return {"big": 88, "blank": 26, "rule": 42, "punch": 80}.get(ln.get("style") or ("rule" if ln.get("rule") else ""), LH)


def PLAN(s, slug):
    t, track, lines = 1.2, [], []
    for ln in s["lines"]:
        t += ln.get("gap", 0.9)
        lines.append(dict(ln, t=t, h=line_h(ln)))
        if not ln.get("blank"):
            track.append((t, buzz()))
    end_t = t + s.get("hold", 3.0)
    cats = []
    for i, c in enumerate(s["cats"]):
        t0 = 0.0 if c["at_line"] == 0 else lines[c["at_line"]]["t"]
        t1 = end_t if i == len(s["cats"]) - 1 else lines[s["cats"][i + 1]["at_line"]]["t"]
        cat = Cat(slug, f"cat{i:02d}", c["clip"], c["start"], c.get("dur", t1 - t0 + 0.2), CAT_H)
        cats.append(dict(c, t0=t0, t1=t1, cat=cat, bg=window_bg(c.get("bg", "home.jpg"), CAT_W, CAT_H),
                         chip=name_chip(c.get("who", "you"))))
        if c.get("loop"):                          # a short looped segment: repeat its sound too
            k = t0
            while k < t1 - 0.5:
                track.append((k + 0.05, cat.audio(min(cat.dur, t1 - k)) * 0.8)); k += 2 * cat.dur + 1.5
        else:
            track.append((t0 + 0.05, cat.audio(min(cat.dur, t1 - t0))))
        if i:
            track.append((t0, ding() * 0.5))
    wall = window_bg(s.get("bg", "restaurant.jpg"), W, H, blur=10, dim=0.55)
    return dict(lines=lines, cats=cats, wall=wall), track, end_t


def draw_line(paper, ln, y):
    d = ImageDraw.Draw(paper)
    w = paper.width
    st = ln.get("style")
    if ln.get("rule"):
        d.text((30, y + 4), "-" * 36, font=mono(37), fill=(70, 70, 70))
        return
    if ln.get("blank"):
        return
    if st == "big":
        f = mono(64, True)
        d.text(((w - f.getlength(ln["text"])) / 2, y + 6), ln["text"], font=f, fill=(20, 20, 20))
        return
    if st == "punch":
        f = mono(56, True)
        d.text(((w - f.getlength(ln["text"])) / 2, y + 10), ln["text"], font=f, fill=(20, 20, 20))
        return
    f = mono(38, st == "bold")
    if "price" in ln:
        d.text((30, y + 6), ln["item"], font=f, fill=(20, 20, 20))
        p = ln["price"]
        d.text((w - 30 - f.getlength(p), y + 6), p, font=f, fill=(20, 20, 20))
    else:
        col = (110, 110, 110) if st == "note" else (20, 20, 20)
        x = 30 if st != "center" else (w - f.getlength(ln["text"])) / 2
        d.text((x, y + 6), ln["text"], font=f, fill=col)


def DRAW(frame, t, s, P):
    frame.alpha_composite(P["wall"])
    d = ImageDraw.Draw(frame)
    # paper: everything printed so far, the newest line just above the slot
    shown = [ln for ln in P["lines"] if ln["t"] <= t]
    pw = PAPER_X1 - PAPER_X0
    fed = 40 + sum(ln["h"] for ln in shown)
    if shown:                                    # the newest line feeds out over 0.25s
        last = shown[-1]
        fed -= last["h"] * (1 - ease((t - last["t"]) / 0.25))
    vis_h = SLOT_Y - VIEW_TOP
    ph = int(min(fed, vis_h + 400)) + 1
    paper = Image.new("RGBA", (pw, ph), (250, 248, 240, 255))
    # draw lines bottom-up so the newest sits at the bottom of the paper strip
    y = ph - 20
    for ln in reversed(shown):
        y -= ln["h"]
        if y + ln["h"] < 0:
            break
        draw_line(paper, ln, y)
    if fed < vis_h + 400:                        # torn top edge while the head of the receipt is visible
        pd = ImageDraw.Draw(paper)
        for x in range(0, pw, 30):
            pd.polygon([(x, 0), (x + 15, 14), (x + 30, 0)], fill=(0, 0, 0, 0))
    py = SLOT_Y - ph
    if py < VIEW_TOP:
        paper = paper.crop((0, VIEW_TOP - py, pw, ph)); py = VIEW_TOP
        # fade the top so lines scroll away under the title
        a = np.asarray(paper.getchannel("A")).astype(np.float32)
        n = min(110, a.shape[0])
        a[:n] *= np.linspace(0, 1, n)[:, None]
        paper.putalpha(Image.fromarray(a.astype(np.uint8)))
    shadow = Image.new("RGBA", (pw, paper.height), (0, 0, 0, 90))
    shadow.putalpha(paper.getchannel("A").point(lambda v: int(v * 0.35)))
    comp(frame, shadow, PAPER_X0 + 10, py + 8)
    comp(frame, paper, PAPER_X0, py)
    # printer
    d.rounded_rectangle((60, SLOT_Y - 10, W - 60, SLOT_Y + 96), 30, fill=(52, 54, 60))
    d.rounded_rectangle((PAPER_X0 - 16, SLOT_Y - 6, PAPER_X1 + 16, SLOT_Y + 10), 6, fill=(18, 18, 20))
    lit = shown and t - shown[-1]["t"] < 0.3
    d.ellipse((W - 130, SLOT_Y + 36, W - 100, SLOT_Y + 66), fill=(80, 220, 120) if lit else (40, 90, 60))
    d.text((100, SLOT_Y + 34), s.get("printer", "order printer · counter 2"), font=font(30, "Medium"),
           fill=(170, 172, 180))
    # title
    pf = font(50, "Bold")
    y = 166
    for ln in wrap(s["pov"], pf, W - 140):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, (255, 255, 255), 64); y += 64
    # cat window
    cur = [c for c in P["cats"] if c["t0"] <= t][-1]
    win = cat_window(cur["bg"], cur["cat"].at(t - cur["t0"], loop=cur.get("loop", False)), CAT_W, CAT_H)
    comp(frame, win, CAT_X, CAT_Y)
    comp(frame, cur["chip"], CAT_X + 24, CAT_Y + 22)
