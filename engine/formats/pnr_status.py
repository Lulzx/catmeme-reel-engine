"""PNR status: a railway PNR screen refreshed again and again before a trip
home. The waitlist number crawls, the refresh counter climbs, a cat refreshes
below, and a message can drop in at the end.

Script: `train` (pnr, name, route, dep), `checks` ({gap, when, count, status,
chart?}), optional `message` ({gap, from, body}) and `cats` ({at, clip,
start, dur?, loop?, bg, who}); `at` indexes checks, len(checks) = the message.
"""
import math
from PIL import Image, ImageDraw

from chat_render import W, H, font, emoji, comp, wrap, draw_rich, line_w, click, ease_out_back
from simple_render import Cat, cat_window, window_bg, name_chip, ease, status_bar, ding, tick, whoosh

BG = (233, 238, 246)
NAVY, INK, GREY = (16, 42, 102), (26, 30, 40), (110, 116, 130)
ORANGE, GREEN = (242, 120, 30), (22, 150, 70)
CAT_X, CAT_Y, CAT_W, CAT_H = 60, 960, 840, 452      # inside the Shorts safe zone (engine/safe_zone.py)
SPIN = 0.9                                   # seconds the refresh spinner turns


def PLAN(s, slug):
    t, track, checks = 1.2, [], []
    for c in s["checks"]:
        t += c.get("gap", 3.2)
        checks.append(dict(c, t=t))
        track.append((t, click(0.25)))
        track.append((t + SPIN, tick() * 2 if not c.get("chart") else ding()))
    msg = None
    if s.get("message"):
        t += s["message"].get("gap", 3.0)
        msg = dict(s["message"], t=t)
        track.append((t, ding()))
    end_t = t + s.get("hold", 4.0)
    marks = [c["t"] for c in checks] + ([msg["t"]] if msg else [])
    cats = []
    for i, c in enumerate(s["cats"]):
        t0 = 0.0 if c["at"] < 0 else marks[c["at"]] + (SPIN if c["at"] < len(checks) else 0)
        nxt = s["cats"][i + 1]["at"] if i + 1 < len(s["cats"]) else None
        t1 = end_t if nxt is None else marks[nxt] + (SPIN if nxt < len(checks) else 0)
        cat = Cat(slug, f"cat{i:02d}", c["clip"], c["start"], c.get("dur", t1 - t0 + 0.2), CAT_H)
        cats.append(dict(c, t0=t0, t1=t1, cat=cat, bg=window_bg(c.get("bg", "station.jpg"), CAT_W, CAT_H),
                         chip=name_chip(c.get("who", "you"))))
        if c.get("loop"):
            k = t0
            while k < t1 - 0.5:
                track.append((k + 0.1, cat.audio(min(cat.dur, t1 - k)) * 0.7)); k += 2 * cat.dur + 1.0
        else:
            track.append((t0 + 0.1, cat.audio(min(cat.dur, t1 - t0))))
    return dict(checks=checks, msg=msg, cats=cats), track, end_t


def card(d, box):
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x0, y0 + 6, x1, y1 + 6), 34, fill=(0, 0, 0, 18))
    d.rounded_rectangle(box, 34, fill=(255, 255, 255))


def refresh_icon(d, cx, cy, r, ang, col):
    d.arc((cx - r, cy - r, cx + r, cy + r), ang + 40, ang + 330, fill=col, width=7)
    a = math.radians(ang + 330)
    x, y = cx + r * math.cos(a), cy + r * math.sin(a)
    d.polygon([(x + 12 * math.cos(a), y + 12 * math.sin(a)), (x - 12 * math.cos(a), y - 12 * math.sin(a)),
               (x + 16 * math.cos(a + math.pi / 2), y + 16 * math.sin(a + math.pi / 2))], fill=col)


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    tr = s["train"]
    d.rectangle((0, 0, W, 236), fill=NAVY)
    status_bar(d, s.get("clock", "12:10"), (255, 255, 255))
    pf = font(48, "Bold")
    pf = font(46, "Bold")
    y = 162
    for ln in wrap(s["pov"], pf, W - 140):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, (255, 255, 255), 60); y += 60
    # train card
    card(d, (60, 252, W - 60, 452))
    d.text((96, 270), f"PNR {tr['pnr']}", font=font(32, "Semibold"), fill=GREY)
    d.text((W - 96 - font(32, "Semibold").getlength(tr["class"]), 270), tr["class"], font=font(32, "Semibold"), fill=GREY)
    d.text((96, 312), tr["name"], font=font(42, "Bold"), fill=INK)
    rf = font(52, "Bold")
    a, b = tr["route"]
    d.text((96, 372), a, font=rf, fill=NAVY)
    ax = 116 + rf.getlength(a)
    d.line((ax, 405, ax + 120, 405), fill=GREY, width=4)
    d.polygon([(ax + 120, 393), (ax + 140, 405), (ax + 120, 417)], fill=GREY)
    d.text((ax + 160, 372), b, font=rf, fill=NAVY)
    d.text((W - 96 - font(32).getlength(tr["dep"]), 386), tr["dep"], font=font(32), fill=GREY)
    # status card
    done = [c for c in P["checks"] if c["t"] + SPIN <= t]
    spinning = [c for c in P["checks"] if c["t"] <= t < c["t"] + SPIN]
    card(d, (60, 470, W - 60, 800))
    d.text((96, 488), f"passenger 1 · booked {s['booked']}", font=font(32, "Medium"), fill=GREY)
    d.text((96, 528), "current status", font=font(36, "Semibold"), fill=INK)
    sf = font(130, "Bold")
    if spinning:
        msg_ = "checking…"
        f2 = font(80, "Semibold")
        d.text(((W - f2.getlength(msg_)) / 2, 612), msg_, font=f2, fill=(190, 194, 205))
    elif done:
        c = done[-1]
        st = c["status"]
        cnf = c.get("chart")
        age = t - c["t"] - SPIN
        k = ease_out_back(min(1, age / 0.35))
        f = sf if not cnf else font(110, "Bold")
        img = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
        ImageDraw.Draw(img).text(((W - f.getlength(st)) / 2, 10), st, font=f, fill=GREEN if cnf else ORANGE)
        sc = 0.7 + 0.3 * k
        img = img.resize((int(W * sc), int(200 * sc)))
        comp(frame, img, (W - img.width) / 2, 568 + (200 - img.height) / 2)
        chip = "chart prepared" if cnf else "chart not prepared"
        cf = font(30, "Semibold")
        cw = cf.getlength(chip) + 40
        d.rounded_rectangle(((W - cw) / 2, 738, (W + cw) / 2, 784), 23,
                            fill=(220, 245, 228) if cnf else (255, 236, 220))
        d.text(((W - cw) / 2 + 20, 744), chip, font=cf, fill=GREEN if cnf else ORANGE)
        if cnf and age < 2.5:
            for i in range(10):                 # confetti
                ex = 120 + (i * 97) % (W - 300)
                ey = 500 + age * 300 + (i % 3) * 40
                comp(frame, emoji(["🎉", "🎊", "✨"][i % 3], 60), ex, ey)
    last = (spinning or done or [None])[-1]
    info = f"last checked {last['when']}" if last else "not checked yet"
    cnt = f"refreshed {last['count']} time{'s' if last['count'] != 1 else ''}" if last else ""
    d.text((86, 826), info, font=font(32), fill=GREY)
    d.text((86, 870), cnt, font=font(34, "Bold"), fill=INK)
    # refresh button
    pressed = spinning and t - spinning[-1]["t"] < 0.15
    bx0, by0, bx1, by1 = W - 390, 822, W - 60, 912
    off = 4 if pressed else 0
    d.rounded_rectangle((bx0, by0 + 6, bx1, by1 + 6), 50, fill=(180, 80, 10))
    d.rounded_rectangle((bx0, by0 + off, bx1, by1 + off), 50, fill=ORANGE)
    ang = ((t - spinning[-1]["t"]) * 540) if spinning else 0
    refresh_icon(d, bx0 + 66, by0 + 45 + off, 24, ang, (255, 255, 255))
    d.text((bx0 + 116, by0 + 21 + off), "REFRESH", font=font(42, "Bold"), fill=(255, 255, 255))
    # cat window
    cur = [c for c in P["cats"] if c["t0"] <= t][-1]
    win = cat_window(cur["bg"], cur["cat"].at(t - cur["t0"], loop=cur.get("loop", False)), CAT_W, CAT_H)
    comp(frame, win, CAT_X, CAT_Y)
    comp(frame, cur["chip"], CAT_X + 24, CAT_Y + 22)
    # message banner
    m = P["msg"]
    if m and t >= m["t"]:
        k = ease_out_back(min(1, (t - m["t"]) / 0.35))
        bf = font(40)
        lines = wrap(m["body"], bf, W - 320)
        h = 120 + 52 * len(lines)
        cd = Image.new("RGBA", (W - 120, h + 10), (0, 0, 0, 0))
        dd = ImageDraw.Draw(cd)
        dd.rounded_rectangle((0, 8, W - 121, h + 8), 40, fill=(0, 0, 0, 60))
        dd.rounded_rectangle((0, 0, W - 121, h), 40, fill=(250, 250, 252))
        dd.rounded_rectangle((30, 30, 110, 110), 20, fill=(37, 211, 102))
        comp(cd, emoji("💬", 50), 45, 45)
        dd.text((136, 30), m["from"], font=font(40, "Semibold"), fill=INK)
        dd.text((W - 230, 34), "now", font=font(30), fill=GREY)
        draw_rich(cd, 136, 86, lines, bf, INK, 52)
        comp(frame, cd, 60, -h - 20 + (h + 180) * k)
