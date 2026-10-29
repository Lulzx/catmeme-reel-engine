"""screen_time: an iOS weekly Screen Time report where the numbers tell the joke.

Each `phase` is one device's report: the daily average counts up, the seven day
bars grow, the most-used apps slide in one by one, then pickups. A `dropdown`
switches devices, `cats` are reaction windows at the bottom (with a speech line),
and a `banner` drops a Screen Time notification for the ending.
"""
import re
from PIL import Image, ImageDraw

from simple_render import (Cat, cat_window, window_bg, name_chip, status_bar, ease, ding, tick,
                           whoosh, thunk)
from chat_render import W, H, font, emoji, comp, wrap, draw_rich, ease_out_back

BG = (242, 242, 247)
INK, GREY, BLUE = (17, 17, 20), (138, 138, 142), (10, 132, 255)
CARD = (255, 255, 255)
DAY_MAX = 13 * 60                      # minutes; one scale for both devices so the bars compare
# Shorts safe area (engine/safe_zone.py): x 60..1020, y 150..1420, and x <= 900 below y 1000
X0, X1 = 60, 1020
WIN = (60, 975, 830, 435)              # x, y, w, h of the reaction window


def minutes(s):
    h = re.search(r"(\d+)h", s); m = re.search(r"(\d+)m", s)
    return (int(h.group(1)) if h else 0) * 60 + (int(m.group(1)) if m else 0)


def hm(mins):
    mins = int(round(mins))
    return f"{mins // 60}h {mins % 60:02d}m" if mins >= 60 else f"{mins}m"


def PLAN(s, slug):
    track = []
    for ph in s["phases"]:
        t = ph["t"]
        ph["row_t"] = [t + 1.6 + k * ph.get("row_gap", 0.8) for k in range(len(ph["apps"]))]
        ph["pick_t"] = ph["row_t"][-1] + 0.9
        track.append((t, whoosh()))
        for rt in ph["row_t"]:
            track.append((rt, tick()))
        track.append((ph["pick_t"], tick()))
    cats = []
    for i, c in enumerate(s["cats"]):
        c = dict(c)
        c["cat"] = Cat(slug, f"win{i:02d}", c["clip"], c["start"], c["until"] - c["t"], WIN[3])
        c["bg"] = window_bg(c.get("bg", "livingroom.jpg"), WIN[2], WIN[3], blur=4)
        c["chip"] = name_chip(c["who"])
        track.append((c["t"] + 0.1, c["cat"].audio(min(c["cat"].dur, c.get("sound_dur", 3.0))) * c.get("vol", 1.0)))
        cats.append(c)
    dd = s.get("dropdown")
    if dd:
        track.append((dd["t"], tick())); track.append((dd["tap"], thunk()))
    b = s.get("banner")
    if b:
        track.append((b["t"], ding()))
    return dict(phases=s["phases"], cats=cats), track, s["end"]


def card(frame, box, r=30):
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle(box, r, fill=CARD)


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    status_bar(d, s.get("clock", "10:48"), INK)
    d.text((X0 + 8, 156), "Screen Time", font=font(58, "Bold"), fill=INK)
    ph = [p for p in P["phases"] if p["t"] <= t]
    ph = ph[-1] if ph else P["phases"][0]
    age = t - ph["t"]
    # device pill, right of the title
    pf = font(34, "Semibold")
    label = ph["device"] + "  ▾"
    pw = pf.getlength(label) + 50
    px = X1 - pw
    d.rounded_rectangle((px, 166, X1, 222), 28, fill=(229, 229, 234))
    d.text((px + 25, 173), label, font=pf, fill=BLUE)
    a = ease(age / 0.35)
    layer = Image.new("RGBA", (W, 720), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    # daily average (left), pickups (right), week bars (bottom of the card)
    ld.rounded_rectangle((X0, 0, X1, 360), 30, fill=CARD)
    ld.text((X0 + 34, 22), "Daily Average", font=font(32), fill=GREY)
    avg = minutes(ph["avg"]) * ease((age - 0.2) / 1.4)
    ld.text((X0 + 34, 60), hm(avg), font=font(84, "Bold"), fill=INK)
    if ph.get("delta") and age > 1.6:
        ld.text((X0 + 34, 160), ph["delta"], font=font(28), fill=GREY)
    if t >= ph["pick_t"]:
        pa = ease((t - ph["pick_t"]) / 0.4)
        for i, (lab, val) in enumerate((("Pickups / day", ph["pickups"]), ("First pickup", ph["first"]))):
            x = 610
            y = 22 + i * 92
            ld.text((x, y), lab, font=font(28), fill=GREY)
            ld.text((x, y + 34 + (1 - pa) * 14), val, font=font(46, "Bold"), fill=INK)
    bx0, by1, bw = X0 + 50, 320, 96
    for i, (day, v) in enumerate(zip("MTWTFSS", ph["days"])):
        g = ease((age - 0.3 - i * 0.08) / 0.6)
        h = 105 * min(1, v * 60 / DAY_MAX) * g
        x = bx0 + i * (bw + 30)
        ld.rounded_rectangle((x, by1 - h, x + bw, by1), 9, fill=tuple(ph.get("bar", BLUE)))
        ld.text((x + bw / 2 - 9, by1 + 4), day, font=font(22), fill=GREY)
    ld.line((X0 + 34, by1 - 106, X1 - 34, by1 - 106), fill=(229, 229, 234), width=2)
    ld.text((X1 - 80, by1 - 140), "12h", font=font(22), fill=GREY)
    # most used
    ld.rounded_rectangle((X0, 380, X1, 715), 30, fill=CARD)
    ld.text((X0 + 34, 396), "MOST USED", font=font(26, "Semibold"), fill=GREY)
    top = max(minutes(a_[2]) for a_ in ph["apps"])
    for k, (em, name, dur, col, *sub) in enumerate(ph["apps"]):
        rt = ph["row_t"][k]
        if t < rt:
            break
        ra = ease((t - rt) / 0.35)
        y = 440 + k * 68
        ic = Image.new("RGBA", (58, 58), (0, 0, 0, 0))
        ImageDraw.Draw(ic).rounded_rectangle((0, 0, 57, 57), 14, fill=tuple(col))
        comp(ic, emoji(em, 38), 10, 10)
        comp(layer, ic, X0 + 34 - (1 - ra) * 40, y)
        nf = font(32, "Semibold")
        nx = X0 + 112
        ld.text((nx, y - 2), name, font=nf, fill=INK)
        if sub:
            draw_rich(layer, nx + 8 + nf.getlength(name), y + 3, wrap(sub[0], font(25), 400)[:1], font(25), GREY, 30)
        tf = font(30)
        shown = hm(minutes(dur) * ease((t - rt) / 0.8))
        ld.text((X1 - 34 - tf.getlength(shown), y), shown, font=tf, fill=GREY)
        bl = (X1 - 34 - nx) * minutes(dur) / top * ease((t - rt - 0.1) / 0.7)
        ld.rounded_rectangle((nx, y + 42, nx + max(12, bl), y + 52), 5, fill=tuple(col))
    if a < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v, a=a: int(v * a)))
    comp(frame, layer, 0, 245)
    # dropdown, under the pill
    dd = s.get("dropdown")
    if dd and dd["t"] <= t < dd["until"]:
        k = ease_out_back(min(1, (t - dd["t"]) / 0.25))
        menu = Image.new("RGBA", (560, 230), (0, 0, 0, 0))
        md = ImageDraw.Draw(menu)
        md.rounded_rectangle((0, 8, 559, 229), 28, fill=(0, 0, 0, 40))
        md.rounded_rectangle((0, 0, 559, 220), 28, fill=(250, 250, 252))
        for i, opt in enumerate(dd["options"]):
            y = 20 + i * 100
            if t >= dd["tap"] and i == dd["pick"]:
                md.rounded_rectangle((12, y - 6, 547, y + 82), 20, fill=(222, 235, 255))
            md.text((40, y + 14), opt, font=font(40, "Semibold" if i == dd["pick"] else "Regular"), fill=INK)
            if (i == 0 and t < dd["tap"]) or (i == dd["pick"] and t >= dd["tap"]):
                md.text((480, y + 12), "✓", font=font(42, "Bold"), fill=BLUE)
        menu = menu.resize((560, max(1, int(230 * k))))
        comp(frame, menu, X1 - 560, 232)
    # reaction window
    cur = [c for c in P["cats"] if c["t"] <= t < c["until"]]
    if cur:
        c = cur[-1]
        win = cat_window(c["bg"], c["cat"].at(t - c["t"]), WIN[2], WIN[3], fit=c.get("fit", 0.95), r=36)
        wa = ease((t - c["t"]) / 0.25)
        if wa < 1:
            win.putalpha(win.getchannel("A").point(lambda v, wa=wa: int(v * wa)))
        comp(frame, win, WIN[0], WIN[1])
        comp(frame, c["chip"], WIN[0] + 24, WIN[1] + 22)
        if c.get("line") and t >= c.get("line_t", c["t"] + 0.6):
            la = ease_out_back(min(1, (t - c.get("line_t", c["t"] + 0.6)) / 0.3))
            lf = font(38, "Semibold")
            lines = wrap(c["line"], lf, 560)
            bw_ = max(sum(x[2] for x in ln) for ln in lines) + 60
            bh = 50 * len(lines) + 34
            bub = Image.new("RGBA", (int(bw_) + 20, bh + 10), (0, 0, 0, 0))
            bd = ImageDraw.Draw(bub)
            bd.rounded_rectangle((0, 6, bw_, bh + 6), 30, fill=(0, 0, 0, 50))
            bd.rounded_rectangle((0, 0, bw_, bh), 30, fill=(255, 255, 255))
            draw_rich(bub, 30, 16, lines, lf, INK, 50)
            if la < 1:
                bub = bub.resize((max(1, int(bub.width * la)), max(1, int(bub.height * la))))
            comp(frame, bub, WIN[0] + WIN[2] - bub.width - 16, WIN[1] + 86)
    # Screen Time notification for the ending, over the title
    b = s.get("banner")
    if b and t >= b["t"]:
        k = ease_out_back(min(1, (t - b["t"]) / 0.35))
        cw = X1 - X0
        bf = font(38)
        lines = wrap(b["body"], bf, cw - 180)
        hgt = 100 + 50 * len(lines)
        cardim = Image.new("RGBA", (cw, hgt + 12), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cardim)
        cd.rounded_rectangle((0, 10, cw - 1, hgt + 10), 44, fill=(0, 0, 0, 60))
        cd.rounded_rectangle((0, 0, cw - 1, hgt), 44, fill=(250, 250, 252))
        cd.rounded_rectangle((28, 28, 108, 108), 22, fill=(88, 86, 214))
        comp(cardim, emoji("⏳", 50), 43, 43)
        cd.text((134, 26), b["app"].upper(), font=font(30, "Semibold"), fill=GREY)
        cd.text((cw - 36 - font(30).getlength(b["when"]), 26), b["when"], font=font(30), fill=GREY)
        draw_rich(cardim, 134, 68, lines, bf, INK, 50)
        comp(frame, cardim, X0, -hgt - 20 + (hgt + 180) * k)
