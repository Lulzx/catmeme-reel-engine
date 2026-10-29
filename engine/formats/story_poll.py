"""story_poll: your Instagram story with a poll sticker, seen from the owner's side.

The story is a looping video of you. Poll results move as `votes` points come in,
story replies stack up at the bottom, and a `sheet` (the viewers list, with who
voted what) slides up for the ending. `swap` changes the story video.
"""
import numpy as np
from PIL import Image, ImageDraw

from simple_render import Cat, window_bg, ease, ding, tick, whoosh, thunk
from chat_render import W, H, font, emoji, comp, wrap, draw_rich, avatar, ease_out_back, decode, CLIPS

BG = (0, 0, 0)
INK, GREY = (20, 20, 20), (142, 142, 147)
IG = [(254, 218, 117), (250, 126, 30), (214, 41, 118), (150, 47, 191), (79, 91, 213)]


def PLAN(s, slug):
    track = []
    people = s["people"]
    for i, p in enumerate(people.values()):
        p["av"] = avatar(p["avatar"], 72, i)
    vids = []
    for i, v in enumerate(s["story"]):
        until = s["story"][i + 1]["t"] if i + 1 < len(s["story"]) else s["end"]
        v = dict(v, until=until)
        v["cat"] = Cat(slug, f"story{i:02d}", v["clip"], v["start"], v.get("dur", until - v["t"]), v.get("height", 860))
        v["bg"] = window_bg(v.get("bg", "library.jpg"), W, H, blur=6, dim=0.15)
        n = until - v["t"]
        a = v["cat"].audio()
        if v.get("loop_audio"):                   # tile the clip's own sound under a long story
            a = np.concatenate([a] * (int(n / (len(a) / 48000)) + 1))[: int(n * 48000)]
        track.append((v["t"], a * v.get("vol", 1.0)))
        if i:
            track.append((v["t"], thunk()))
        vids.append(v)
    for d in s["dms"]:
        track.append((d["t"], ding()))
    sh = s.get("sheet")
    if sh:
        track.append((sh["t"], whoosh()))
        if sh.get("close"):
            track.append((sh["close"], whoosh()))
        for r in sh["rows"]:
            track.append((r["t"], tick()))
    return dict(vids=vids, people=people), track, s["end"]


def votes_at(s, t):
    pts = s["votes"]
    if t <= pts[0][0]:
        return pts[0][1], pts[0][2]
    for (t0, q0, s0), (t1, q1, s1) in zip(pts, pts[1:]):
        if t0 <= t < t1:
            k = ease((t - t0) / min(1.0, t1 - t0))
            return q0 + (q1 - q0) * k, s0 + (s1 - s0) * k
    return pts[-1][1], pts[-1][2]


def gradient_ring(d, x, y, r, w=6):
    for i, c in enumerate(IG):
        d.arc((x - r, y - r, x + r, y + r), -90 + i * 72, -90 + (i + 1) * 72 + 2, fill=c, width=w)


# Shorts safe area (engine/safe_zone.py): x 60..1020, y 150..1420, and x <= 900 below y 1000
X0, X1, RAIL_X, TOP, BOTTOM = 60, 1020, 900, 150, 1420
SHEET_Y = 678


def DRAW(frame, t, s, P):
    v = [x for x in P["vids"] if x["t"] <= t][-1]
    frame.alpha_composite(v["bg"])
    cat = v["cat"].at(t - v["t"], loop=v.get("loop", True))
    comp(frame, cat, v.get("cx", 480) - cat.width / 2, v.get("bottom", 1330) - cat.height)
    d = ImageDraw.Draw(frame)
    # top: progress bar + header, just under the player's buttons
    d.rounded_rectangle((X0, 158, X1, 164), 3, fill=(255, 255, 255, 110))
    d.rounded_rectangle((X0, 158, X0 + (X1 - X0) * min(1, t / s["end"]), 164), 3, fill=(255, 255, 255))
    me = P["people"]["you"]
    gradient_ring(d, X0 + 40, 222, 40)
    comp(frame, me["av"].resize((66, 66)), X0 + 7, 189)
    hf = font(36, "Semibold")
    d.text((X0 + 96, 200), "Your story", font=hf, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 90))
    d.text((X0 + 110 + hf.getlength("Your story"), 202), s.get("ago", "2h"), font=font(34), fill=(235, 235, 235))
    q, st = votes_at(s, t)
    tot = max(1, q + st)
    seen = s["seen_base"] + int(q + st)
    sf = font(32, "Semibold")
    stxt = f"Seen by {seen}"
    sw = sf.getlength(stxt) + 104
    d.rounded_rectangle((X1 - sw, 192, X1, 252), 30, fill=(0, 0, 0, 120))
    comp(frame, emoji("👁", 38), X1 - sw + 20, 203)
    d.text((X1 - sw + 72, 201), stxt, font=sf, fill=(255, 255, 255))
    # question + poll sticker
    cw = 800
    cx, cy = (W - cw) // 2, 268
    card = Image.new("RGBA", (cw, 410), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0, 8, cw - 1, 409), 40, fill=(0, 0, 0, 60))
    cd.rounded_rectangle((0, 0, cw - 1, 400), 40, fill=(255, 255, 255))
    qf = font(48, "Bold")
    ql = wrap(s["question"], qf, cw - 80)
    yq = 34
    for ln in ql:
        lw = sum(x[2] for x in ln)
        draw_rich(card, (cw - lw) / 2, yq, [ln], qf, INK, 60); yq += 60
    for i, (lab, n, col) in enumerate(((s["options"][0], q, (214, 41, 118)), (s["options"][1], st, (79, 91, 213)))):
        y = 160 + i * 110
        pct = n / tot
        cd.rounded_rectangle((40, y, cw - 40, y + 90), 26, fill=(239, 239, 244))
        if pct > 0.01:
            cd.rounded_rectangle((40, y, 40 + max(52, (cw - 80) * pct), y + 90), 26, fill=col + (60,))
        of = font(40, "Bold")
        draw_rich(card, 70, y + 20, wrap(lab, of, 400)[:1], of, INK, 50)
        ptxt = f"{round(pct * 100)}%"
        cd.text((cw - 70 - font(40, "Bold").getlength(ptxt), y + 20), ptxt, font=font(40, "Bold"), fill=col)
    comp(frame, card, cx, cy)
    # replies stack, newest at the bottom, clear of the like/share rail
    shown = [x for x in s["dms"] if x["t"] <= t]
    if s.get("sheet") and t >= s["sheet"]["t"]:        # the viewers sheet clears the replies for good
        shown = []
    pw = RAIL_X - X0
    y = BOTTOM - 10
    for i, dm in enumerate(shown[::-1][:3]):
        p = P["people"][dm["who"]]
        age = t - dm["t"]
        nf, tf = font(30, "Semibold"), font(36)
        lines = wrap(dm["text"], tf, pw - 130)
        hgt = 58 + 46 * len(lines) + 18
        pill = Image.new("RGBA", (pw, hgt), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill)
        pd.rounded_rectangle((0, 0, pw - 1, hgt - 1), 34, fill=(20, 20, 24, 205))
        comp(pill, p["av"], 20, (hgt - 72) / 2)
        pd.text((110, 14), f"{p['name']} replied to your story", font=nf, fill=(200, 200, 205))
        draw_rich(pill, 110, 54, lines, tf, (255, 255, 255), 46)
        a = 1.0 if i < 2 else 0.45
        if i == 0 and age < 0.35:
            k = ease_out_back(age / 0.35)
            a = min(1, age / 0.2)
            yy = y - hgt + (1 - k) * 60
        else:
            yy = y - hgt
        if a < 1:
            pill.putalpha(pill.getchannel("A").point(lambda vv, a=a: int(vv * a)))
        comp(frame, pill, X0, yy)
        y -= hgt + 14
    # viewers sheet for the ending: rows end above the caption strip, badges left of the rail
    sh = s.get("sheet")
    if sh and t >= sh["t"]:
        k = ease(min(1, (t - sh["t"]) / 0.45))
        if sh.get("close") and t >= sh["close"]:
            k = 1 - ease((t - sh["close"]) / 0.45)
        top = H - (H - SHEET_Y) * k
        panel = Image.new("RGBA", (W, H - SHEET_Y), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        pd.rounded_rectangle((0, 0, W - 1, H - SHEET_Y + 40), 44, fill=(255, 255, 255))
        pd.rounded_rectangle((W / 2 - 50, 16, W / 2 + 50, 24), 4, fill=(200, 200, 205))
        pd.text((X0 + 20, 40), f"Viewers · {seen}", font=font(44, "Bold"), fill=INK)
        summ = f"{s['options'][0]} {round(q / tot * 100)}%   ·   {s['options'][1]} {round(st / tot * 100)}%"
        draw_rich(panel, X0 + 20, 98, wrap(summ, font(34), W)[:1], font(34), GREY, 44)
        ry = 140
        rw = RAIL_X - X0
        for r in sh["rows"]:
            if t < r["t"]:
                break
            p = P["people"][r["who"]]
            ra = ease((t - r["t"]) / 0.3)
            row = Image.new("RGBA", (rw, 96), (0, 0, 0, 0))
            rd = ImageDraw.Draw(row)
            comp(row, p["av"].resize((76, 76)), 14, 10)
            rd.text((108, 8), p["name"], font=font(36, "Semibold"), fill=INK)
            vf = font(28)
            draw_rich(row, 108, 52, wrap(r["note"], vf, 480)[:1], vf, GREY, 38)
            badge = r["vote"]
            bf = font(32, "Bold")
            bw = sum(x[2] for x in wrap(badge, bf, 400)[0]) + 44
            col = (214, 41, 118) if r["vote"].startswith(s["options"][0].split()[0]) else (79, 91, 213)
            rd.rounded_rectangle((rw - 18 - bw, 20, rw - 18, 76), 28, fill=col)
            draw_rich(row, rw - 18 - bw + 22, 26, wrap(badge, bf, 400)[:1], bf, (255, 255, 255), 42)
            if r.get("hl"):
                rd.rounded_rectangle((0, 0, rw - 1, 95), 22, outline=(214, 41, 118), width=4)
            if ra < 1:
                row.putalpha(row.getchannel("A").point(lambda vv, ra=ra: int(vv * ra)))
            comp(panel, row, X0, ry + (1 - ra) * 24)
            ry += 100
        comp(frame, panel, 0, top)
