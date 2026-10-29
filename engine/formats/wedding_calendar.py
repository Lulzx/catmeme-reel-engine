"""Wedding-season calendar: a month grid fills with weddings, sangeets and haldis
as family members add them; a toast says who added what, the leave balance drains,
and a cat window reacts. Laid out inside the Shorts safe zone
(engine/safe_zone.py): the grid ends above y 1000 so it can use x 60..1020;
everything below stays inside x 60..900, y < 1420.

Script keys: month, first_weekday (0 = Sunday), days, leaves, prefilled[] of
{day, emoji, label}, events[] of {t, days[], emoji, label, color, cost, who, text},
cams[] of {t, clip, start, bg}, end.
"""
import numpy as np
from PIL import Image, ImageDraw

from simple_render import Cat, cat_window, window_bg, name_chip, fit_font, ease, ding, tick, thunk
from chat_render import W, H, FPS, SR, font, emoji, wrap, draw_rich, line_w, comp, tone, ease_out_back

BG = (246, 241, 234)
INK, MUTE, RED, GREEN = (34, 30, 28), (130, 120, 112), (220, 60, 50), (60, 170, 90)
GX0, GY0, CW, CH = 60, 300, 137, 128
WIN = (60, 986, 360, 420)
PX0, PX1 = 440, 900


def plan(s, slug):
    track, cams = [], []
    end_t = s["end"]
    cs = sorted(s["cams"], key=lambda c: c["t"])
    for i, c in enumerate(cs):
        t1 = cs[i + 1]["t"] if i + 1 < len(cs) else end_t
        cat = Cat(slug, f"cam{i:02d}", c["clip"], c.get("start", 0), t1 - c["t"] + 0.2, WIN[3])
        cams.append(dict(c, t1=t1, cat=cat, bg=window_bg(c.get("bg", "home.jpg"), WIN[2], WIN[3], blur=4)))
        if not c.get("mute"):
            track.append((c["t"] + 0.05, cat.audio(min(cat.dur, t1 - c["t"])) * c.get("vol", 1.0)))
    left = s["leaves"]
    for e in s["events"]:
        for k, _ in enumerate(e["days"]):
            track.append((e["t"] + 0.15 * k, tone(900, 1300, 0.08, 0.16, 25)))
        if e.get("cost"):
            left -= e["cost"]
            track.append((e["t"] + 0.6, thunk() * (1.6 if left <= 0 else 1.0)))
        if e.get("finale"):
            track.append((e["t"], np.concatenate([tone(587, 587, 0.25, 0.14, 4), tone(740, 740, 0.25, 0.14, 4),
                                                  tone(880, 880, 0.6, 0.16, 3)])))
        else:
            track.append((e["t"] - 0.05, ding() * 0.6))
    return dict(cams=cams), track, end_t


def chip(e, w=CW - 12):
    f = fit_font(e["label"], w - 16, 24, "Semibold")
    im = Image.new("RGBA", (w, 74), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 73), 14, fill=tuple(e.get("color", (255, 214, 120))))
    comp(im, emoji(e["emoji"], 34), (w - 34) / 2, 4)
    d.text(((w - f.getlength(e["label"])) / 2, 42), e["label"], font=f, fill=INK)
    return im


def draw(frame, t, s, st):
    d = ImageDraw.Draw(frame)
    pf = fit_font(s["pov"], W - 220, 40, "Bold")
    pl = wrap(s["pov"], pf, W - 220)[:1]
    draw_rich(frame, (W - line_w(pl[0])) / 2, 160, pl, pf, INK, 48)
    mf = font(40, "Heavy")
    d.text((GX0 + 6, 210), s["month"], font=mf, fill=RED)
    wf = font(24, "Semibold")
    for i, wd in enumerate("SMTWTFS"):
        d.text((GX0 + i * CW + CW / 2 - wf.getlength(wd) / 2, 264), wd, font=wf, fill=MUTE)
    placed = {p["day"]: p for p in s.get("prefilled", [])}
    landing = {}
    for e in s["events"]:
        for k, day in enumerate(e["days"]):
            tt = e["t"] + 0.15 * k
            if t >= tt:
                placed[day] = e; landing[day] = tt
    fd = s.get("first_weekday", 0)
    df = font(26, "Semibold")
    for day in range(1, s["days"] + 1):
        idx = fd + day - 1
        cx, cy = GX0 + (idx % 7) * CW, GY0 + (idx // 7) * CH
        weekend = idx % 7 in (0, 6)
        d.rounded_rectangle((cx + 3, cy + 3, cx + CW - 3, cy + CH - 3), 14,
                            fill=(236, 230, 222) if weekend else (255, 255, 255))
        d.text((cx + 12, cy + 8), str(day), font=df, fill=RED if idx % 7 == 0 else INK)
        if day in placed:
            c = chip(placed[day])
            age = t - landing.get(day, -9)
            if 0 <= age < 0.3:
                k = ease_out_back(age / 0.3)
                c = c.resize((max(1, int(c.width * k)), max(1, int(c.height * k))), Image.BILINEAR)
            comp(frame, c, cx + 6 + (CW - 12 - c.width) / 2, cy + 46 + (74 - c.height) / 2)
    # cat window
    cs = [c for c in st["cams"] if c["t"] <= t]
    if cs:
        c = cs[-1]
        x, y, w, h = WIN
        comp(frame, cat_window(c["bg"], c["cat"].at(t - c["t"]), w, h, fit=0.95, r=30), x, y)
        comp(frame, name_chip("you", size=28), x + 16, y + 14)
    # toast: who added what
    ev = [e for e in s["events"] if e["t"] <= t]
    if ev:
        e = ev[-1]
        a = ease((t - e["t"]) / 0.3)
        card = Image.new("RGBA", (PX1 - PX0, 196), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, card.width - 1, 195), 24, fill=(255, 255, 255), outline=(225, 218, 208), width=2)
        comp(card, emoji("📅", 40), 20, 18)
        cd.text((72, 22), f"{e['who']} added", font=font(28, "Bold"), fill=RED)
        tf = font(28)
        draw_rich(card, 22, 72, wrap(e["text"], tf, card.width - 44)[:3], tf, INK, 38)
        card.putalpha(card.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, card, PX0, WIN[1] + (1 - a) * 20)
    # leave balance
    left = s["leaves"] - sum(e.get("cost", 0) for e in s["events"] if t >= e["t"] + 0.6)
    ly = WIN[1] + 214
    d.rounded_rectangle((PX0, ly, PX1, WIN[1] + WIN[3]), 24, fill=(255, 255, 255), outline=(225, 218, 208), width=2)
    d.text((PX0 + 22, ly + 16), "leaves left", font=font(30, "Semibold"), fill=MUTE)
    col = GREEN if left > 4 else (230, 150, 40) if left > 0 else RED
    nf = font(96, "Heavy")
    d.text((PX0 + 22, ly + 52), str(max(0, left)), font=nf, fill=col)
    d.text((PX0 + 30 + nf.getlength(str(max(0, left))), ly + 110), f"/ {s['leaves']}", font=font(34), fill=MUTE)
    bw = PX1 - PX0 - 44
    d.rounded_rectangle((PX0 + 22, ly + 168, PX0 + 22 + bw, ly + 186), 9, fill=(234, 228, 220))
    if left > 0:
        d.rounded_rectangle((PX0 + 22, ly + 168, PX0 + 22 + bw * left / s["leaves"], ly + 186), 9, fill=col)
    for e in s["events"]:                              # floating "-n"
        if e.get("cost") and 0.6 <= t - e["t"] < 1.6:
            k = (t - e["t"] - 0.6)
            ff = font(44, "Heavy")
            d.text((PX1 - 120, ly + 60 - 40 * k), f"-{e['cost']}", font=ff,
                   fill=RED + (int(255 * (1 - k)),))


PLAN, DRAW = plan, draw
