"""reviews: a Google-Maps-style place page whose reviews arrive one by one.

The header photo is a video of whoever is posting (each `review` / `reply` event
names a clip), the rating ticks as reviews land, and new cards slide in at the
top of the list. A `reply` is the owner answering one earlier review.
"""
from PIL import Image, ImageDraw

from simple_render import Cat, cat_window, window_bg, name_chip, status_bar, ease, ding, tick, whoosh
from chat_render import W, H, font, emoji, comp, wrap, draw_rich, avatar, ease_out_back

BG = (255, 255, 255)
INK, GREY, STAR, BLUE = (32, 33, 36), (95, 99, 104), (251, 188, 4), (26, 115, 232)
# Shorts safe area (engine/safe_zone.py): x 60..1020, y 150..1420, and x <= 900 below y 1000
X0, X1, RAIL_X, TOP, BOTTOM = 60, 1020, 900, 150, 1420
HEAD_Y, HEAD_H, LIST_Y = 150, 420, 868


def stars(d, x, y, n, size=30, total=5):
    for i in range(total):
        cx, cy, r = x + i * (size + 6) + size / 2, y + size / 2, size / 2
        pts = []
        import math
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = r if k % 2 == 0 else r * 0.45
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        d.polygon(pts, fill=STAR if i < n else (218, 220, 224))


def review_card(e, people):
    cw = RAIL_X - X0
    tf = font(37)
    lines = wrap(e["text"], tf, cw - 40)
    if e["type"] == "reply":
        quote = wrap(f"replying to {people[e['target_who']]['name']}", font(30, "Semibold"), cw)[:1]
        h = 70 + 48 + 50 * len(lines) + 40
        im = Image.new("RGBA", (cw, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, cw - 1, h - 1), 26, fill=(241, 243, 244))
        d.text((30, 24), "Response from the owner", font=font(34, "Semibold"), fill=INK)
        d.text((cw - 30 - font(30).getlength("just now"), 26), "just now", font=font(30), fill=GREY)
        draw_rich(im, 30, 74, quote, font(30, "Semibold"), BLUE, 40)
        draw_rich(im, 30, 122, lines, tf, INK, 50)
        return im
    p = people[e["who"]]
    h = 100 + 52 + 50 * len(lines) + 34
    im = Image.new("RGBA", (cw, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, cw - 1, h - 1), 26, fill=(255, 255, 255), outline=(232, 234, 237), width=2)
    comp(im, p["av"], 26, 24)
    d.text((124, 22), p["name"], font=font(36, "Semibold"), fill=INK)
    d.text((124, 66), p.get("meta", "Local Guide · 3 reviews"), font=font(28), fill=GREY)
    stars(d, 28, 116, e["stars"], 32)
    d.text((228, 112), e.get("when", "just now"), font=font(30), fill=GREY)
    draw_rich(im, 28, 162, lines, tf, INK, 50)
    return im


def PLAN(s, slug):
    people = s["people"]
    for i, (k, p) in enumerate(people.items()):
        p["av"] = avatar(p["avatar"], 80, i)
    evs, track, heads = s["events"], [], []
    for i, e in enumerate(evs):
        e["card"] = review_card(e, people)
        track.append((e["t"], ding() if e["type"] == "reply" else tick()))
    end_t = s["end"]
    for i, h in enumerate(s["header"]):
        until = s["header"][i + 1]["t"] if i + 1 < len(s["header"]) else end_t
        h = dict(h, until=until)
        h["cat"] = Cat(slug, f"head{i:02d}", h["clip"], h["start"], until - h["t"], HEAD_H)
        h["bg"] = window_bg(h.get("bg", "kitchen.jpg"), X1 - X0, HEAD_H, blur=3)
        h["chip"] = name_chip(h["label"])
        if h.get("sound", True):
            track.append((h["t"] + 0.1, h["cat"].audio(min(h["cat"].dur, h.get("sound_dur", 3.0))) * h.get("vol", 1.0)))
        track.append((h["t"], whoosh()))
        heads.append(h)
    return dict(evs=evs, heads=heads), track, end_t


def DRAW(frame, t, s, P):
    hd = [h for h in P["heads"] if h["t"] <= t]
    h = hd[-1] if hd else P["heads"][0]
    win = cat_window(h["bg"], h["cat"].at(t - h["t"]), X1 - X0, HEAD_H, fit=h.get("fit", 0.95), r=36)
    if len(hd) > 1 and t - h["t"] < 0.25:                    # quick flash between photos
        a = 1 - (t - h["t"]) / 0.25
        win.alpha_composite(Image.new("RGBA", win.size, (255, 255, 255, int(200 * a))))
    comp(frame, win, X0, HEAD_Y)
    comp(frame, h["chip"], X0 + 24, HEAD_Y + HEAD_H - 84)
    d = ImageDraw.Draw(frame)
    status_bar(d, s.get("clock", "8:15"), INK)
    # place info
    y = HEAD_Y + HEAD_H + 18
    d.text((X0 + 24, y), s["place"], font=font(56, "Bold"), fill=INK)
    shown = [e for e in P["evs"] if e["t"] <= t]
    rating = shown[-1].get("rating", s["rating"]) if shown else s["rating"]
    count = s["count"] + sum(1 for e in shown if e["type"] == "review")
    rf = font(34)
    d.text((X0 + 24, y + 78), f"{rating:.1f}", font=rf, fill=INK)
    stars(d, X0 + 86, y + 82, round(rating), 30)
    d.text((X0 + 282, y + 78), f"({count:,})", font=rf, fill=GREY)
    d.text((X0 + 24, y + 126), s["subtitle"], font=font(32), fill=GREY)
    ty = y + 186
    for i, tab in enumerate(("Overview", "Reviews", "Photos", "About")):
        x = X0 + 24 + i * 226
        d.text((x, ty), tab, font=font(32, "Semibold"), fill=BLUE if i == 1 else GREY)
        if i == 1:
            d.rounded_rectangle((x, ty + 48, x + font(32, "Semibold").getlength(tab), ty + 54), 3, fill=BLUE)
    d.line((X0, ty + 56, X1, ty + 56), fill=(232, 234, 237), width=2)
    # reviews list, newest on top, faded out before the caption strip
    lay = Image.new("RGBA", (W, BOTTOM - LIST_Y), (0, 0, 0, 0))
    yy = 0
    for i, e in enumerate(shown[::-1]):
        c = e["card"]
        age = t - e["t"]
        if i == 0 and age < 0.4:
            k = ease_out_back(age / 0.4)
            c2 = c.copy()
            c2.putalpha(c2.getchannel("A").point(lambda v, a=min(1, age / 0.25): int(v * a)))
            comp(lay, c2, X0, yy - (1 - k) * 50)
            yy += int((c.height + 20) * min(1, k))
            continue
        if yy > lay.height:
            break
        comp(lay, c, X0, yy)
        yy += c.height + 20
    fade = 70
    a = lay.getchannel("A")
    ramp = Image.linear_gradient("L").rotate(180).resize((W, fade))
    mask = Image.new("L", lay.size, 255); mask.paste(ramp, (0, lay.height - fade))
    from PIL import ImageChops
    lay.putalpha(ImageChops.multiply(a, mask))
    comp(frame, lay, 0, LIST_Y)
