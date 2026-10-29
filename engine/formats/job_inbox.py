"""job_inbox: a mail app's inbox during a job hunt. Emails arrive one at a time
at the top of the list (rejections, HR, a relative's forwards), the cat cam cuts
to whoever sent or suffered each one, and the last email opens full screen.

Script: `events` [{t, from, color, subject, preview, time, cam?} | {t, open:
{from, subject, body, time}} | {t, end}]; `t: -1` items are already in the inbox.
Laid out inside the Shorts safe zone (engine/safe_zone.py).
"""
from PIL import Image, ImageDraw

from simple_render import Cat, cat_window, window_bg, name_chip, fit_font, ease, tone, whoosh, W, H
from chat_render import font, emoji, wrap, draw_rich, line_w, comp, ease_out_back
import numpy as np

BG = (255, 255, 255)
L, R = 60, 1020
LIST_Y, ROW_H, LIST_B = 380, 150, 990
CAM = (60, 1000, 820, 410)
INK, GREY, LINE = (32, 33, 36), (95, 99, 104), (232, 234, 237)


def mail_sound():
    return (whoosh() * 0.8)[: int(0.25 * 48000)]


def clip_text(text, f, maxw):
    if f.getlength(text) <= maxw:
        return text
    while text and f.getlength(text + "…") > maxw:
        text = text[:-1]
    return text.rstrip() + "…"


def row(e, unread=True):
    im = Image.new("RGBA", (R - L, ROW_H), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 26, 80, 106), fill=tuple(e["color"]))
    lf = font(40, "Semibold")
    letter = e["from"][0].upper()
    d.text((40 - lf.getlength(letter) / 2, 42), letter, font=lf, fill=(255, 255, 255))
    x = 100
    tf = font(30, "Semibold" if unread else "Regular")
    tw = tf.getlength(e["time"])
    d.text((R - L - tw, 14), e["time"], font=tf, fill=INK if unread else GREY)
    sf = font(37, "Bold" if unread else "Regular")
    d.text((x, 10), clip_text(e["from"], sf, R - L - x - tw - 30), font=sf, fill=INK)
    jf = font(34, "Semibold" if unread else "Regular")
    d.text((x, 58), clip_text(e["subject"], jf, R - L - x - 10), font=jf, fill=INK)
    pf = font(31)
    d.text((x, 102), clip_text(e["preview"], pf, R - L - x - 10), font=pf, fill=GREY)
    d.line((x, ROW_H - 1, R - L, ROW_H - 1), fill=LINE, width=2)
    return im


def PLAN(s, slug):
    evs, track, cams = s["events"], [], []
    end_t = next(e["t"] for e in evs if e.get("end"))
    cam_evs = [e for e in evs if "cam" in e]
    for i, e in enumerate(cam_evs):
        c = e["cam"]
        t0 = max(0.0, e["t"])
        t1 = cam_evs[i + 1]["t"] if i + 1 < len(cam_evs) else end_t
        cat = Cat(slug, f"cam{i:02d}", c["clip"], c["start"], min(c.get("dur", 99), t1 - t0 + 0.2), 520)
        cams.append(dict(c, t=t0, cat=cat, bg=window_bg(c.get("bg", "home.jpg"), CAM[2], CAM[3], blur=4)))
        track.append((t0 + 0.15, cat.audio(min(cat.dur, t1 - t0 - 0.1, 3.6)) * c.get("vol", 0.85)))
    mails = []
    for e in evs:
        if "subject" in e and "open" not in e:
            mails.append(dict(e, im=row(e), im_read=row(e, unread=False)))
            if e["t"] >= 0:
                track.append((e["t"], mail_sound()))
                track.append((e["t"] + 0.05, tone(1175, 1175, 0.12, 0.12, 14)))
        if "open" in e:
            track.append((e["t"], tone(660, 880, 0.08, 0.1, 30)))
    return {"cams": cams, "mails": mails, "open": next((e for e in evs if "open" in e), None)}, track, end_t


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    pf = fit_font(s["pov"], R - L - 20, 44, "Bold")
    y = 165
    for ln in wrap(s["pov"], pf, R - L - 20):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, INK, 56); y += 56
    d.rounded_rectangle((L, 236, R, 312), 38, fill=(234, 239, 247))
    d.text((L + 96, 254), "Search in mail", font=font(32), fill=GREY)
    d.ellipse((L + 34, 254, L + 64, 284), outline=GREY, width=4)
    d.line((L + 60, 280, L + 72, 292), fill=GREY, width=5)
    d.ellipse((R - 70, 244, R - 10, 304), fill=(26, 115, 232))
    af = font(30, "Semibold")
    d.text((R - 40 - af.getlength("Y") / 2, 256), "Y", font=af, fill=(255, 255, 255))
    d.text((L, 326), "Primary", font=font(32, "Bold"), fill=(26, 115, 232))

    shown = [m for m in P["mails"] if m["t"] <= t][::-1]
    yy = LIST_Y
    for k, m in enumerate(shown):
        age = t - m["t"]
        im = m["im"] if (k == 0 or m["t"] >= 0) else m["im_read"]
        if k == 0 and 0 <= age < 0.4:
            a = ease(age / 0.4)
            hgt = int(ROW_H * a)
            if hgt > 0:
                part = im.copy()
                part.putalpha(int(255 * a))
                comp(frame, part, L, yy - ROW_H + hgt)
            yy += hgt
            continue
        if yy + ROW_H > LIST_B:
            break
        comp(frame, im, L, yy)
        yy += ROW_H

    op = P["open"]
    if op and t >= op["t"]:
        o = op["open"]
        k = ease_out_back(min(1, (t - op["t"]) / 0.35))
        card = Image.new("RGBA", (R - L, LIST_B - LIST_Y + 50), (255, 255, 255, 255))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, card.width - 1, card.height - 1), 28, fill=(255, 255, 255), outline=(218, 220, 224), width=3)
        sf = font(40, "Bold")
        sy = 30
        for ln in wrap(o["subject"], sf, card.width - 70)[:2]:
            draw_rich(card, 34, sy, [ln], sf, INK, 50); sy += 50
        cd.text((34, sy + 10), f"{o['from']} · {o['time']}", font=font(30), fill=GREY)
        sy += 64
        cd.line((34, sy, card.width - 34, sy), fill=LINE, width=2)
        bf = font(44)
        sy += 26
        for para in o["body"]:
            for ln in wrap(para, bf, card.width - 70):
                draw_rich(card, 34, sy, [ln], bf, INK, 58); sy += 58
            sy += 22
        sc = 0.85 + 0.15 * k
        card = card.resize((int(card.width * sc), int(card.height * sc)), Image.BILINEAR)
        sh = Image.new("RGBA", (card.width, card.height), (0, 0, 0, 40))
        comp(frame, sh, (W - card.width) / 2 + 6, LIST_Y - 40 + 10)
        comp(frame, card, (W - card.width) / 2, LIST_Y - 40)

    cur = [c for c in P["cams"] if c["t"] <= t]
    if cur:
        c = cur[-1]
        x, wy, w, h = CAM
        win = cat_window(c["bg"], c["cat"].at(t - c["t"], loop=c.get("loop", False)), w, h, fit=c.get("fit", 0.85), r=32)
        comp(frame, win, x, wy)
        comp(frame, name_chip(c["label"], size=30), x + 20, wy + 20)
