"""cricket_scorecard: a live scorecard for a society cricket final. Score, target
and "need X off Y" at the top, this over's balls as circles, ball-by-ball
commentary underneath, a rules card, and a cat cam that cuts to whoever the
ball is about. Big FOUR / SIX / OUT flashes over the cam.

Script: `match`, `batting`, `target`, `start_score`, `start_need`, `over_so_far`,
`rules`, `events` [{t, ball, over, text, score, need, flash, cam} |
{t, rules, highlight, until} | {t, retcon, ball, text, score, need, flash} | {t, end}].
Laid out inside the Shorts safe zone (engine/safe_zone.py).
"""
import numpy as np
from PIL import Image, ImageDraw

from simple_render import (Cat, cat_window, window_bg, name_chip, fit_font, ease, tone, noise, lowpass,
                           whoosh, W, H, SR)
from chat_render import font, emoji, wrap, draw_rich, line_w, comp, ease_out_back

BG = (12, 24, 52)
L, R = 60, 1020
CAM = (60, 1000, 820, 410)
BALL_COL = {"4": (30, 120, 255), "6": (150, 60, 220), "W": (226, 40, 50), "wd": (240, 150, 20),
            "0": (90, 96, 110), "db": (60, 66, 80), "1": (40, 160, 90)}
CARD, INK, MUTED = (24, 40, 80), (255, 255, 255), (160, 172, 200)


def crack():
    a = noise(0.05, 0.6, 5) * np.exp(-np.arange(int(0.05 * SR)) / SR * 90)[:, None]
    return a + tone(1900, 900, 0.05, 0.2, 60)


def cheer(dur=2.2, vol=0.35):
    a = lowpass(noise(dur, vol, 11), 6)
    env = np.minimum(1, np.linspace(0, 4, len(a))) * np.linspace(1, 0.2, len(a))
    return (a * env[:, None]).astype(np.float32)


def PLAN(s, slug):
    track, cams, balls = [], [], []
    evs = s["events"]
    end_t = next(e["t"] for e in evs if e.get("end"))
    cam_evs = [e for e in evs if "cam" in e]
    for i, e in enumerate(cam_evs):
        c = e["cam"]
        t1 = cam_evs[i + 1]["t"] if i + 1 < len(cam_evs) else end_t
        cat = Cat(slug, f"cam{i:02d}", c["clip"], c["start"], min(c.get("dur", 99), t1 - e["t"] + 0.2), 520)
        cams.append(dict(c, t=e["t"], cat=cat, bg=window_bg(c.get("bg", "playground.jpg"), CAM[2], CAM[3], blur=4)))
        track.append((e["t"] + 0.1, cat.audio(min(cat.dur, t1 - e["t"] - 0.1, 4.0)) * c.get("vol", 0.85)))
    for e in evs:
        b = e.get("ball")
        if b and not e.get("retcon"):
            track.append((e["t"], crack() if b in ("4", "6", "1") else whoosh() * 0.6))
        if b in ("4", "6") and not e.get("retcon"):
            track.append((e["t"] + 0.15, cheer(2.6 if b == "6" else 1.8)))
        if e.get("retcon"):
            track.append((e["t"], tone(330, 110, 0.7, 0.35, 3)))
        if e.get("rules"):
            track.append((e["t"], tone(880, 880, 0.08, 0.15, 30)))
    return {"cams": cams, "evs": [e for e in evs if not e.get("end")]}, track, end_t


def last(P, t, key):
    v = None
    for e in P["evs"]:
        if e["t"] <= t and key in e:
            v = e
    return v


def ball_circle(b, d=74):
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse((0, 0, d - 1, d - 1), fill=BALL_COL.get(b, (90, 96, 110)))
    txt = "•" if b == "0" else b
    f = font(34 if len(txt) < 2 else 28, "Bold")
    dr.text(((d - f.getlength(txt)) / 2, d / 2 - f.size * 0.62), txt, font=f, fill=(255, 255, 255))
    return im


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    pf = fit_font(s["pov"], R - L - 20, 44, "Bold")
    y = 165
    for ln in wrap(s["pov"], pf, R - L - 20):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, INK, 56); y += 56

    # score card
    d.rounded_rectangle((L, 236, R, 470), 30, fill=CARD)
    d.text((L + 32, 254), s["match"], font=font(30, "Semibold"), fill=MUTED)
    lv = font(26, "Bold")
    d.rounded_rectangle((R - 130, 256, R - 32, 294), 19, fill=(226, 40, 50))
    d.text((R - 81 - lv.getlength("LIVE") / 2, 260), "LIVE", font=lv, fill=INK)
    sc = last(P, t, "score")
    score = sc["score"] if sc else s["start_score"]
    sf = font(78, "Bold")
    txt = f"{s['batting']} {score}"
    pop = 1.0
    if sc and t - sc["t"] < 0.35:
        pop = 0.85 + 0.15 * ease_out_back((t - sc["t"]) / 0.35)
    f2 = font(int(78 * pop), "Bold")
    d.text((L + 32, 300), txt, font=f2, fill=INK)
    tf = font(32, "Semibold")
    tg = f"target {s['target']}"
    d.text((R - 32 - tf.getlength(tg), 330), tg, font=tf, fill=MUTED)
    nd = last(P, t, "need")
    need = nd["need"] if nd else s["start_need"]
    nf = font(42, "Bold")
    col = (255, 214, 10) if not (nd and nd.get("final")) else (255, 90, 90)
    draw_rich(frame, L + 32, 400, wrap(need, nf, R - L - 64)[:1], nf, col, 50)

    # this over
    d.text((L, 500), "this over", font=font(30, "Semibold"), fill=MUTED)
    balls = list(s.get("over_so_far", []))
    for e in P["evs"]:
        if e["t"] <= t and e.get("ball"):
            if e.get("retcon"):
                balls[-1] = (e["ball"], e["t"])
            else:
                balls.append((e["ball"], e["t"]))
    bx = L + 170
    for b in balls:
        b, bt = (b, -9) if isinstance(b, str) else b
        im = ball_circle(b)
        age = t - bt
        if age < 0.3:
            k = ease_out_back(age / 0.3)
            im = im.resize((max(1, int(74 * k)), max(1, int(74 * k))), Image.BILINEAR)
        comp(frame, im, bx + (74 - im.width) / 2, 486 + (74 - im.height) / 2)
        bx += 88

    # commentary, or the rules card
    rules = [e for e in P["evs"] if e.get("rules") and e["t"] <= t < e["until"]]
    if rules:
        e = rules[-1]
        a = ease((t - e["t"]) / 0.3)
        card = Image.new("RGBA", (R - L, 400), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, R - L - 1, 399), 30, fill=(250, 246, 230))
        cd.text((36, 26), s["rules"]["title"], font=font(38, "Bold"), fill=(30, 30, 34))
        ry = 92
        for i, rl in enumerate(s["rules"]["list"]):
            hl = e.get("highlight") == i
            rf = font(36, "Bold" if hl else "Regular")
            ls = wrap(f"{i + 1}. {rl}", rf, R - L - 90)
            if hl:
                cd.rounded_rectangle((20, ry - 6, R - L - 20, ry + 46 * len(ls) + 4), 14, fill=(255, 220, 90))
            draw_rich(card, 36, ry, ls, rf, (200, 30, 40) if hl else (30, 30, 34), 46)
            ry += 46 * len(ls) + 22
        card.putalpha(card.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, card, L, 590)
    else:
        feed = [e for e in P["evs"] if e["t"] <= t and e.get("text")][::-1][:3]
        fy = 596
        for k, e in enumerate(feed):
            a = ease((t - e["t"]) / 0.3) if k == 0 else 1
            f = font(36 if k == 0 else 31, "Semibold" if k == 0 else "Regular")
            ls = wrap(e["text"], f, R - L - 150)[:2]
            h = (46 if k == 0 else 40) * len(ls) + 18
            if fy + h > CAM[1] - 8:
                break
            layer = Image.new("RGBA", (R - L, h), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.text((0, 4), e.get("over", ""), font=font(30, "Bold"), fill=MUTED)
            if e.get("ball"):
                comp(layer, ball_circle(e["ball"], 44), 74, 0)
            draw_rich(layer, 140, 0, ls, f, INK if k == 0 else MUTED, 46 if k == 0 else 40)
            layer.putalpha(layer.getchannel("A").point(lambda v, a=a: int(v * a)))
            comp(frame, layer, L, fy)
            fy += h + 6

    # cat cam + flash
    cur = [c for c in P["cams"] if c["t"] <= t]
    if cur:
        c = cur[-1]
        x, wy, w, h = CAM
        win = cat_window(c["bg"], c["cat"].at(t - c["t"], loop=c.get("loop", False)), w, h, fit=c.get("fit", 0.85), r=32)
        comp(frame, win, x, wy)
        comp(frame, name_chip(c["label"], size=30), x + 20, wy + 20)
    fl = last(P, t, "flash")
    if fl and t - fl["t"] < 1.6:
        age = t - fl["t"]
        k = ease_out_back(min(1, age / 0.3))
        a = 1 if age < 1.2 else max(0, 1 - (age - 1.2) / 0.4)
        word = fl["flash"]
        f = font(int(150 * (0.6 + 0.4 * k)), "Heavy")
        lay = Image.new("RGBA", (CAM[2], 220), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        colw = BALL_COL.get({"FOUR": "4", "SIX": "6", "OUT": "W"}.get(word, "0"))
        ld.text(((CAM[2] - f.getlength(word)) / 2, 30), word, font=f, fill=(255, 255, 255),
                stroke_width=10, stroke_fill=colw)
        lay.putalpha(lay.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, lay, CAM[0], CAM[1] + 110)
