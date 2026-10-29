"""Departures board: an airport split-flap board while someone waits. The board
flips to each new state (changed characters spin, with a clatter), the clock
jumps, and the waiting person's latest message sits under it. A cat below.

Script: `columns` ([[label, width], ...]), `events` ({gap, clock?, board?:
[[cells...], ...], msg?: {from, text}}) and `cats` ({at, clip, start, dur?,
loop?, fit?, bg, who}). Layout stays inside engine/safe_zone.py.
"""
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from chat_render import W, H, SR, font, emoji, comp, wrap, draw_rich, line_w, tone, ease_out_back
from simple_render import Cat, cat_window, window_bg, name_chip, ease, status_bar, ding, noise

BG = (10, 12, 18)
AMBER, DIM, INK, GREY = (255, 196, 40), (120, 124, 136), (236, 238, 242), (138, 144, 158)
X0, X1 = 60, 1020
BOARD_Y, ROW_H, CW, CH = 380, 66, 24, 52
GAP = 18
CAT_X, CAT_Y, CAT_W, CAT_H = 60, 1004, 840, 406
FLIP = 0.7
MONO = "/System/Library/Fonts/Menlo.ttc"
_MF = ImageFont.truetype(MONO, 36, index=1)
_GLYPH = {}
ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:"


def glyph(ch, col):
    k = (ch, col)
    if k not in _GLYPH:
        im = Image.new("RGBA", (CW - 2, CH), (30, 32, 40, 255))
        d = ImageDraw.Draw(im)
        d.line((0, CH // 2, CW, CH // 2), fill=(10, 10, 14), width=2)
        if ch.strip():
            d.text(((CW - 2 - _MF.getlength(ch)) / 2, 5), ch, font=_MF, fill=col)
        _GLYPH[k] = im
    return _GLYPH[k]


def clatter(dur):
    a = np.zeros((int(dur * SR), 2), dtype=np.float32)
    rng = np.random.default_rng(5)
    for i in range(int(dur * 40)):
        i0 = int((i / 40 + rng.uniform(0, 0.02)) * SR)
        n = int(0.006 * SR)
        if i0 + n < len(a):
            a[i0:i0 + n] += (rng.standard_normal((n, 1)) * 0.10 * np.exp(-np.arange(n) / SR * 900)[:, None]).astype(np.float32)
    return a


def chime():
    return np.concatenate([tone(784, 784, 0.45, 0.16, 4), tone(622, 622, 0.7, 0.16, 3)])


def fmt_row(cells, widths):
    return "".join(c.upper().ljust(w)[:w] for c, w in zip(cells, widths))


def PLAN(s, slug):
    widths = [w for _, w in s["columns"]]
    t, track, evs = 1.0, [], []
    board = None
    for e in s["events"]:
        t += e.get("gap", 3.6)
        e = dict(e, t=t)
        if "board" in e:
            new = [fmt_row(r, widths) for r in e["board"]]
            e["old"] = board or [" " * sum(widths)] * len(new)
            e["rows"] = new
            board = new
            track.append((t, clatter(FLIP)))
        if e.get("msg"):
            track.append((t + (FLIP if "board" in e else 0) + 0.1, ding() * 0.6))
        if e.get("chime"):
            track.append((t, chime()))
        evs.append(e)
    end_t = t + s.get("hold", 4.2)
    marks = [e["t"] for e in evs]
    cats = []
    for i, c in enumerate(s["cats"]):
        t0 = 0.0 if c["at"] < 0 else marks[c["at"]]
        t1 = end_t if i + 1 == len(s["cats"]) else marks[s["cats"][i + 1]["at"]]
        cat = Cat(slug, f"cat{i:02d}", c["clip"], c["start"], c.get("dur", t1 - t0 + 0.2), CAT_H)
        cats.append(dict(c, t0=t0, t1=t1, cat=cat, bg=window_bg(c.get("bg", "airport.jpg"), CAT_W, CAT_H),
                         chip=name_chip(c.get("who", "papa"))))
        if c.get("loop"):
            k = t0
            while k < t1 - 0.5:
                track.append((k + 0.1, cat.audio(min(cat.dur, t1 - k)) * 0.8)); k += 2 * cat.dur + 1.2
        else:
            track.append((t0 + 0.1, cat.audio(min(cat.dur, t1 - t0))))
    return dict(evs=evs, cats=cats, widths=widths), track, end_t


def bubble(m):
    bf = font(38)
    lines = wrap(m["text"], bf, X1 - X0 - 80)[:2]
    h = 70 + 48 * len(lines)
    im = Image.new("RGBA", (X1 - X0, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, h - 1), 30, fill=(32, 44, 38))
    d.text((32, 14), m["from"], font=font(32, "Semibold"), fill=(120, 220, 160))
    draw_rich(im, 32, 56, lines, bf, INK, 48)
    return im


_B = {}


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    status_bar(d, s.get("clock", "5:10"), INK)
    pf = font(46, "Bold")
    y = 162
    for ln in wrap(s["pov"], pf, X1 - X0 - 40):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, INK, 56); y += 56
    widths = P["widths"]
    shown = [e for e in P["evs"] if e["t"] <= t]
    clock = ([e["clock"] for e in shown if e.get("clock")] or [s.get("start_clock", "05:10")])[-1]
    # board frame
    d.rounded_rectangle((X0, 236, X1, 800), 26, fill=(22, 24, 32))
    comp(frame, emoji("🛫", 46), X0 + 28, 256)
    d.text((X0 + 88, 254), "DEPARTURES", font=font(44, "Heavy"), fill=AMBER)
    cf = font(52, "Bold")
    d.text((X1 - 30 - cf.getlength(clock), 248), clock, font=cf, fill=INK)
    x = X0 + (X1 - X0 - CW * sum(widths) - GAP * (len(widths) - 1)) / 2
    xs = []
    hx = x
    for (lab, w) in s["columns"]:
        d.text((hx, 330), lab, font=font(24, "Semibold"), fill=DIM)
        xs.append(hx); hx += w * CW + GAP
    bev = [e for e in shown if "board" in e]
    if bev:
        e = bev[-1]
        age = t - e["t"]
        rnd = random.Random(int(t * 30))
        for r, (old, new) in enumerate(zip(e["old"] + [""] * (len(e["rows"]) - len(e["old"])), e["rows"])):
            old = old.ljust(len(new))
            ry = BOARD_Y + r * ROW_H
            ci = 0
            for col, w in enumerate(widths):
                for k in range(w):
                    ch = new[ci]
                    if old[ci] != ch and age < FLIP * (0.5 + 0.5 * ((ci * 7 + r * 3) % 10) / 10):
                        ch = rnd.choice(ALPHA)          # still spinning
                    colr = AMBER if col == len(widths) - 1 and ch.strip() else INK
                    if new.strip().endswith(s.get("alert_word", "@@")) and col == len(widths) - 1:
                        colr = (255, 90, 80)
                    comp(frame, glyph(ch, colr), xs[col] + k * CW, ry)
                    ci += 1
    # latest message
    msgs = [e for e in shown if e.get("msg") and t >= e["t"] + (FLIP if "board" in e else 0)]
    if msgs:
        e = msgs[-1]
        key = id(e)
        if key not in _B:
            _B[key] = bubble(e["msg"])
        im = _B[key]
        t0 = e["t"] + (FLIP if "board" in e else 0)
        k = ease_out_back(min(1, (t - t0) / 0.35))
        comp(frame, im, X0, 814 + (1 - k) * 30)
    cur = [c for c in P["cats"] if c["t0"] <= t][-1]
    win = cat_window(cur["bg"], cur["cat"].at(t - cur["t0"], loop=cur.get("loop", False)), CAT_W, CAT_H,
                     fit=cur.get("fit", 0.92))
    comp(frame, win, CAT_X, CAT_Y)
    comp(frame, cur["chip"], CAT_X + 24, CAT_Y + 22)
