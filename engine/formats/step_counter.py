"""step_counter: a fitness app's family challenge. Two activity rings (Mummy and
you) count up as the day's activity log comes in, a result card lands, and the
last two log lines carry the joke. Each person has a live cat cam below.

Script: `challenge`, `goal`, `people` {id: {name, color}}, `cams` {id: [{t, clip,
start, dur, bg}]}, `events` [{t, who, time, text, steps} | {t, result} | {t, end}].
Laid out inside the Shorts safe zone (engine/safe_zone.py).
"""
import math
from PIL import Image, ImageDraw

from simple_render import Cat, cat_window, window_bg, name_chip, fit_font, ease, tick, ding, tone, W, H
from chat_render import font, emoji, wrap, draw_rich, line_w, comp, ease_out_back

BG = (14, 14, 18)
L, R = 60, 1020                                   # safe x range above the rail
RING_Y, RING_R, RING_W = 545, 150, 30
CAM_Y, CAM_H = 1000, 410
CAMS_X = {0: (60, 400), 1: (480, 400)}            # two cams side by side, clear of the rail at x 900


def fmt(n):
    return f"{n:,}"


def PLAN(s, slug):
    track, cams = [], {}
    end_t = next(e["t"] for e in s["events"] if e.get("end"))
    for pid, lst in s["cams"].items():
        cams[pid] = []
        for i, c in enumerate(lst):
            t1 = lst[i + 1]["t"] if i + 1 < len(lst) else end_t
            cat = Cat(slug, f"{pid}{i}", c["clip"], c["start"], min(c.get("dur", 99), t1 - c["t"] + 0.2), 520)
            cams[pid].append(dict(c, cat=cat, bg=window_bg(c.get("bg", "home.jpg"), 400, CAM_H, blur=4)))
            track.append((c["t"] + 0.05, cat.audio(min(cat.dur, 3.5)) * c.get("vol", 0.8)))
    totals, logs = {pid: [(0.0, 0, 0)] for pid in s["people"]}, []
    for e in s["events"]:
        if "steps" in e:
            prev = totals[e["who"]][-1][2]
            totals[e["who"]].append((e["t"] + 0.3, prev, prev + e["steps"]))
            logs.append(e)
            track.append((e["t"], ding() * 1.5))
            n = 10 if e["steps"] > 500 else 3
            for k in range(n):
                track.append((e["t"] + 0.3 + k * 0.07, tick() * 2.5))
        if "result" in e:
            track.append((e["t"], tone(392, 196, 0.5, 0.3, 4)))
    return {"cams": cams, "totals": totals, "logs": logs,
            "result": next((e for e in s["events"] if "result" in e), None)}, track, end_t


def steps_at(P, pid, t):
    t0, a, b = [x for x in P["totals"][pid] if x[0] <= t][-1]
    return int(a + (b - a) * ease((t - t0) / 0.8))


def ring(d, cx, cy, frac, col):
    dim = tuple(int(c * 0.25) for c in col)
    box = (cx - RING_R, cy - RING_R, cx + RING_R, cy + RING_R)
    d.ellipse(box, outline=dim, width=RING_W)
    laps = int(frac)
    if laps:
        d.ellipse(box, outline=col, width=RING_W)
        shade = tuple(int(c * 0.8) for c in col)
        if frac - laps > 0.002:
            d.arc(box, -90, -90 + 360 * (frac - laps), fill=shade, width=RING_W)
    elif frac > 0.002:
        d.arc(box, -90, -90 + 360 * frac, fill=col, width=RING_W)


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    pf = fit_font(s["pov"], R - L - 20, 44, "Bold")
    y = 165
    for ln in wrap(s["pov"], pf, R - L - 20):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, (255, 255, 255), 56); y += 56
    # challenge banner
    d.rounded_rectangle((L, 240, R, 330), 24, fill=(38, 38, 44))
    cf = font(34, "Semibold")
    ln = wrap(s["challenge"], cf, R - L - 60)[:1]
    draw_rich(frame, L + 30, 262, ln, cf, (255, 214, 10), 44)
    # rings
    for i, (pid, p) in enumerate(s["people"].items()):
        cx = 290 if i == 0 else 790
        n = steps_at(P, pid, t)
        ring(d, cx, RING_Y, n / s["goal"], tuple(p["color"]))
        nf = fit_font(fmt(n), RING_R * 2 - 70, 64, "Bold")
        d.text((cx - nf.getlength(fmt(n)) / 2, RING_Y - 52), fmt(n), font=nf, fill=(255, 255, 255))
        sf = font(28)
        d.text((cx - sf.getlength("steps") / 2, RING_Y + 22), "steps", font=sf, fill=(150, 150, 158))
        lf = font(36, "Semibold")
        d.text((cx - lf.getlength(p["name"]) / 2, RING_Y + RING_R + 14), p["name"], font=lf, fill=tuple(p["color"]))
    # activity log, newest first
    shown = [e for e in P["logs"] if e["t"] <= t][::-1][:3]
    ly = 780
    for k, e in enumerate(shown):
        a = ease((t - e["t"]) / 0.3)
        f = font(31, "Semibold" if k == 0 else "Regular")
        col = (255, 255, 255) if k == 0 else (150, 150, 158)
        txt = f"{e['time']} · {e['text']}"
        layer = Image.new("RGBA", (R - L, 66), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse((0, 14, 20, 34), fill=tuple(s["people"][e["who"]]["color"]))
        stx = f"+{fmt(e['steps'])}" if e["steps"] else "0 steps"
        sf = font(31, "Bold")
        sw = sf.getlength(stx)
        draw_rich(layer, 36, 4, wrap(txt, fit_font(txt, R - L - sw - 70, 31, "Semibold" if k == 0 else "Regular"), 9999)[:1],
                  fit_font(txt, R - L - sw - 70, 31, "Semibold" if k == 0 else "Regular"), col, 40)
        ld.text((R - L - sw, 4), stx, font=sf, fill=tuple(s["people"][e["who"]]["color"]))
        layer.putalpha(layer.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, layer, L, ly + (1 - a) * 16)
        ly += 70
    # cams
    for i, pid in enumerate(s["people"]):
        cur = [c for c in P["cams"][pid] if c["t"] <= t][-1]
        x, w = CAMS_X[i]
        win = cat_window(cur["bg"], cur["cat"].at(t - cur["t"], loop=cur.get("loop", False)), w, CAM_H,
                         fit=cur.get("fit", 0.85), r=32)
        comp(frame, win, x, CAM_Y)
        comp(frame, name_chip(cur.get("label", s["people"][pid]["name"]), size=28), x + 18, CAM_Y + 18)
    # result card over the rings
    rs = P["result"]
    if rs and t >= rs["t"]:
        r = rs["result"]
        k = ease_out_back(min(1, (t - rs["t"]) / 0.4))
        card = Image.new("RGBA", (R - L - 40, 330), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, card.width - 1, 329), 36, fill=(250, 250, 252))
        cd.text((40, 30), r["title"], font=font(34, "Semibold"), fill=(120, 120, 128))
        hf = font(58, "Bold")
        cd.text((40, 82), r["headline"], font=fit_font(r["headline"], card.width - 80, 58, "Bold"), fill=(226, 40, 60))
        bf = font(40, "Semibold")
        draw_rich(card, 40, 180, wrap(r["body"], bf, card.width - 80)[:2], bf, (24, 24, 28), 52)
        sc = 0.7 + 0.3 * k
        card = card.resize((int(card.width * sc), int(card.height * sc)), Image.BILINEAR)
        comp(frame, card, (W - card.width) / 2, 390 + (1 - sc) * 160)
