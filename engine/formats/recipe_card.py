"""recipe_card: a recipe app page for Mummy's recipe, where no quantity is a unit.

A hero video plays at the top (`hero` segments, each with an optional speech
`line`). `tabs` switch between the ingredients list and the method; ingredients
and steps pop in at their `t`. A `convert` button is tapped, every quantity
fails, and a toast says why.

Everything sits in the Shorts safe area (engine/safe_zone.py): the list column is
x 60..900 so nothing reaches under the like/share rail, and nothing goes below y 1420.
"""
import math
from PIL import Image, ImageDraw

from simple_render import Cat, cat_window, window_bg, name_chip, status_bar, ease, ding, tick, whoosh, thunk
from chat_render import W, H, font, emoji, comp, wrap, draw_rich, ease_out_back, tone

BG = (255, 250, 243)
INK, GREY, ORANGE, RED, GREEN = (40, 30, 24), (130, 118, 108), (226, 98, 26), (214, 48, 49), (46, 160, 67)
X0, X1, RAIL_X, BOTTOM = 60, 1020, 900, 1420
HERO_Y, HERO_H = 160, 380
LIST_Y = 762


def error_buzz():
    return tone(220, 180, 0.18, 0.25, 8) + tone(222, 182, 0.18, 0.0, 8)


def PLAN(s, slug):
    track = []
    heroes = []
    for i, h in enumerate(s["hero"]):
        until = s["hero"][i + 1]["t"] if i + 1 < len(s["hero"]) else s["end"]
        h = dict(h, until=until)
        h["cat"] = Cat(slug, f"hero{i:02d}", h["clip"], h["start"], until - h["t"], HERO_H)
        h["bg"] = window_bg(h.get("bg", "kitchen.jpg"), X1 - X0, HERO_H, blur=3)
        h["chip"] = name_chip(h["label"])
        track.append((h["t"] + 0.05, h["cat"].audio(min(h["cat"].dur, h.get("sound_dur", 3.0))) * h.get("vol", 1.0)))
        heroes.append(h)
    for it in s["ingredients"] + s["steps"]:
        track.append((it["t"], tick()))
    for tb in s["tabs"]:
        track.append((tb["t"], whoosh()))
    cv = s["convert"]
    track.append((cv["tap"], thunk()))
    track.append((cv["fail"], error_buzz()))
    track.append((cv["toast"], ding()))
    return dict(heroes=heroes), track, s["end"]


def spinner(d, cx, cy, r, t):
    for k in range(8):
        a = t * 8 + k * math.pi / 4
        g = int(80 + 170 * (k / 8))
        d.ellipse((cx + r * math.cos(a) - 6, cy + r * math.sin(a) - 6, cx + r * math.cos(a) + 6, cy + r * math.sin(a) + 6),
                  fill=(g, g, g))


def DRAW(frame, t, s, P):
    d = ImageDraw.Draw(frame)
    status_bar(d, s.get("clock", "7:05"), INK)
    # hero video
    hs = [h for h in P["heroes"] if h["t"] <= t]
    h = hs[-1] if hs else P["heroes"][0]
    win = cat_window(h["bg"], h["cat"].at(t - h["t"]), X1 - X0, HERO_H, fit=h.get("fit", 0.95), r=34)
    if len(hs) > 1 and t - h["t"] < 0.25:
        win.alpha_composite(Image.new("RGBA", win.size, (255, 255, 255, int(200 * (1 - (t - h["t"]) / 0.25)))))
    comp(frame, win, X0, HERO_Y)
    comp(frame, h["chip"], X0 + 22, HERO_Y + HERO_H - 80)
    if h.get("line") and t >= h.get("line_t", h["t"] + 0.5):
        la = ease_out_back(min(1, (t - h.get("line_t", h["t"] + 0.5)) / 0.3))
        lf = font(40, "Semibold")
        lines = wrap(h["line"], lf, 520)
        bw = max(sum(x[2] for x in ln) for ln in lines) + 60
        bh = 52 * len(lines) + 34
        bub = Image.new("RGBA", (int(bw) + 10, bh + 10), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bub)
        bd.rounded_rectangle((0, 6, bw, bh + 6), 30, fill=(0, 0, 0, 50))
        bd.rounded_rectangle((0, 0, bw, bh), 30, fill=(255, 255, 255))
        draw_rich(bub, 30, 16, lines, lf, INK, 52)
        if la < 1:
            bub = bub.resize((max(1, int(bub.width * la)), max(1, int(bub.height * la))))
        comp(frame, bub, X1 - 24 - bub.width, HERO_Y + 24)
    # title + meta
    y = HERO_Y + HERO_H + 18
    d.text((X0 + 8, y), s["dish"], font=font(54, "Bold"), fill=INK)
    mf = font(30)
    draw_rich(frame, X0 + 8, y + 74, wrap(s["meta"], mf, X1 - X0)[:1], mf, GREY, 38)
    # tabs
    tab = [tb for tb in s["tabs"] if tb["t"] <= t]
    tab = tab[-1]["tab"] if tab else "Ingredients"
    ty = y + 128
    tf = font(36, "Semibold")
    x = X0 + 8
    for name in ("Ingredients", "Method"):
        on = name == tab
        d.text((x, ty), name, font=tf, fill=ORANGE if on else GREY)
        if on:
            d.rounded_rectangle((x, ty + 50, x + tf.getlength(name), ty + 56), 3, fill=ORANGE)
        x += tf.getlength(name) + 60
    d.line((X0, ty + 58, X1, ty + 58), fill=(236, 226, 214), width=2)
    cv = s["convert"]
    cw = RAIL_X - X0
    if tab == "Ingredients":
        rows = [it for it in s["ingredients"] if it["t"] <= t]
        for k, it in enumerate(rows):
            ry = LIST_Y + k * 92
            ra = ease((t - it["t"]) / 0.3)
            row = Image.new("RGBA", (cw, 88), (0, 0, 0, 0))
            rd = ImageDraw.Draw(row)
            rd.rounded_rectangle((0, 0, cw - 1, 84), 22, fill=(255, 255, 255), outline=(240, 230, 218), width=2)
            comp(row, emoji(it["emoji"], 50), 20, 17)
            rd.text((92, 20), it["name"], font=font(36, "Semibold"), fill=INK)
            qf = font(34, "Semibold")
            q = it["qty"]
            qcol = ORANGE
            if t >= cv["fail"]:
                q, qcol = "⚠️ error", RED
            elif t >= cv["tap"]:
                q = ""
                spinner(rd, cw - 60, 42, 16, t + k)
            qw = sum(x_[2] for x_ in wrap(q, qf, 600)[0]) if q else 0
            if q:
                draw_rich(row, cw - 26 - qw, 22, wrap(q, qf, 600)[:1], qf, qcol, 44)
            if ra < 1:
                row.putalpha(row.getchannel("A").point(lambda v, ra=ra: int(v * ra)))
            comp(frame, row, X0 + (1 - ra) * 30, ry)
        if t >= cv["show"]:
            ba = ease_out_back(min(1, (t - cv["show"]) / 0.3))
            by = LIST_Y + len(s["ingredients"]) * 92 + 10
            bf = font(36, "Bold")
            label = cv["label"]
            bw = sum(x_[2] for x_ in wrap(label, bf, 800)[0]) + 70
            btn = Image.new("RGBA", (int(bw), 76), (0, 0, 0, 0))
            bd = ImageDraw.Draw(btn)
            pressed = cv["tap"] <= t < cv["tap"] + 0.25
            bd.rounded_rectangle((0, 0, bw - 1, 75), 38, fill=(196, 80, 16) if pressed else ORANGE)
            draw_rich(btn, 35, 14, wrap(label, bf, 800)[:1], bf, (255, 255, 255), 46)
            if ba < 1:
                btn = btn.resize((max(1, int(btn.width * ba)), max(1, int(btn.height * ba))))
            comp(frame, btn, X0 + (cw - btn.width) / 2, by + (76 - btn.height) / 2)
    else:
        sy = LIST_Y
        for k, st in enumerate([x_ for x_ in s["steps"] if x_["t"] <= t]):
            ra = ease((t - st["t"]) / 0.3)
            sf = font(36)
            lines = wrap(st["text"], sf, cw - 130)
            hh = 50 * len(lines) + 40
            card = Image.new("RGBA", (cw, hh), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            cd.rounded_rectangle((0, 0, cw - 1, hh - 1), 24, fill=(255, 255, 255), outline=(240, 230, 218), width=2)
            cd.ellipse((22, 20, 82, 80), fill=ORANGE)
            nf = font(34, "Bold")
            cd.text((52 - nf.getlength(str(k + 1)) / 2, 28), str(k + 1), font=nf, fill=(255, 255, 255))
            draw_rich(card, 108, 20, lines, sf, INK, 50)
            if ra < 1:
                card.putalpha(card.getchannel("A").point(lambda v, ra=ra: int(v * ra)))
            comp(frame, card, X0 + (1 - ra) * 30, sy)
            sy += hh + 16
    # failure toast, above the caption strip
    if t >= cv["toast"]:
        k = ease_out_back(min(1, (t - cv["toast"]) / 0.35))
        tf2 = font(34, "Semibold")
        lines = wrap(cv["toast_text"], tf2, cw - 120)
        hh = 46 * len(lines) + 44
        toast = Image.new("RGBA", (cw, hh), (0, 0, 0, 0))
        td = ImageDraw.Draw(toast)
        td.rounded_rectangle((0, 0, cw - 1, hh - 1), 28, fill=(40, 40, 44, 240))
        comp(toast, emoji("⚠️", 46), 26, (hh - 46) / 2)
        draw_rich(toast, 92, 22, lines, tf2, (255, 255, 255), 46)
        comp(frame, toast, X0, BOTTOM - 10 - hh + (1 - k) * 60)
