"""Shopping cart: a checkout page where coupon codes keep failing, items get
added to qualify, and fees pile on. The coupon box types each code, the reply
shows under it, and the to-pay total counts to its new value. A cat reacts below.

Script: `start` (first cart rows) and `events` ({gap, add: {emoji, name, price,
note?, fee?}} or {gap, code, reply, ok?, discount?}), `cats` ({at, clip, start,
dur?, loop?, bg, who}). Layout stays inside engine/safe_zone.py.
"""
from PIL import Image, ImageDraw

from chat_render import W, H, font, emoji, comp, wrap, draw_rich, line_w, tone, click, ease_out_back
from simple_render import Cat, cat_window, window_bg, name_chip, ease, status_bar, ding

BG = (244, 245, 248)
INK, GREY = (28, 30, 38), (112, 116, 128)
RED, GREEN, BRAND = (214, 48, 49), (16, 150, 72), (252, 128, 25)
X0, X1 = 60, 1020
LIST_Y0, LIST_Y1, ROW_H = 290, 700, 70
CAT_X, CAT_Y, CAT_W, CAT_H = 60, 1004, 840, 406
TYPE = 0.09                                       # seconds per typed character


def err():
    return tone(300, 180, 0.22, 0.25, 9)


def PLAN(s, slug):
    t, track, evs = 1.2, [], []
    rows = [dict(r, t=-1) for r in s["start"]]
    disc = 0
    for e in s["events"]:
        t += e.get("gap", 2.6)
        e = dict(e, t=t)
        if "add" in e:
            rows.append(dict(e["add"], t=t))
            track.append((t, tone(700, 1050, 0.08, 0.18, 25) if not e["add"].get("fee") else tone(1200, 900, 0.1, 0.16, 20)))
        else:
            e["t_res"] = t + len(e["code"]) * TYPE + 0.5
            for k in range(len(e["code"])):
                track.append((t + k * TYPE, click(0.12)))
            track.append((e["t_res"], ding() if e.get("ok") else err()))
            if e.get("ok"):
                disc = e.get("discount", 0)
            t = e["t_res"]
        e["disc"] = disc
        evs.append(e)
    end_t = t + s.get("hold", 4.0)
    marks = [e.get("t_res", e["t"]) for e in evs]
    cats = []
    for i, c in enumerate(s["cats"]):
        t0 = 0.0 if c["at"] < 0 else marks[c["at"]]
        t1 = end_t if i + 1 == len(s["cats"]) else marks[s["cats"][i + 1]["at"]]
        cat = Cat(slug, f"cat{i:02d}", c["clip"], c["start"], c.get("dur", t1 - t0 + 0.2), CAT_H)
        cats.append(dict(c, t0=t0, t1=t1, cat=cat, bg=window_bg(c.get("bg", "home.jpg"), CAT_W, CAT_H),
                         chip=name_chip(c.get("who", "you"))))
        if c.get("loop"):
            k = t0
            while k < t1 - 0.5:
                track.append((k + 0.1, cat.audio(min(cat.dur, t1 - k)) * 0.8)); k += 2 * cat.dur + 1.2
        else:
            track.append((t0 + 0.1, cat.audio(min(cat.dur, t1 - t0))))
    return dict(rows=rows, evs=evs, cats=cats), track, end_t


def inr(n):
    return "₹" + f"{n:,}"


def row_img(r):
    im = Image.new("RGBA", (X1 - X0, ROW_H - 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fee = r.get("fee")
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), 20, fill=(255, 248, 238) if fee else (255, 255, 255))
    comp(im, emoji(r["emoji"], 44), 18, 9)
    nf = font(34, "Semibold" if not fee else "Medium")
    d.text((80, 12), r["name"], font=nf, fill=INK)
    if r.get("note"):
        x = 80 + nf.getlength(r["name"]) + 14
        d.text((x, 13), r["note"], font=font(32, "Semibold"), fill=RED if fee else GREY)
    pf = font(36, "Bold")
    p = inr(r["price"])
    d.text((im.width - 24 - pf.getlength(p), 11), p, font=pf, fill=INK)
    return im


_R = {}


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    status_bar(d, s.get("clock", "11:48"), INK)
    pf = font(46, "Bold")
    y = 162
    for ln in wrap(s["pov"], pf, X1 - X0 - 40):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, INK, 56); y += 56
    d.text((X0 + 16, 232), "checkout", font=font(40, "Bold"), fill=INK)
    rows = [r for r in P["rows"] if r["t"] <= t]
    n = len(rows)
    cnt = f"{n} item{'s' if n != 1 else ''}"
    d.text((X1 - 16 - font(30).getlength(cnt), 240), cnt, font=font(30), fill=GREY)
    # rows, newest at the bottom, scrolling up when the list is full
    fit = (LIST_Y1 - LIST_Y0) // ROW_H
    first = max(0, n - fit)
    y = LIST_Y0
    for i, r in enumerate(rows[first:]):
        key = id(r)
        if key not in _R:
            _R[key] = row_img(r)
        im = _R[key]
        age = t - r["t"]
        if r["t"] >= 0 and age < 0.3:
            k = ease_out_back(age / 0.3)
            im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v, a=min(1, age / 0.15): int(v * a)))
            comp(frame, im, X0 + (1 - k) * 60, y)
        else:
            comp(frame, im, X0, y)
        y += ROW_H
    # coupon box
    codes = [e for e in P["evs"] if "code" in e and e["t"] <= t]
    d.rounded_rectangle((X0, 716, X1, 796), 22, fill=(255, 255, 255), outline=(220, 222, 228), width=3)
    comp(frame, emoji("🏷️", 40), X0 + 20, 736)
    cf = font(38, "Bold")
    if codes:
        e = codes[-1]
        nn = min(len(e["code"]), int((t - e["t"]) / TYPE) + 1)
        d.text((X0 + 80, 734), e["code"][:nn], font=cf, fill=INK)
        if nn < len(e["code"]) and int(t * 4) % 2 == 0:
            cx = X0 + 82 + cf.getlength(e["code"][:nn])
            d.line((cx, 738, cx, 780), fill=BRAND, width=3)
    else:
        d.text((X0 + 80, 736), "enter coupon code", font=font(36), fill=(170, 172, 180))
    af = font(36, "Bold")
    d.text((X1 - 30 - af.getlength("APPLY"), 736), "APPLY", font=af, fill=BRAND)
    if codes and t >= codes[-1]["t_res"]:
        e = codes[-1]
        rf = font(34, "Semibold")
        a = ease((t - e["t_res"]) / 0.25)
        lay = Image.new("RGBA", (X1 - X0, 100), (0, 0, 0, 0))
        mark = "✅ " if e.get("ok") else "❌ "
        draw_rich(lay, 6, 0, wrap(mark + e["reply"], rf, X1 - X0 - 20)[:2], rf, GREEN if e.get("ok") else RED, 44)
        lay.putalpha(lay.getchannel("A").point(lambda v, a=a: int(v * a)))
        dx = 0
        if not e.get("ok") and t - e["t_res"] < 0.35:            # shake on failure
            import math
            dx = math.sin((t - e["t_res"]) * 60) * 10 * (1 - (t - e["t_res"]) / 0.35)
        comp(frame, lay, X0 + dx, 806)
    # to pay bar
    shown = [e for e in P["evs"] if e.get("t_res", e["t"]) <= t]
    disc = shown[-1]["disc"] if shown else 0
    total = sum(r["price"] for r in rows) - disc
    prev_rows = [r for r in P["rows"] if r["t"] <= t - 0.5]
    prev_disc = ([e for e in P["evs"] if e.get("t_res", e["t"]) <= t - 0.5] or [{"disc": 0}])[-1]["disc"]
    prev_total = sum(r["price"] for r in prev_rows) - prev_disc
    last_change = max([r["t"] for r in rows] + [e.get("t_res", e["t"]) for e in shown] + [0])
    k = ease((t - last_change) / 0.5)
    shown_total = round(prev_total + (total - prev_total) * k) if t - last_change < 0.5 else total
    d.rounded_rectangle((X0, 896, X1, 990), 26, fill=(255, 255, 255))
    d.text((X0 + 30, 922), "to pay", font=font(36, "Semibold"), fill=GREY)
    tf = font(60, "Bold")
    d.text((X0 + 170, 908), inr(shown_total), font=tf, fill=INK)
    if disc:
        sav = f"you saved {inr(disc)}"
        sf = font(32, "Bold")
        sw = sf.getlength(sav) + 36
        d.rounded_rectangle((X1 - 24 - sw, 920, X1 - 24, 966), 23, fill=(222, 246, 230))
        d.text((X1 - 6 - sw, 925), sav, font=sf, fill=GREEN)
    ok = [e for e in P["evs"] if e.get("ok") and e.get("t_res", 0) <= t]
    if ok and t - ok[-1]["t_res"] < 2.2:                       # confetti over the list
        age = t - ok[-1]["t_res"]
        for i in range(10):
            ex = X0 + 40 + (i * 89) % (X1 - X0 - 120)
            ey = 300 + age * 260 + (i % 3) * 50
            comp(frame, emoji(["🎉", "🎊", "✨"][i % 3], 56), ex, ey)
    cur = [c for c in P["cats"] if c["t0"] <= t][-1]
    win = cat_window(cur["bg"], cur["cat"].at(t - cur["t0"], loop=cur.get("loop", False)), CAT_W, CAT_H)
    comp(frame, win, CAT_X, CAT_Y)
    comp(frame, cur["chip"], CAT_X + 24, CAT_Y + 22)
