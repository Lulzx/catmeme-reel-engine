"""Family video call: a Meet-style gallery of cat tiles with mute icons,
active-speaker outlines, frozen connections, raised hands, toasts, live
captions at the bottom and a toolbar. The last beat can spotlight one tile.

Script keys: meeting, people{id: {name, clip, start, bg, muted, crop?, joins?}}
(tile order = dict order, 2 x 3 grid), events[] with t and one of:
caption{who, text, until}, speak{who, at, dur}, toast{text, until}, join, leave,
mute{who, on}, freeze{who, until}, hand{who}, onmute{until}, spotlight{who},
sound{clip, start, dur}, end.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from simple_render import Cat, cat_window, window_bg, fit_font, ease, ding, tick, rounded
from chat_render import W, H, FPS, SR, font, emoji, wrap, draw_rich, line_w, comp, clip, decode, tone, \
    ease_out_back, circle_mask
from paths import CLIPS

BG = (32, 33, 36)
# Everything lives inside the Shorts safe zone (engine/safe_zone.py): x 60..900, y 150..1420.
SX0, SX1, SY0 = 60, 900, 160
TW, TH, GAP, GY = 414, 300, 12, 272
BLUE, RED = (138, 180, 248), (234, 67, 53)


def tile_rect(i):
    return SX0 + (i % 2) * (TW + GAP), GY + (i // 2) * (TH + GAP), TW, TH


GRID = (SX0, GY, 2 * TW + GAP, 3 * TH + 2 * GAP)
CAP_Y = GY + 3 * TH + 2 * GAP + 12             # 1208
BAR_Y = CAP_Y + 118                            # toolbar row, ends ~1406


def mic_off(d, x, y, r=24):
    d.ellipse((x, y, x + 2 * r, y + 2 * r), fill=RED)
    d.rounded_rectangle((x + r - 6, y + 10, x + r + 6, y + r + 6), 6, fill=(255, 255, 255))
    d.arc((x + r - 11, y + r - 8, x + r + 11, y + r + 12), 0, 180, fill=(255, 255, 255), width=3)
    d.line((x + r, y + r + 12, x + r, y + r + 16), fill=(255, 255, 255), width=3)
    d.line((x + 10, y + 10, x + 2 * r - 10, y + 2 * r - 10), fill=(255, 255, 255), width=4)


def plan(s, slug):
    evs, track = s["events"], []
    end_t = next(e["t"] for e in evs if e.get("end"))
    people = s["people"]
    st = dict(order=list(people), tiles={}, captions=[], toasts=[], speaks=[], mutes={}, freezes=[],
              hands={}, joins={}, leaves={}, onmute=[], spot=None)
    spot = next((e["spotlight"] for e in evs if "spotlight" in e), None)
    for i, (pid, p) in enumerate(people.items()):
        hh = GRID[3] if pid == spot else TH          # the spotlit tile is keyed big so it stays sharp
        st["tiles"][pid] = dict(cat=Cat(slug, f"tile_{pid}", p["clip"], p.get("start", 0), 30, hh),
                                bg=window_bg(p.get("bg", "home.jpg"), TW, TH, blur=3),
                                bg_big=window_bg(p.get("bg", "home.jpg"), GRID[2], GRID[3], blur=3))
        st["mutes"][pid] = [(-1, p.get("muted", False))]
        if p.get("joins") is not None:
            st["joins"][pid] = p["joins"]
    for e in evs:
        t = e["t"]
        if "caption" in e:
            st["captions"].append(dict(e["caption"], t=t))
        if "speak" in e:
            sp = dict(e["speak"], t=t); st["speaks"].append(sp)
            p = people[sp["who"]]
            track.append((t, decode(os.path.join(CLIPS, clip(p["clip"])["file"]), sp["at"], sp["dur"], 0.15)
                          * sp.get("vol", 1.0)))
        if "toast" in e:
            st["toasts"].append(dict(text=e["toast"], t=t, until=e["until"])); track.append((t, tick() * 2))
        if "join" in e:
            st["joins"][e["join"]] = t; track.append((t, ding() * 0.7))
        if "leave" in e:
            st["leaves"][e["leave"]] = t; track.append((t, tone(700, 400, 0.25, 0.18, 8)))
        if "mute" in e:
            m = e["mute"]; st["mutes"][m["who"]].append((t, m["on"]))
            track.append((t, tone(1200 if not m["on"] else 800, 1200 if not m["on"] else 800, 0.06, 0.15, 40)))
        if "freeze" in e:
            st["freezes"].append(dict(e["freeze"], t=t))
        if "hand" in e:
            st["hands"][e["hand"]] = t; track.append((t, tone(990, 1320, 0.12, 0.18, 14)))
        if "onmute" in e:
            st["onmute"].append((t, e["onmute"]["until"]))
        if "spotlight" in e:
            st["spot"] = (t, e["spotlight"]); track.append((t, tone(400, 800, 0.3, 0.12, 6)))
        if "sound" in e:
            sd = e["sound"]
            track.append((t, decode(os.path.join(CLIPS, clip(sd["clip"])["file"]), sd["start"], sd["dur"], 0.1)))
    return st, track, end_t


def muted(st, pid, t):
    return [m for m in st["mutes"][pid] if m[0] <= t][-1][1]


def draw_tile(frame, t, s, st, pid, rect):
    x, y, w, h = rect
    p = s["people"][pid]
    T = st["tiles"][pid]
    joined = st["joins"].get(pid, -1) <= t
    left = pid in st["leaves"] and t >= st["leaves"][pid]
    d = ImageDraw.Draw(frame)
    if not joined or left:
        d.rounded_rectangle((x, y, x + w, y + h), 24, fill=(60, 64, 67))
        r = min(w, h) // 6
        d.ellipse((x + w / 2 - r, y + h / 2 - r, x + w / 2 + r, y + h / 2 + r), fill=(95, 99, 104))
        lf = font(int(r * 1.1), "Semibold")
        d.text((x + w / 2 - lf.getlength(p["name"][0]) / 2, y + h / 2 - r * 0.75), p["name"][0], font=lf, fill=(255, 255, 255))
        sub = "left" if left else "joining…"
        sf = font(28)
        d.text((x + w / 2 - sf.getlength(sub) / 2, y + h / 2 + r + 14), sub, font=sf, fill=(200, 200, 205))
    else:
        age = t - max(0, st["joins"].get(pid, 0))
        fr = next((f for f in st["freezes"] if f["who"] == pid and f["t"] <= t < f["until"]), None)
        cat = T["cat"].at((fr["t"] if fr else t) - 0, loop=True)
        bg = T["bg"] if w == TW else T["bg_big"].resize((int(w), int(h)))
        if (int(w), int(h)) != bg.size:
            bg = bg.resize((int(w), int(h)))
        if p.get("crop") == "forehead":               # phone held at the ceiling: only the top of the head
            win = bg.copy()
            s_ = h * 1.25 / cat.height
            c = cat.resize((max(1, int(cat.width * s_)), max(1, int(cat.height * s_))), Image.BILINEAR)
            comp(win, c, (w - c.width) / 2, h * 0.55)
            win = rounded(win, 24)
        else:
            win = cat_window(bg, cat, int(w), int(h), fit=0.92, r=24)
        if fr:
            g = ImageOps.grayscale(win.convert("RGB")).convert("RGBA")
            g.putalpha(win.getchannel("A")); win = g
        if age < 0.4:
            a = age / 0.4
            win.putalpha(win.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, win, x, y)
        if fr:
            chip = Image.new("RGBA", (360, 56), (0, 0, 0, 0))
            cd = ImageDraw.Draw(chip)
            cd.rounded_rectangle((0, 0, 359, 55), 28, fill=(0, 0, 0, 180))
            comp(chip, emoji("⚠️", 34), 18, 10)
            cd.text((64, 10), "poor connection", font=font(30, "Semibold"), fill=(255, 255, 255))
            comp(frame, chip, x + (w - 360) / 2, y + 24)
    # name, mic, hand, speaker outline
    nf = font(30, "Semibold")
    nm = p["name"]
    d.rounded_rectangle((x + 14, y + h - 62, x + 44 + nf.getlength(nm), y + h - 14), 16, fill=(0, 0, 0, 150))
    d.text((x + 28, y + h - 56), nm, font=nf, fill=(255, 255, 255))
    if joined and not left and muted(st, pid, t):
        mic_off(d, x + w - 66, y + 16)
    if pid in st["hands"] and t >= st["hands"][pid]:
        k = ease_out_back(min(1, (t - st["hands"][pid]) / 0.3))
        sz = int(64 * max(0.2, k))
        d.ellipse((x + 16, y + 16, x + 96, y + 96), fill=(255, 255, 255))
        comp(frame, emoji("✋", sz), x + 56 - sz / 2, y + 56 - sz / 2)
    speaking = any(sp["who"] == pid and sp["t"] <= t < sp["t"] + sp["dur"] for sp in st["speaks"])
    if speaking and not left:
        d.rounded_rectangle((x, y, x + w, y + h), 24, outline=BLUE, width=7)


def draw(frame, t, s, st):
    d = ImageDraw.Draw(frame)
    sw = SX1 - SX0
    pf = fit_font(s["pov"], W - 120, 42, "Bold")
    ln = wrap(s["pov"], pf, W - 120)[:1]
    draw_rich(frame, (W - line_w(ln[0])) / 2, SY0, ln, pf, (255, 255, 255), 52)
    mf = font(32, "Semibold")
    secs = int(t) + s.get("elapsed", 754)
    draw_rich(frame, SX0 + 12, 220, wrap(s["meeting"], mf, 500)[:1], mf, (232, 234, 237), 40)
    clock = f"{secs // 60:02d}:{secs % 60:02d}"
    tf = font(30)
    n = sum(1 for pid in st["order"] if st["joins"].get(pid, -1) <= t and not (pid in st["leaves"] and t >= st["leaves"][pid]))
    meta = f"{clock}  ·  👤 {n}"
    draw_rich(frame, SX1 - 12 - line_w(wrap(meta, tf, 600)[0]), 222, wrap(meta, tf, 600), tf, (189, 193, 198), 38)
    sp = st["spot"]
    for i, pid in enumerate(st["order"]):
        if sp and t >= sp[0] and pid == sp[1]:
            continue
        draw_tile(frame, t, s, st, pid, tile_rect(i))
    if sp and t >= sp[0]:
        i = st["order"].index(sp[1])
        k = ease((t - sp[0]) / 0.6)
        r0, r1 = tile_rect(i), GRID
        rect = tuple(a + (b - a) * k for a, b in zip(r0, r1))
        if k >= 1:
            d.rectangle((GRID[0], GRID[1], GRID[0] + GRID[2], GRID[1] + GRID[3]), fill=BG)
        draw_tile(frame, t, s, st, sp[1], tuple(int(v) for v in rect))
    for a0, a1 in st["onmute"]:
        if a0 <= t < a1:
            a = min(1, (t - a0) / 0.2, (a1 - t) / 0.2)
            box = Image.new("RGBA", (560, 110), (0, 0, 0, 0))
            bd = ImageDraw.Draw(box)
            bd.rounded_rectangle((0, 0, 559, 109), 30, fill=(20, 20, 22, 230))
            mic_off(bd, 26, 25, 30)
            bd.text((104, 14), "you're on mute", font=font(38, "Bold"), fill=(255, 255, 255))
            bd.text((104, 62), "unmute to talk", font=font(28), fill=(189, 193, 198))
            box.putalpha(box.getchannel("A").point(lambda v, a=a: int(v * a)))
            comp(frame, box, SX0 + (sw - 560) / 2, GY + 2 * (TH + GAP) + TH / 2 - 55)
    shown = [x for x in st["toasts"] if x["t"] <= t < x["until"]]
    for j, tst in enumerate(shown[-2:]):
        a = min(1, (t - tst["t"]) / 0.25, (tst["until"] - t) / 0.25)
        tf2 = font(32, "Semibold")
        lines = wrap(tst["text"], tf2, sw - 80)[:2]
        bw = max(line_w(l) for l in lines) + 56
        bh = 28 + 42 * len(lines)
        box = Image.new("RGBA", (int(bw), bh), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle((0, 0, bw - 1, bh - 1), 22, fill=(60, 64, 67, 240))
        draw_rich(box, 28, 13, lines, tf2, (255, 255, 255), 42)
        box.putalpha(box.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, box, SX0 + (sw - bw) / 2,
             GY + 3 * TH + 2 * GAP - 20 - (bh + 12) * (len(shown[-2:]) - j) + (1 - a) * 20)
    cap = next((c for c in st["captions"] if c["t"] <= t < c["until"]), None)
    if cap:
        p = s["people"][cap["who"]]
        cf = font(34)
        lines = wrap(cap["text"], cf, sw - 48)
        if len(lines) > 1:
            cf = font(30); lines = wrap(cap["text"], cf, sw - 48)
        a = min(1, (t - cap["t"]) / 0.2)
        box = Image.new("RGBA", (sw, 108), (0, 0, 0, 0))
        bd = ImageDraw.Draw(box)
        bd.rounded_rectangle((0, 0, sw - 1, 107), 20, fill=(0, 0, 0, 220))
        bd.text((24, 8), p["name"], font=font(28, "Bold"), fill=BLUE)
        draw_rich(box, 24, 44 if len(lines) == 1 else 40, lines[:2], cf, (255, 255, 255), 32)
        box.putalpha(box.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, box, SX0, CAP_Y)
    # toolbar, compact so it clears the caption/comment bar
    you_muted = muted(st, "you", t) if "you" in s["people"] else True
    buttons = [("🎙️", RED if you_muted else (60, 64, 67)), ("📷", (60, 64, 67)), ("✋", (60, 64, 67)),
               ("💬", (60, 64, 67)), ("📞", RED)]
    for i, (em, col) in enumerate(buttons):
        cx = SX0 + 84 + i * 168
        if i == 4:
            d.rounded_rectangle((cx - 64, BAR_Y, cx + 64, BAR_Y + 80), 40, fill=col)
        else:
            d.ellipse((cx - 40, BAR_Y, cx + 40, BAR_Y + 80), fill=col)
        comp(frame, emoji(em, 42), cx - 21, BAR_Y + 19)
        if i == 0 and you_muted:
            d.line((cx - 22, BAR_Y + 18, cx + 22, BAR_Y + 62), fill=(255, 255, 255), width=5)


PLAN, DRAW = plan, draw
