"""delivery_tracking: a food app's live-tracking screen. A drawn street map with
the rider's scooter moving between road junctions (wrong turns, loops, a chai
stop), an ETA card that refuses to change, a status feed, the rider's calls as
full-screen popups, and the rider (a cat) in a window in the bottom sheet.

Script: `path` = rider keyframes [t, node], node names from NODES; `events` with
any of eta / status / clock / call / cancel / you; see data/formats/*.json.
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw

from simple_render import (Cat, cat_window, window_bg, name_chip, fit_font, ease, tick, tone, ring,
                           ding, W, H, SR, circle_mask)
from chat_render import font, emoji, wrap, draw_rich, line_w, comp, ease_out_back

BG = (236, 232, 222)
MAP_H = 1040
XS, YS = [140, 400, 660, 920], [540, 740, 940]             # road grid, inside the Shorts safe zone
SHEET_Y, SAFE_B, RAIL_X = 990, 1410, 900                    # engine/safe_zone.py
NODES = {f"{c}{r}": (x, y) for c, x in zip("abcd", XS) for r, y in zip("123", YS)}
INK, GREY, GREEN, RED = (28, 28, 30), (110, 110, 118), (0, 150, 80), (226, 55, 68)


def draw_map(s):
    im = Image.new("RGBA", (W, MAP_H), BG + (255,))
    d = ImageDraw.Draw(im)
    for i in range(len(XS) + 1):                           # building blocks between roads
        for j in range(len(YS) + 1):
            x0 = (XS[i - 1] if i else -200) + 34
            x1 = (XS[i] if i < len(XS) else W + 200) - 34
            y0 = (YS[j - 1] if j else 200) + 34
            y1 = (YS[j] if j < len(YS) else MAP_H + 200) - 34
            col = (200, 228, 190) if (i + j) % 4 == 1 else (222, 218, 208)
            d.rounded_rectangle((x0, y0, x1, y1), 18, fill=col)
    for x in XS:
        d.line((x, 200, x, MAP_H), fill=(255, 255, 255), width=46)
    for y in YS:
        d.line((0, y, W, y), fill=(255, 255, 255), width=46)
    lf = font(26, "Semibold")
    for name, (x, y, rot) in s.get("road_names", {}).items():
        t = Image.new("RGBA", (int(lf.getlength(name)) + 10, 34), (0, 0, 0, 0))
        ImageDraw.Draw(t).text((5, 0), name, font=lf, fill=(150, 146, 136))
        if rot:
            t = t.rotate(90, expand=True)
        comp(im, t, x, y)
    route = [NODES[n] for n in s["route"]]                 # the route the app promised
    d.line(route, fill=(30, 160, 90), width=14, joint="curve")
    return im


def pin(em, col, size=96):
    im = Image.new("RGBA", (size + 12, size + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((6, 10, size + 6, size + 10), fill=(0, 0, 0, 40))
    d.ellipse((0, 0, size, size), fill=(255, 255, 255), outline=col, width=6)
    d.polygon([(size / 2 - 14, size - 8), (size / 2 + 14, size - 8), (size / 2, size + 22)], fill=col)
    comp(im, emoji(em, int(size * 0.56)), size * 0.22, size * 0.2)
    return im


def rider_pos(t, path):
    if t <= path[0][0]:
        return NODES[path[0][1]]
    for (t0, n0), (t1, n1) in zip(path, path[1:]):
        if t0 <= t < t1:
            k = (t - t0) / (t1 - t0)
            k = k * k * (3 - 2 * k)
            (x0, y0), (x1, y1) = NODES[n0], NODES[n1]
            return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
    return NODES[path[-1][1]]


def scooter_hum(dur):
    n = int(dur * SR); x = np.arange(n) / SR
    w = (np.sin(2 * np.pi * 95 * x) * 0.6 + np.sin(2 * np.pi * 190 * x) * 0.3) * 0.03
    w *= 0.7 + 0.3 * np.sin(2 * np.pi * 3 * x)
    return np.repeat(w[:, None], 2, axis=1).astype(np.float32)


def PLAN(s, slug):
    evs, track = s["events"], []
    end_t = next(e["t"] for e in evs if e.get("end"))
    rd = s["rider"]
    P = {"map": draw_map(s), "evs": [e for e in evs if not e.get("end")],
         "rider": Cat(slug, "rider", rd["clip"], rd["start"], rd["dur"], 400),
         "rider_bg": window_bg(rd.get("bg", "highway.jpg"), 380, 400, blur=4),
         "calls": [], "you": None, "pins": {"home": pin("🏠", (30, 160, 90)), "food": pin("🍗", RED),
                                             "chai": pin("☕", (150, 100, 50), 84)}}
    for i, e in enumerate(evs):
        if "status" in e:
            track.append((e["t"], tick() * 2))
        if "call" in e:
            c = dict(e["call"], t=e["t"])
            c["cat"] = Cat(slug, f"call{i:02d}", c["clip"], c["start"], c["until"] - e["t"], 440)
            c["bg"] = window_bg(c.get("bg", "highway.jpg"), 440, 440, blur=3)
            P["calls"].append(c)
            track.append((e["t"], ring(c["until"] - e["t"]) * 0.8))
            track.append((e["t"] + 0.3, c["cat"].audio(min(c["cat"].dur, c["until"] - e["t"] - 0.4))))
            track.append((c["until"] - 0.05, tone(500, 300, 0.15, 0.25, 12)))
        if "you" in e:
            y = e["you"]
            P["you"] = dict(y, t=e["t"], cat=Cat(slug, "you", y["clip"], y["start"], y["dur"], 400),
                            bg=window_bg(y.get("bg", "home.jpg"), 380, 400, blur=4))
            track.append((e["t"], P["you"]["cat"].audio()))
        if "cancel" in e:
            track.append((e["t"], tone(660, 330, 0.35, 0.3, 5)))
    for (t0, n0), (t1, n1) in zip(s["path"], s["path"][1:]):
        if n0 != n1:
            track.append((t0, scooter_hum(t1 - t0)))
    return P, track, end_t


def latest(P, t, key):
    v = None
    for e in P["evs"]:
        if e["t"] <= t and key in e:
            v = e
    return v


def DRAW(frame, t, s, P):
    comp(frame, P["map"], 0, 0)
    for name, key in (("food", s["restaurant"]), ("home", s["home"])) + tuple(("chai", c) for c in s.get("chai", [])):
        x, y = NODES[key]
        p = P["pins"][name]
        comp(frame, p, x - p.width / 2 + 6, y - p.height + 8)
    x, y = rider_pos(t, s["path"])
    bob = math.sin(t * 9) * 3
    d = ImageDraw.Draw(frame)
    d.ellipse((x - 46, y - 46 + bob, x + 46, y + 46 + bob), fill=(255, 255, 255), outline=INK, width=4)
    comp(frame, emoji("🛵", 60), x - 30, y - 30 + bob)

    # top: pov pill + ETA card
    pf = fit_font(s["pov"], W - 140, 42, "Bold")
    if pf.size < 36:
        pf = font(42, "Bold")
    lines = wrap(s["pov"], pf, W - 140)
    ph = 34 + 52 * len(lines)
    d.rounded_rectangle((60, 160, W - 60, 160 + ph), 30, fill=(20, 20, 24, 235))
    yy = 176
    for ln in lines:
        draw_rich(frame, (W - line_w(ln)) / 2, yy, [ln], pf, (255, 255, 255), 52); yy += 52
    eta = latest(P, t, "eta")
    ce = latest(P, t, "clock")
    cy = 175 + ph
    d.rounded_rectangle((60, cy + 4, W - 60, cy + 150), 30, fill=(0, 0, 0, 30))
    d.rounded_rectangle((60, cy, W - 60, cy + 146), 30, fill=(255, 255, 255))
    ef = font(54, "Bold")
    etxt = eta["eta"] if eta else ""
    col = RED if eta and eta.get("red") else GREEN
    if eta and t - eta["t"] < 0.4:                          # ETA pops when it changes
        k = ease_out_back((t - eta["t"]) / 0.4); ef = font(int(54 * (0.8 + 0.2 * k)), "Bold")
    d.text((96, cy + 22), etxt, font=ef, fill=col)
    d.text((96, cy + 92), s["order"], font=fit_font(s["order"], W - 360, 32), fill=GREY)
    if ce:
        cf = font(34, "Semibold")
        d.text((W - 96 - cf.getlength(ce["clock"]), cy + 30), ce["clock"], font=cf, fill=INK)

    # bottom sheet: rider window + status feed
    sy = SHEET_Y
    d.rounded_rectangle((0, sy, W, H + 40), 44, fill=(255, 255, 255))
    d.rounded_rectangle((W / 2 - 60, sy + 14, W / 2 + 60, sy + 22), 4, fill=(210, 210, 214))
    you = P["you"] if P["you"] and t >= P["you"]["t"] else None
    if you:
        win = cat_window(you["bg"], you["cat"].at(t - you["t"]), 380, 400, fit=0.9, r=32)
        chip = name_chip(you["label"], size=28)
    else:
        win = cat_window(P["rider_bg"], P["rider"].at(t, loop=True), 380, 400, fit=0.8, r=32)
        chip = name_chip(s["rider"]["label"], size=28)
    comp(frame, win, 60, sy + 20)
    comp(frame, chip, 76, sy + 36)
    feed = [e for e in P["evs"] if e["t"] <= t and "status" in e][::-1]
    fx = 470
    fy = sy + 20
    d.text((fx, fy), "updates", font=font(30, "Bold"), fill=GREY)
    fy += 48
    for k, e in enumerate(feed[:4]):
        f = font(32, "Semibold" if k == 0 else "Regular")
        ls = wrap(e["status"], f, RAIL_X - fx - 50)[:2]
        a = ease((t - e["t"]) / 0.3) if k == 0 else 1
        col = INK if k == 0 else (150, 150, 156)
        layer = Image.new("RGBA", (RAIL_X - fx, 46 * len(ls) + 36), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse((0, 12, 18, 30), fill=GREEN if k == 0 else (200, 200, 204))
        draw_rich(layer, 34, 0, ls, f, col, 46)
        ld.text((34, 46 * len(ls)), e.get("clock_tag", ""), font=font(26), fill=(160, 160, 166))
        layer.putalpha(layer.getchannel("A").point(lambda v, a=a: int(v * a)))
        if fy + layer.height > SAFE_B:
            break
        comp(frame, layer, fx, fy)
        fy += layer.height + 4

    for c in P["calls"]:
        if c["t"] <= t < c["until"]:
            draw_call(frame, t, c)
    ce = latest(P, t, "cancel")
    if ce:
        draw_cancel(frame, t - ce["t"], ce["cancel"])


def draw_call(frame, t, c):
    age = t - c["t"]
    a = min(1, age / 0.25, (c["until"] - t) / 0.2)
    ov = Image.new("RGBA", (W, H), (16, 16, 20, 248))
    d = ImageDraw.Draw(ov)
    d.text(((W - font(36).getlength("incoming call")) / 2, 240), "incoming call", font=font(36), fill=(170, 170, 178))
    nf = font(74, "Semibold")
    d.text(((W - nf.getlength(c["number"])) / 2, 290), c["number"], font=nf, fill=(255, 255, 255))
    wf = font(40, "Semibold")
    warn = c["warning"]
    lw = wf.getlength(warn) + 60
    d.rounded_rectangle(((W - lw) / 2, 400, (W + lw) / 2, 470), 35, fill=(120, 20, 28))
    d.text(((W - wf.getlength(warn)) / 2, 412), warn, font=wf, fill=(255, 140, 140))
    if c.get("sub"):
        sf = font(34)
        d.text(((W - sf.getlength(c["sub"])) / 2, 500), c["sub"], font=sf, fill=(170, 170, 178))
    D = 440
    sq = c["bg"].copy()
    cat = c["cat"].at(age)
    s = min(D * 0.95 / cat.height, D * 1.2 / cat.width)
    cat = cat.resize((int(cat.width * s), int(cat.height * s)), Image.BILINEAR)
    comp(sq, cat, (D - cat.width) / 2, D - cat.height + 4)
    sq.putalpha(circle_mask(D))
    pulse = 1 + 0.03 * math.sin(age * 6)
    rr = int(D / 2 * pulse) + 24
    d.ellipse((W / 2 - rr, 800 - rr, W / 2 + rr, 800 + rr), fill=(52, 199, 89, 60))
    comp(ov, sq, (W - D) / 2, 800 - D / 2)
    press = c["until"] - t < 0.45
    bf = font(34)
    for cx, col, lab in ((270, (255, 59, 48), "Decline"), (690, (52, 199, 89), "Accept")):
        r = 85 + (12 if press and lab == "Decline" else 0)
        cc = (180, 30, 24) if press and lab == "Decline" else col
        d.ellipse((cx - r, 1170 - r, cx + r, 1170 + r), fill=cc)
        comp(ov, emoji("📞", 80), cx - 40, 1130)
        d.text((cx - bf.getlength(lab) / 2, 1280), lab, font=bf, fill=(255, 255, 255))
    ov.putalpha(ov.getchannel("A").point(lambda v, a=a: int(v * a)))
    frame.alpha_composite(ov)


def draw_cancel(frame, age, c):
    k = ease_out_back(min(1, age / 0.4))
    cw, ch = W - 120, 400
    card = Image.new("RGBA", (cw, ch + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 12, cw - 1, ch + 11), 40, fill=(0, 0, 0, 60))
    d.rounded_rectangle((0, 0, cw - 1, ch), 40, fill=(255, 255, 255))
    d.rounded_rectangle((0, 0, cw - 1, 120), 40, fill=RED)
    d.rectangle((0, 80, cw - 1, 120), fill=RED)
    d.text((50, 30), c["title"], font=font(56, "Bold"), fill=(255, 255, 255))
    y = 150
    for i, ln in enumerate(c["lines"]):
        f = font(42, "Semibold" if i == 0 else "Regular")
        for l in wrap(ln, f, cw - 100):
            draw_rich(card, 50, y, [l], f, INK if i == 0 else GREY, 54); y += 54
        y += 14
    sc = 0.6 + 0.4 * k
    card = card.resize((int(card.width * sc), int(card.height * sc)), Image.BILINEAR)
    comp(frame, card, (W - card.width) / 2, 560 + (1 - sc) * 200)
