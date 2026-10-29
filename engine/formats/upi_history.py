"""UPI history: a payments app's transaction list fills in one payment at a
time, newest on top, while the balance card counts down. A cat reacts below.

Script: `start_balance`, `rows` ({gap, emoji, name, when, note?, amount,
declined?}) and `cats` ({at_row, clip, start, dur?, loop?, bg, who}).
"""
from PIL import Image, ImageDraw

from chat_render import W, H, font, emoji, comp, wrap, draw_rich, line_w, tone, ease_out_back
from simple_render import Cat, cat_window, window_bg, name_chip, ease, status_bar, ding, tick

BG = (246, 245, 250)
PURPLE, INK, GREY = (95, 37, 159), (28, 28, 34), (118, 118, 128)
RED, GREEN = (214, 48, 49), (16, 150, 72)
LIST_Y, ROW_H = 456, 118
CAT_X, CAT_Y, CAT_W, CAT_H = 60, 1010, 840, 404     # inside the Shorts safe zone (engine/safe_zone.py)


def rupees(n):
    s = f"{abs(int(n)):,}"
    if abs(n) >= 1000:                      # indian grouping: 1,00,000
        digits = str(abs(int(n)))
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return "₹" + s


def pay_sound():
    return tone(880, 880, 0.06, 0.12, 40)


def decline_sound():
    return tone(420, 220, 0.3, 0.25, 8)


def PLAN(s, slug):
    t, track, rows = 1.4, [], []
    bal = s["start_balance"]
    for r in s["rows"]:
        t += r.get("gap", 2.2)
        if not r.get("declined"):
            bal += r["amount"]
        rows.append(dict(r, t=t, balance=bal))
        track.append((t, ding() * 0.7 if r["amount"] > 0 and not r.get("declined")
                      else decline_sound() if r.get("declined") else pay_sound()))
    end_t = t + s.get("hold", 3.5)
    cats = []
    for i, c in enumerate(s["cats"]):
        t0 = 0.0 if c["at_row"] < 0 else rows[c["at_row"]]["t"]
        t1 = end_t if i == len(s["cats"]) - 1 else rows[s["cats"][i + 1]["at_row"]]["t"]
        cat = Cat(slug, f"cat{i:02d}", c["clip"], c["start"], c.get("dur", t1 - t0 + 0.2), CAT_H)
        cats.append(dict(c, t0=t0, t1=t1, cat=cat, bg=window_bg(c.get("bg", "home.jpg"), CAT_W, CAT_H),
                         chip=name_chip(c.get("who", "you"))))
        if c.get("loop"):
            k = t0
            while k < t1 - 0.5:
                track.append((k + 0.1, cat.audio(min(cat.dur, t1 - k)) * 0.8)); k += 2 * cat.dur + 1.5
        else:
            track.append((t0 + 0.1, cat.audio(min(cat.dur, t1 - t0))))
    return dict(rows=rows, cats=cats), track, end_t


def row_img(r):
    im = Image.new("RGBA", (W - 120, ROW_H - 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), 28, fill=(255, 255, 255))
    d.ellipse((22, 13, 102, 93), fill=(239, 232, 250))
    comp(im, emoji(r["emoji"], 50), 37, 28)
    nf, sf, af = font(38, "Semibold"), font(29), font(42, "Bold")
    d.text((124, 12), r["name"], font=nf, fill=INK)
    sub = r["when"] + (f" · {r['note']}" if r.get("note") else "")
    draw_rich(im, 124, 60, wrap(sub, sf, im.width - 420)[:1], sf, GREY, 36)
    amt = ("+" if r["amount"] > 0 else "-") + rupees(r["amount"])
    if r.get("declined"):
        aw = af.getlength(amt)
        x = im.width - 30 - aw
        d.text((x, 10), amt, font=af, fill=(170, 170, 178))
        d.line((x - 4, 36, x + aw + 4, 36), fill=(170, 170, 178), width=4)
        pf = font(26, "Bold")
        lab = "DECLINED"
        pw = pf.getlength(lab) + 28
        d.rounded_rectangle((im.width - 30 - pw, 62, im.width - 30, 98), 18, fill=(253, 228, 228))
        d.text((im.width - 16 - pw, 66), lab, font=pf, fill=RED)
    else:
        col = GREEN if r["amount"] > 0 else INK
        d.text((im.width - 30 - af.getlength(amt), 24), amt, font=af, fill=col)
    return im


_ROWS = {}


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    d.rectangle((0, 0, W, 410), fill=PURPLE)
    status_bar(d, s.get("clock", "6:14"), (255, 255, 255))
    pf = font(48, "Bold")
    y = 160
    for ln in wrap(s["pov"], pf, W - 140):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, (255, 255, 255), 60); y += 60
    shown = [r for r in P["rows"] if r["t"] <= t]
    # balance card, counting from the previous balance to the new one
    prev = shown[-2]["balance"] if len(shown) > 1 else s["start_balance"]
    cur_b = shown[-1]["balance"] if shown else s["start_balance"]
    k = ease((t - shown[-1]["t"]) / 0.6) if shown else 1
    bal = prev + (cur_b - prev) * k
    d.rounded_rectangle((60, 236, W - 60, 400), 36, fill=(255, 255, 255))
    d.text((96, 254), "bank balance · a/c xx4417", font=font(32, "Medium"), fill=GREY)
    bf = font(88, "Bold")
    col = RED if bal < 100 else INK
    d.text((92, 290), rupees(round(bal)), font=bf, fill=col)
    d.text((W - 96 - font(30).getlength(s.get("payday", "salary in 7 days")), 262),
           s.get("payday", "salary in 7 days"), font=font(30), fill=GREY)
    d.text((66, 412), "history", font=font(36, "Bold"), fill=INK)
    # list: newest on top, older rows pushed down
    y = LIST_Y
    for i, r in enumerate(reversed(shown)):
        key = id(r)
        if key not in _ROWS:
            _ROWS[key] = row_img(r)
        im = _ROWS[key]
        age = t - r["t"]
        if i == 0 and age < 0.4:
            kk = ease_out_back(age / 0.4)
            a = min(1, age / 0.2)
            im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v, a=a: int(v * a)))
            comp(frame, im, 60, y - (1 - kk) * 50)
            y += int(ROW_H * min(1, kk))
            continue
        if y > CAT_Y - 50:
            break
        if y + ROW_H > CAT_Y - 10:
            a = max(0.0, (CAT_Y - 10 - y) / ROW_H)
            im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, im, 60, y)
        y += ROW_H
    cur = [c for c in P["cats"] if c["t0"] <= t][-1]
    win = cat_window(cur["bg"], cur["cat"].at(t - cur["t0"], loop=cur.get("loop", False)), CAT_W, CAT_H)
    comp(frame, win, CAT_X, CAT_Y)
    comp(frame, cur["chip"], CAT_X + 24, CAT_Y + 22)
