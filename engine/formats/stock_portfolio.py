"""Stock portfolio: Papa's trading app after a WhatsApp-uncle tip. The price
chart draws itself, every buy averages down, the P&L goes red, and the latest
message sits under the chart. A cat (Papa, or whoever is talking) reacts below.

Script: `stock`, `events` ({gap, clock, price?, buy?, feed?: {from, text,
kind?}}) and `cats` ({at, clip, start, dur?, loop?, bg, who}); `at` indexes
events, -1 = from the start. Layout stays inside engine/safe_zone.py.
"""
from PIL import Image, ImageDraw

from chat_render import W, H, font, emoji, comp, wrap, draw_rich, line_w, tone, ease_out_back
from simple_render import Cat, cat_window, window_bg, name_chip, ease, status_bar, ding, tick

BG = (12, 14, 20)
INK, GREY = (236, 238, 242), (138, 144, 158)
RED, GREEN = (240, 68, 68), (38, 196, 110)
X0, X1 = 60, 1020
CHART = (60, 430, 1020, 700)
CAT_X, CAT_Y, CAT_W, CAT_H = 60, 1004, 840, 406


def inr(n, sign=False):
    s = f"{abs(n):,.0f}"
    digits = s.replace(",", "")
    if len(digits) > 3:                       # indian grouping
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "+" if sign else "") + "₹" + s


def PLAN(s, slug):
    t, track, evs = 1.0, [], []
    qty, cost, price = 0, 0.0, s["stock"]["open"]
    for e in s["events"]:
        t += e.get("gap", 2.6)
        price = e.get("price", price)
        if e.get("buy"):
            qty += e["buy"]; cost += e["buy"] * price
        evs.append(dict(e, t=t, p=price, qty=qty, cost=cost))
        if e.get("buy"):
            track.append((t, tone(660, 990, 0.12, 0.2, 18)))
        elif "price" in e:
            track.append((t, tone(520, 300, 0.25, 0.18, 10)))
        if e.get("feed"):
            track.append((t + 0.05, ding() * 0.6))
    end_t = t + s.get("hold", 4.0)
    cats = []
    for i, c in enumerate(s["cats"]):
        t0 = 0.0 if c["at"] < 0 else evs[c["at"]]["t"]
        t1 = end_t if i + 1 == len(s["cats"]) else evs[s["cats"][i + 1]["at"]]["t"]
        cat = Cat(slug, f"cat{i:02d}", c["clip"], c["start"], c.get("dur", t1 - t0 + 0.2), CAT_H)
        cats.append(dict(c, t0=t0, t1=t1, cat=cat, bg=window_bg(c.get("bg", "livingroom.jpg"), CAT_W, CAT_H),
                         chip=name_chip(c.get("who", "papa"))))
        if c.get("loop"):
            k = t0
            while k < t1 - 0.5:
                track.append((k + 0.1, cat.audio(min(cat.dur, t1 - k)) * 0.8)); k += 2 * cat.dur + 1.2
        else:
            track.append((t0 + 0.1, cat.audio(min(cat.dur, t1 - t0))))
    return dict(evs=evs, cats=cats), track, end_t


def feed_card(f):
    kind = f.get("kind", "chat")
    bf = font(38)
    lines = wrap(f["text"], bf, X1 - X0 - 150)[:2]
    h = 70 + 48 * len(lines)
    im = Image.new("RGBA", (X1 - X0, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = {"chat": (22, 64, 48), "order": (30, 34, 46), "warn": (70, 24, 28)}[kind]
    d.rounded_rectangle((0, 0, im.width - 1, h - 1), 28, fill=fill)
    icon = {"chat": "💬", "order": "🧾", "warn": "⚠️"}[kind]
    comp(im, emoji(icon, 52), 26, 22)
    ff = font(32, "Semibold")
    draw_rich(im, 100, 16, wrap(f["from"], ff, im.width - 120)[:1], ff, (150, 230, 180) if kind == "chat" else GREY, 40)
    draw_rich(im, 100, 58, lines, bf, INK, 48)
    return im


_FEED = {}


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    st = s["stock"]
    status_bar(d, ([e["clock"] for e in P["evs"] if e["t"] <= t] or [s.get("clock", "9:14")])[-1], INK)
    pf = font(46, "Bold")
    y = 162
    for ln in wrap(s["pov"], pf, X1 - X0 - 40):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, INK, 56); y += 56
    shown = [e for e in P["evs"] if e["t"] <= t]
    cur = shown[-1] if shown else dict(p=st["open"], qty=0, cost=0.0, t=0)
    prev = shown[-2] if len(shown) > 1 else cur
    k = ease((t - cur["t"]) / 0.6)
    price = prev["p"] + (cur["p"] - prev["p"]) * k
    qty, cost = cur["qty"], cur["cost"]
    value = qty * price
    pnl = value - cost
    # portfolio card
    d.rounded_rectangle((X0, 240, X1, 416), 32, fill=(24, 27, 36))
    d.text((X0 + 36, 256), s.get("owner", "papa's portfolio"), font=font(32, "Medium"), fill=GREY)
    d.text((X0 + 36, 296), inr(value), font=font(78, "Bold"), fill=INK)
    if qty:
        pct = pnl / cost * 100 if cost else 0
        lab = f"{inr(pnl, True)}  ({pct:+.1f}%)"
        pf2 = font(38, "Bold")
        d.text((X1 - 36 - pf2.getlength(lab), 324), lab, font=pf2, fill=RED if pnl < 0 else GREEN)
    # chart: one point per priced event, newest segment drawing in
    pts = [st["open"]] + [e["p"] for e in shown if "price" in e]
    if shown and "price" in shown[-1] and k < 1:
        pts[-1] = pts[-2] + (pts[-1] - pts[-2]) * k
    lo, hi = st["low_axis"], st["high_axis"]
    cx0, cy0, cx1, cy1 = CHART
    n = max(len(s["events"]), 2)
    def xy(i, p):
        return cx0 + 20 + (cx1 - cx0 - 40) * i / n, cy1 - (p - lo) / (hi - lo) * (cy1 - cy0)
    by = xy(0, st["open"])[1]
    for x in range(cx0, cx1, 24):
        d.line((x, by, x + 12, by), fill=(70, 74, 88), width=2)
    xy_pts = [xy(i, p) for i, p in enumerate(pts)]
    col = RED if pts[-1] < st["open"] else GREEN
    if len(xy_pts) > 1:
        poly = xy_pts + [(xy_pts[-1][0], cy1), (xy_pts[0][0], cy1)]
        fill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(fill).polygon(poly, fill=col + (46,))
        frame.alpha_composite(fill)
        d.line(xy_pts, fill=col, width=7, joint="curve")
    ex, ey = xy_pts[-1]
    d.ellipse((ex - 11, ey - 11, ex + 11, ey + 11), fill=col)
    lab = inr(price)
    lf = font(34, "Bold")
    lx = min(ex + 18, X1 - lf.getlength(lab) - 4)
    d.text((lx, ey - 52 if ey > cy0 + 60 else ey + 14), lab, font=lf, fill=col)
    # holding row
    d.text((X0 + 6, 720), st["ticker"], font=font(36, "Bold"), fill=INK)
    avg = f"{qty} shares · avg {inr(cost / qty) if qty else '-'}"
    d.text((X1 - 6 - font(32).getlength(avg), 724), avg, font=font(32), fill=GREY)
    # latest message
    lastf = [e for e in shown if e.get("feed")]
    if lastf:
        e = lastf[-1]
        key = id(e)
        if key not in _FEED:
            _FEED[key] = feed_card(e["feed"])
        im = _FEED[key]
        age = t - e["t"]
        kk = ease_out_back(min(1, age / 0.35))
        y = 784 + (1 - kk) * 40
        if age < 0.2:
            im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v, a=age / 0.2: int(v * a)))
        comp(frame, im, X0, y)
    curc = [c for c in P["cats"] if c["t0"] <= t][-1]
    win = cat_window(curc["bg"], curc["cat"].at(t - curc["t0"], loop=curc.get("loop", False)), CAT_W, CAT_H)
    comp(frame, win, CAT_X, CAT_Y)
    comp(frame, curc["chip"], CAT_X + 24, CAT_Y + 22)
