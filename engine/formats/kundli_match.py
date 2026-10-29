"""Kundli / guna-milan match: two camera windows (you and the pandit), then the
eight kootas reveal one by one with points out of 36 and a running total. A
twist can re-score rows after a payment toast.

Script keys: rows[] of {name, max, score, note, t}, cams[] of {t, side, who,
clip, start, bg}, says[] of {t, until, text}, paid {t, until, text, sub},
rescore[] of {t, row, score}, verdicts[] of {t, text, good}, end.
Laid out inside the Shorts safe zone (engine/safe_zone.py).
"""
import numpy as np
from PIL import Image, ImageDraw

from simple_render import Cat, cat_window, window_bg, name_chip, fit_font, ease, ding, tick, whoosh, thunk
from chat_render import W, H, FPS, SR, font, emoji, wrap, draw_rich, line_w, comp, tone, ease_out_back

BG = (22, 14, 44)
GOLD, CARD, MUTE = (242, 196, 92), (40, 28, 74), (176, 168, 200)
GOOD, MID, BAD = (90, 220, 130), (250, 190, 70), (255, 96, 96)
WINS = {"left": (70, 262, 420, 330), "right": (590, 262, 420, 330)}
TX0, TX1, ROW0, ROW_H = 60, 900, 676, 80


def plan(s, slug):
    track, cams = [], []
    end_t = s["end"]
    for side in ("left", "right"):
        cs = sorted([c for c in s["cams"] if c["side"] == side], key=lambda c: c["t"])
        x, y, w, h = WINS[side]
        for i, c in enumerate(cs):
            t1 = cs[i + 1]["t"] if i + 1 < len(cs) else end_t
            cat = Cat(slug, f"{side}{i:02d}", c["clip"], c.get("start", 0), t1 - c["t"] + 0.2, h)
            cams.append(dict(c, t1=t1, cat=cat, bg=window_bg(c.get("bg", "home.jpg"), w, h, blur=4)))
            if not c.get("mute"):
                track.append((c["t"] + 0.05, cat.audio(min(cat.dur, t1 - c["t"])) * c.get("vol", 1.0)))
    for r in s["rows"]:
        track.append((r["t"], whoosh()))
        for k in range(r["score"]):
            track.append((r["t"] + 0.5 + k * 0.08, tick() * 2))
        if r["score"] == 0:
            track.append((r["t"] + 0.5, tone(300, 160, 0.3, 0.25, 8)))
    for rs in s.get("rescore", []):
        track.append((rs["t"], tone(660, 1320, 0.18, 0.2, 10)))
    for v in s.get("verdicts", []):
        if v["good"]:
            track.append((v["t"], np.concatenate([tone(880, 880, 0.12, 0.2, 8), tone(1320, 1320, 0.4, 0.2, 5)])))
        else:
            track.append((v["t"], thunk() * 1.6))
    if s.get("paid"):
        track.append((s["paid"]["t"], ding()))
    if s.get("sting"):
        t = s["sting"]
        track.append((t, tone(110, 55, 0.9, 0.5, 3) + tone(233, 116, 0.9, 0.2, 4)))
    return dict(cams=cams), track, end_t


def row_score(s, i, t):
    sc = s["rows"][i]["score"]
    for rs in s.get("rescore", []):
        if rs["row"] == i and t >= rs["t"]:
            sc = rs["score"]
    return sc


def draw(frame, t, s, st):
    d = ImageDraw.Draw(frame)
    for k in range(40):                                  # faint stars, decoration only
        x, y = (k * 397) % W, (k * 911) % H
        d.ellipse((x, y, x + 3, y + 3), fill=(90, 80, 140))
    pf = fit_font(s["pov"], W - 140, 42, "Bold")
    ln = wrap(s["pov"], pf, W - 140)[:1]
    draw_rich(frame, (W - line_w(ln[0])) / 2, 160, ln, pf, (255, 255, 255), 50)
    tf = font(30, "Semibold")
    title = s.get("heading", "guna milan · kundli match 🪐")
    tl = wrap(title, tf, 900)[:1]
    draw_rich(frame, (W - line_w(tl[0])) / 2, 214, tl, tf, GOLD, 38)
    # camera windows
    for side, (x, y, w, h) in WINS.items():
        cs = [c for c in st["cams"] if c["side"] == side and c["t"] <= t]
        if not cs:
            continue
        c = cs[-1]
        d.rounded_rectangle((x - 5, y - 5, x + w + 5, y + h + 5), 34, fill=GOLD)
        comp(frame, cat_window(c["bg"], c["cat"].at(t - c["t"]), w, h, fit=0.95, r=30), x, y)
        comp(frame, name_chip(c["who"], size=28), x + 18, y + 16)
    comp(frame, emoji("💞", 64), (WINS["left"][0] + WINS["left"][2] + WINS["right"][0]) / 2 - 32, 395)
    sub = s.get("pair", "")
    sf = font(28)
    d.text(((W - sf.getlength(sub)) / 2, 612), sub, font=sf, fill=MUTE)
    # pandit's speech, over the right window
    for sy in s.get("says", []):
        if sy["t"] <= t < sy["until"]:
            a = min(1, (t - sy["t"]) / 0.2, (sy["until"] - t) / 0.2)
            x, y, w, h = WINS[sy.get("side", "right")]
            cf = font(32, "Semibold")
            lines = wrap(sy["text"], cf, w - 44)[:3]
            bh = 24 + 40 * len(lines)
            box = Image.new("RGBA", (w - 20, bh), (0, 0, 0, 0))
            ImageDraw.Draw(box).rounded_rectangle((0, 0, w - 21, bh - 1), 20, fill=(0, 0, 0, 205))
            draw_rich(box, 14, 10, lines, cf, (255, 255, 255), 40)
            box.putalpha(box.getchannel("A").point(lambda v, a=a: int(v * a)))
            comp(frame, box, x + 10, y + h - bh - 10)
    # table
    hf = font(26, "Semibold")
    d.text((TX0 + 20, ROW0 - 36), "koota", font=hf, fill=MUTE)
    d.text((TX1 - 20 - hf.getlength("points"), ROW0 - 36), "points", font=hf, fill=MUTE)
    total, shown = 0, 0
    nf, nof, pf2 = font(32, "Bold"), font(28), font(36, "Heavy")
    for i, r in enumerate(s["rows"]):
        if t < r["t"]:
            continue
        shown += 1
        sc = row_score(s, i, t)
        a = ease((t - r["t"]) / 0.3)
        y = ROW0 + i * ROW_H
        row = Image.new("RGBA", (TX1 - TX0, ROW_H - 8), (0, 0, 0, 0))
        rd = ImageDraw.Draw(row)
        flash = any(rs["row"] == i and 0 <= t - rs["t"] < 0.6 for rs in s.get("rescore", []))
        rd.rounded_rectangle((0, 0, row.width - 1, row.height - 1), 16, fill=(70, 120, 80) if flash else CARD)
        rd.text((20, 6), r["name"], font=nf, fill=(255, 255, 255))
        draw_rich(row, 20, 40, wrap(r["note"], fit_font(r["note"], 640, 28), 660)[:1], fit_font(r["note"], 640, 28), MUTE, 32)
        if t >= r["t"] + 0.5:
            col = GOOD if sc == r["max"] else BAD if sc == 0 else MID
            txt = f"{sc}/{r['max']}"
            rd.text((row.width - 20 - pf2.getlength(txt), 16), txt, font=pf2, fill=col)
            total += sc
        row.putalpha(row.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, row, TX0 + (1 - a) * 40, y)
    # total + verdict
    if shown:
        fy = ROW0 + len(s["rows"]) * ROW_H + 4
        tf2 = font(40, "Heavy")
        d.text((TX0 + 20, fy), f"total: {total}/36", font=tf2, fill=GOLD)
        v = [v for v in s.get("verdicts", []) if v["t"] <= t]
        if v:
            v = v[-1]
            k = ease_out_back(min(1, (t - v["t"]) / 0.35))
            vf = font(32, "Bold")
            vw = vf.getlength(v["text"]) + 40
            pill = Image.new("RGBA", (int(vw), 56), (0, 0, 0, 0))
            ImageDraw.Draw(pill).rounded_rectangle((0, 0, vw - 1, 55), 28, fill=(40, 150, 80) if v["good"] else (200, 50, 50))
            draw_rich(pill, 20, 9, wrap(v["text"], vf, 900)[:1], vf, (255, 255, 255), 40)
            sc = 1.5 - 0.5 * k
            pill = pill.resize((max(1, int(pill.width * sc)), max(1, int(pill.height * sc))), Image.BILINEAR)
            comp(frame, pill, TX1 - pill.width, fy - (pill.height - 56) / 2)
    pd = s.get("paid")
    if pd and pd["t"] <= t < pd["until"]:
        k = ease_out_back(min(1, (t - pd["t"]) / 0.35))
        a = min(1, (pd["until"] - t) / 0.25)
        card = Image.new("RGBA", (700, 210), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, 699, 209), 36, fill=(250, 250, 252))
        cd.ellipse((30, 55, 130, 155), fill=(40, 170, 90))
        cd.line((55, 105, 75, 128), fill=(255, 255, 255), width=10)
        cd.line((75, 128, 110, 80), fill=(255, 255, 255), width=10)
        cd.text((160, 44), pd["text"], font=font(46, "Heavy"), fill=(20, 20, 24))
        cd.text((160, 112), pd["sub"], font=font(30), fill=(100, 100, 110))
        card.putalpha(card.getchannel("A").point(lambda v, a=a: int(v * a)))
        sc = 0.6 + 0.4 * k
        card = card.resize((int(700 * sc), int(210 * sc)), Image.BILINEAR)
        comp(frame, card, (W - card.width) / 2, 330 + (210 - card.height) / 2)


PLAN, DRAW = plan, draw
