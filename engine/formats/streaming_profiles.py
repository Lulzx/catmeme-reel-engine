"""streaming_profiles: a "who's watching?" profile picker, then each family member's
"continue watching" row gives them away.

Each `profiles` entry has a `t`: the picker comes back, the highlight lands on that
profile, then its page shows a header video, three posters and a `note`.
Layout keeps to the Shorts safe area (engine/safe_zone.py): posters end above
y 1000 or stay left of x 900, and nothing goes below y 1420.
"""
from PIL import Image, ImageDraw

from simple_render import Cat, cat_window, window_bg, name_chip, status_bar, ease, tick, whoosh, thunk
from chat_render import W, H, font, emoji, comp, wrap, draw_rich, avatar, ease_out_back

BG = (16, 16, 18)
WHITE, GREY, RED = (245, 245, 245), (160, 160, 165), (229, 9, 20)
X0, X1, RAIL_X, BOTTOM = 60, 1020, 900, 1420
HEAD_Y, HEAD_H = 160, 400
PICK = 0.9                                   # seconds the picker shows before a profile opens


def PLAN(s, slug):
    track = []
    profs = s["profiles"]
    for i, p in enumerate(profs):
        p["av"] = avatar(p["avatar"], 230, i)
        until = profs[i + 1]["t"] if i + 1 < len(profs) else s["end"]
        p["until"] = until
        p["cat"] = Cat(slug, f"prof{i:02d}", p["clip"], p["start"], until - p["t"] - PICK, HEAD_H)
        p["bg"] = window_bg(p.get("bg", "livingroom.jpg"), X1 - X0, HEAD_H, blur=4, dim=0.15)
        p["chip"] = name_chip(p["name"])
        track.append((p["t"], whoosh()))
        track.append((p["t"] + PICK - 0.2, thunk()))
        if p.get("sound", True):
            track.append((p["t"] + PICK, p["cat"].audio(min(p["cat"].dur, p.get("sound_dur", 3.0))) * p.get("vol", 1.0)))
        for k in range(len(p["posters"])):
            track.append((p["t"] + PICK + 0.6 + k * 0.45, tick()))
    return dict(profs=profs), track, s["end"]


def poster(pt, w=260, h=330):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(g)
    c0, c1 = pt["colors"]
    for y in range(h):
        k = y / h
        gd.line([(0, y), (w, y)], fill=tuple(int(c0[i] + (c1[i] - c0[i]) * k) for i in range(3)) + (255,))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 18, fill=255)
    g.putalpha(m)
    im.alpha_composite(g)
    comp(im, emoji(pt["emoji"], 96), (w - 96) / 2, 34)
    tf = font(32, "Bold")
    lines = wrap(pt["title"], tf, w - 28)[:3]
    y = h - 30 - 40 * len(lines)
    draw_rich(im, 16, y, lines, tf, WHITE, 40)
    d = ImageDraw.Draw(im)
    d.rectangle((0, h - 12, w, h - 4), fill=(80, 80, 80))
    d.rectangle((0, h - 12, int(w * pt.get("prog", 0.5)), h - 4), fill=RED)
    return im


def draw_picker(frame, t, s, profs, hi):
    d = ImageDraw.Draw(frame)
    lf = font(50, "Heavy")
    d.text(((W - lf.getlength(s["brand"])) / 2, 190), s["brand"], font=lf, fill=RED)
    hf = font(56, "Semibold")
    d.text(((W - hf.getlength("Who's watching?")) / 2, 290), "Who's watching?", font=hf, fill=WHITE)
    n = len(profs)
    rows = [profs[:3], profs[3:]]
    sz, gap = 240, 50
    y = 400
    for row in rows:
        x = (W - (len(row) * sz + (len(row) - 1) * gap)) / 2
        for p in row:
            sel = hi is p
            av = p["av"].resize((sz, sz))
            tile = Image.new("RGBA", (sz + 16, sz + 16), (0, 0, 0, 0))
            td = ImageDraw.Draw(tile)
            if sel:
                td.rounded_rectangle((0, 0, sz + 15, sz + 15), 26, outline=WHITE, width=6)
            comp(tile, av, 8, 8)
            comp(frame, tile, x - 8, y - 8)
            nf = font(34, "Semibold" if sel else "Regular")
            d.text((x + sz / 2 - nf.getlength(p["name"]) / 2, y + sz + 14), p["name"], font=nf, fill=WHITE if sel else GREY)
            x += sz + gap
        y += sz + 90


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    status_bar(d, s.get("clock", "11:40"), WHITE)
    profs = P["profs"]
    cur = [p for p in profs if p["t"] <= t]
    if not cur:
        draw_picker(frame, t, s, profs, None)
        return
    p = cur[-1]
    age = t - p["t"]
    if age < PICK:
        draw_picker(frame, t, s, profs, p if age > 0.25 else None)
        return
    age -= PICK
    a = ease(age / 0.3)
    page = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    win = cat_window(p["bg"], p["cat"].at(age, loop=True), X1 - X0, HEAD_H, fit=p.get("fit", 0.95), r=30)
    comp(page, win, X0, HEAD_Y)
    pd = ImageDraw.Draw(page)
    comp(page, p["chip"], X0 + 22, HEAD_Y + HEAD_H - 80)
    pd.text((X0 + 6, HEAD_Y + HEAD_H + 26), f"Continue watching for {p['name']}", font=font(42, "Bold"), fill=WHITE)
    py = HEAD_Y + HEAD_H + 96
    for k, pt in enumerate(p["posters"]):
        pa = ease((age - 0.6 - k * 0.45) / 0.35)
        if pa <= 0:
            continue
        po = poster(pt)
        if pa < 1:
            po.putalpha(po.getchannel("A").point(lambda v, pa=pa: int(v * pa)))
        comp(page, po, X0 + k * 280, py + (1 - pa) * 30)
        if pt.get("sub"):
            sf = font(28)
            draw_rich(page, X0 + k * 280 + 4, py + 344, wrap(pt["sub"], sf, 256)[:2], sf, GREY, 34)
    if age >= p.get("note_t", 3.2):
        na = ease_out_back(min(1, (age - p.get("note_t", 3.2)) / 0.3))
        nf = font(40, "Semibold")
        lines = wrap(p["note"], nf, RAIL_X - X0 - 60)
        hh = 54 * len(lines) + 40
        card = Image.new("RGBA", (RAIL_X - X0, hh), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, RAIL_X - X0 - 1, hh - 1), 26, fill=(255, 255, 255))
        cd.rectangle((0, 18, 8, hh - 18), fill=RED)
        draw_rich(card, 32, 20, lines, nf, (20, 20, 22), 54)
        if na < 1:
            card = card.resize((max(1, int(card.width * na)), max(1, int(card.height * na))))
        comp(page, card, X0, BOTTOM - 14 - hh)
    if a < 1:
        page.putalpha(page.getchannel("A").point(lambda v, a=a: int(v * a)))
    frame.alpha_composite(page)
