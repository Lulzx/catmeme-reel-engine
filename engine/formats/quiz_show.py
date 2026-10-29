"""KBC-style quiz: a cat contestant, one question, four options and three
lifelines (50:50, audience poll, phone a friend). The top window is the camera
(host, contestant or whoever is on the phone); captions run along its bottom.

Script keys: question, options[4], answer, amount, people{id: {name, color}},
events[] with t and one of: cam, show, say, lifeline, lock, reveal, incoming, end.
"""
import math
import numpy as np
from PIL import Image, ImageDraw

from simple_render import (Cat, cat_window, window_bg, name_chip, fit_font, ease, tick, whoosh,
                           thunk, ding, ring, noise, rounded)
from chat_render import W, H, FPS, SR, font, emoji, wrap, draw_rich, line_w, comp, tone, ease_out_back

BG = (8, 6, 38)
GOLD, NAVY, ORANGE, GREEN = (240, 190, 70), (22, 26, 92), (236, 128, 20), (30, 160, 70)
WIN = (60, 200, 960, 830)                     # camera window x, y, w, h
LIFE_Y, AMT_Y, Q_Y, OPT_Y = 1080, 1200, 1280, 1510


def hexbox(w, h, fill, edge=GOLD):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(h / 2, 0), (w - h / 2, 0), (w - 1, h / 2), (w - h / 2, h - 1), (h / 2, h - 1), (0, h / 2)]
    d.polygon(pts, fill=edge)
    k = 5
    inner = [(h / 2 + k * 0.5, k), (w - h / 2 - k * 0.5, k), (w - 1 - k * 1.6, h / 2),
             (w - h / 2 - k * 0.5, h - 1 - k), (h / 2 + k * 0.5, h - 1 - k), (k * 1.6, h / 2)]
    d.polygon(inner, fill=fill)
    return im


def heartbeat():
    return tone(62, 48, 0.18, 0.55, 14)


def plan(s, slug):
    evs, track = s["events"], []
    end_t = next(e["t"] for e in evs if e.get("end"))
    cams = [e for e in evs if "cam" in e]
    st = dict(cams=[], says=[], shows={}, used={}, removed=set(), remove_t={}, poll=None, phone=None,
              lock=None, reveal=None, incoming=None)
    for i, e in enumerate(cams):
        nxt = cams[i + 1]["t"] if i + 1 < len(cams) else end_t
        c = e["cam"]
        cat = Cat(slug, f"cam{i:02d}", c["clip"], c.get("start", 0), nxt - e["t"] + 0.2, WIN[3])
        st["cams"].append(dict(t=e["t"], t1=nxt, cat=cat, who=c["who"],
                               bg=window_bg(c.get("bg", "stage.jpg"), WIN[2], WIN[3], blur=5, dim=0.15)))
        if not c.get("mute"):
            track.append((e["t"] + 0.05, cat.audio(min(cat.dur, nxt - e["t"])) * c.get("vol", 1.0)))
    for e in evs:
        t = e["t"]
        if "show" in e:
            st["shows"][("q" if e["show"] == "question" else e["i"])] = t
            track.append((t, tick() * 2))
            if e["show"] == "question":                    # the dhum-dhum sting
                track.append((t, tone(110, 55, 0.7, 0.5, 4) + tone(220, 110, 0.7, 0.2, 5)))
        if "say" in e:
            st["says"].append(dict(e["say"], t=t))
        if "lifeline" in e:
            ll = e["lifeline"]
            st["used"][ll] = t
            track.append((t, whoosh() * 2))
            if ll == "5050":
                for i in e["remove"]:
                    st["remove_t"][i] = t + 0.3
                track.append((t + 0.3, thunk()))
            elif ll == "audience":
                st["poll"] = dict(t=t, until=e["until"], vals=e["poll"])
            elif ll == "phone":
                st["phone"] = dict(t=t, until=e["until"], secs=e.get("seconds", 30))
                n = e.get("seconds", 30)
                for k in range(n):
                    track.append((t + (e["until"] - t) * k / n, tone(2000, 2000, 0.02, 0.05, 80)))
        if "lock" in e:
            st["lock"] = (t, e["lock"])
            track.append((t, tone(300, 600, 0.35, 0.25, 6)))
            nxt = next(x["t"] for x in evs if "reveal" in x)
            k = t + 0.6
            while k < nxt - 0.2:
                track.append((k, heartbeat())); k += 0.55
        if "reveal" in e:
            st["reveal"] = (t, e["reveal"])
            track.append((t, np.concatenate([tone(880, 880, 0.15, 0.2, 6), tone(1320, 1320, 0.5, 0.2, 4)])))
            crowd = noise(2.6, 0.16, 11) * np.abs(np.sin(np.linspace(0, 40, int(2.6 * SR))))[:, None]
            crowd *= np.linspace(1, 0, len(crowd), dtype=np.float32)[:, None]
            track.append((t + 0.2, crowd.astype(np.float32)))
        if "incoming" in e:
            st["incoming"] = dict(e["incoming"], t=t, until=e["until"])
            track.append((t, ring(e["until"] - t)))
    return st, track, end_t


def draw_caption(frame, t, say, people):
    age = t - say["t"]
    if not 0 <= age < say["until"] - say["t"]:
        return
    a = min(1, age / 0.2, (say["until"] - t) / 0.2)
    p = people[say["who"]]
    tf = font(42, "Semibold")
    lines = wrap(say["text"], tf, WIN[2] - 100)[:3]
    h = 70 + 54 * len(lines)
    box = Image.new("RGBA", (WIN[2] - 40, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle((0, 0, box.width - 1, h - 1), 26, fill=(0, 0, 0, 190))
    d.text((30, 14), p["name"], font=font(32, "Bold"), fill=tuple(p["color"]))
    draw_rich(box, 30, 58, lines, tf, (255, 255, 255), 54)
    box.putalpha(box.getchannel("A").point(lambda v, a=a: int(v * a)))
    comp(frame, box, WIN[0] + 20, WIN[1] + WIN[3] - h - 20)


def draw(frame, t, s, st):
    d = ImageDraw.Draw(frame)
    for y in range(0, H, 8):                           # stage glow
        k = max(0.0, 1 - abs(y - 1300) / 1300)
        d.rectangle((0, y, W, y + 8), fill=(int(8 + 30 * k), int(6 + 10 * k), int(38 + 60 * k)))
    pf = fit_font(s["pov"], W - 80, 46, "Bold")
    y = 70
    for ln in wrap(s["pov"], pf, W - 80):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, (255, 255, 255), 56); y += 56
    x0, y0, ww, wh = WIN
    # camera
    cam = [c for c in st["cams"] if c["t"] <= t]
    if cam:
        c = cam[-1]
        win = cat_window(c["bg"], c["cat"].at(t - c["t"]), ww, wh, fit=0.95)
        d.rounded_rectangle((x0 - 6, y0 - 6, x0 + ww + 6, y0 + wh + 6), 46, fill=GOLD)
        comp(frame, win, x0, y0)
        comp(frame, name_chip(s["people"][c["who"]]["name"]), x0 + 28, y0 + 28)
    ph = st["phone"]
    if ph and ph["t"] <= t < ph["until"] + 0.8:
        left = max(0, ph["secs"] - int((t - ph["t"]) / (ph["until"] - ph["t"]) * ph["secs"]))
        cx, cy, r = x0 + ww - 110, y0 + 110, 76
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(10, 10, 40, 230))
        frac = left / ph["secs"]
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * frac, fill=GOLD if left > 5 else (230, 60, 50), width=12)
        nf = font(70, "Bold")
        txt = str(left)
        d.text((cx - nf.getlength(txt) / 2, cy - 44), txt, font=nf, fill=(255, 255, 255))
        if t >= ph["until"]:
            chip = name_chip("call ended", bg=(200, 40, 40, 235), fg=(255, 255, 255))
            comp(frame, chip, x0 + (ww - chip.width) / 2, y0 + wh / 2 - 30)
    pl = st["poll"]
    if pl and pl["t"] <= t < pl["until"]:
        a = min(1, (t - pl["t"]) / 0.3, (pl["until"] - t) / 0.3)
        panel = Image.new("RGBA", (640, 560), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        pd.rounded_rectangle((0, 0, 639, 559), 30, fill=(12, 14, 60, 235), outline=GOLD, width=4)
        pd.text((40, 26), "audience poll", font=font(40, "Bold"), fill=GOLD)
        grow = ease((t - pl["t"] - 0.3) / 1.4)
        for i, v in enumerate(pl["vals"]):
            bx = 60 + i * 140
            bh = 330 * v / 100 * grow
            pd.rectangle((bx, 470 - bh, bx + 90, 470), fill=(90, 150, 255))
            lab = f"{int(round(v * grow))}%"
            lf = font(32, "Semibold")
            pd.text((bx + 45 - lf.getlength(lab) / 2, 430 - bh), lab, font=lf, fill=(255, 255, 255))
            pd.text((bx + 30, 486), "ABCD"[i], font=font(40, "Bold"), fill=GOLD)
        panel.putalpha(panel.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, panel, x0 + (ww - 640) / 2, y0 + 90)
    for sy in st["says"]:
        draw_caption(frame, t, sy, s["people"])
    inc = st["incoming"]
    if inc and inc["t"] <= t < inc["until"]:
        k = ease_out_back(min(1, (t - inc["t"]) / 0.35))
        card = Image.new("RGBA", (ww - 60, 150), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, card.width - 1, 149), 40, fill=(245, 245, 248))
        cd.ellipse((30, 30, 120, 120), fill=(52, 199, 89))
        comp(card, emoji("📞", 54), 48, 48)
        cd.text((150, 26), inc["name"], font=font(44, "Bold"), fill=(20, 20, 24))
        cd.text((150, 84), "calling…", font=font(36), fill=(110, 110, 118))
        comp(frame, card, x0 + 30, y0 - 170 + 210 * k)
    # lifelines
    for i, (key, label) in enumerate((("5050", "50:50"), ("audience", "👥"), ("phone", "📞"))):
        cx, cy, r = 300 + i * 240, LIFE_Y + 50, 56
        used = key in st["used"] and t >= st["used"][key]
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(40, 20, 110) if not used else (30, 24, 60),
                  outline=GOLD, width=4)
        if label.startswith("5"):
            lf = font(36, "Bold")
            d.text((cx - lf.getlength(label) / 2, cy - 24), label, font=lf, fill=(255, 255, 255) if not used else (110, 110, 130))
        else:
            em = emoji(label, 60)
            if used:
                em = em.copy(); em.putalpha(em.getchannel("A").point(lambda v: v // 3))
            comp(frame, em, cx - 30, cy - 30)
        if used:
            d.line((cx - 40, cy - 40, cx + 40, cy + 40), fill=(230, 50, 50), width=9)
            d.line((cx + 40, cy - 40, cx - 40, cy + 40), fill=(230, 50, 50), width=9)
    # amount
    if "q" in st["shows"] and t >= st["shows"]["q"]:
        amt = s["amount"] + " ke liye"
        af = font(44, "Bold")
        d.text(((W - af.getlength(amt)) / 2, AMT_Y), amt, font=af, fill=GOLD)
        d.line((0, Q_Y + 80, W, Q_Y + 80), fill=GOLD, width=3)
        qb = hexbox(W - 60, 160, NAVY)
        qf = fit_font(s["question"], W - 260, 46, "Semibold")
        ql = wrap(s["question"], qf, W - 260)[:2]
        qy = 80 - len(ql) * 29
        for ln in ql:
            draw_rich(qb, (qb.width - line_w(ln)) / 2, qy, [ln], qf, (255, 255, 255), 58); qy += 58
        a = ease((t - st["shows"]["q"]) / 0.3)
        qb.putalpha(qb.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, qb, 30, Q_Y)
    for i, opt in enumerate(s["options"]):
        if i not in st["shows"] or t < st["shows"][i]:
            continue
        ox, oy = 30 + (i % 2) * 520, OPT_Y + (i // 2) * 150
        if i % 2 == 0:
            d.line((0, oy + 60, W, oy + 60), fill=GOLD, width=3)
        fill = NAVY
        gone = i in st["remove_t"] and t >= st["remove_t"][i]
        if st["lock"] and t >= st["lock"][0] and st["lock"][1] == i:
            fill = ORANGE
        if st["reveal"] and t >= st["reveal"][0] and st["reveal"][1] == i:
            fill = GREEN if int((t - st["reveal"][0]) * 6) % 2 == 0 or t - st["reveal"][0] > 1.2 else ORANGE
        ob = hexbox(500, 120, fill)
        od = ImageDraw.Draw(ob)
        if not gone:
            lf = font(42, "Bold")
            od.text((70, 32), "ABCD"[i] + ":", font=lf, fill=GOLD if fill == NAVY else (255, 255, 255))
            of = fit_font(opt, 330, 42, "Semibold")
            od.text((130, 32), opt, font=of, fill=(255, 255, 255))
        a = ease((t - st["shows"][i]) / 0.25)
        ob.putalpha(ob.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, ob, ox, oy)
    rv = st["reveal"]
    if rv and t >= rv[0] + 0.4 and (not inc or t < inc["t"]):
        k = ease_out_back(min(1, (t - rv[0] - 0.4) / 0.4))
        bf = font(int(96 * k) + 1, "Heavy")
        txt = s["amount"]
        d.text(((W - bf.getlength(txt)) / 2, y0 + 120), txt, font=bf, fill=GOLD, stroke_width=6, stroke_fill=(60, 30, 0))
        sf = font(int(50 * k) + 1, "Bold")
        sub = "jeet gaye!"
        d.text(((W - sf.getlength(sub)) / 2, y0 + 240), sub, font=sf, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))


PLAN, DRAW = plan, draw
