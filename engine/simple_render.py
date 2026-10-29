#!/usr/bin/env python3
"""Simple one-screen reel formats, one per script `format`:

  search      Papa's search history: queries type into a search bar, the
              autocomplete suggestions carry the jokes, a cat reacts below.
  lockscreen  A phone lock screen while you're away: notifications pile up,
              the clock ticks, a call comes in. The wallpaper is the cat.
  tierlist    A cat ranks things: each item is introduced, a judge cat reacts,
              and the tile drops into its S..F row (rows can be added).
  <other>     engine/formats/<other>.py (see load_format).

    python3 engine/simple_render.py data/formats/<slug>.json              ->  output/<slug>.mp4
    python3 engine/simple_render.py data/formats/<slug>.json --register   ... + queue it in videos.db

Pillow frames piped into ffmpeg, audio mixed in numpy, same as chat_render.py
(whose text, emoji and sound helpers this reuses).
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import BACKGROUNDS, CLIPS, OUTPUT, WORK
import cutouts as C
from safe_zone import TOP, BOTTOM, SIDE, RAIL_X
from chat_render import (W, H, FPS, SR, font, emoji, comp, wrap, draw_rich, line_w, cover,
                         circle_mask, clip, decode, tone, click, ease_out_back)

INK, GREY = (32, 33, 36), (95, 99, 104)


def ease(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def noise(dur, vol, seed=0):
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(int(dur * SR)).astype(np.float32) * vol
    return np.repeat(w[:, None], 2, axis=1)


def lowpass(a, n):
    """Soften white noise into a shower hiss: two passes of an n-sample moving average."""
    k = np.ones(n, dtype=np.float32) / n
    for _ in range(2):
        a = np.stack([np.convolve(a[:, c], k, mode="same") for c in range(2)], axis=1)
    return a.astype(np.float32)


def bang(vol=0.9, seed=1):
    a = noise(0.9, vol, seed)
    a *= np.exp(-np.arange(len(a)) / SR * 6)[:, None]
    boom = tone(70, 40, 0.5, 0.5, 6)
    a[:len(boom)] += boom
    return a


def thunk():
    return tone(180, 90, 0.12, 0.35, 22)


def whoosh():
    a = noise(0.28, 0.12, 3)
    env = np.sin(np.linspace(0, math.pi, len(a)))[:, None]
    return (a * env).astype(np.float32)


def ding():
    return np.concatenate([tone(1320, 1320, 0.12, 0.18, 12), tone(1760, 1760, 0.22, 0.16, 9)])


def tick():
    return tone(1800, 1800, 0.02, 0.06, 90)


def ring(dur):
    """Two-tone phone ring, 0.4s on / 0.2s off."""
    out = np.zeros((int(dur * SR), 2), dtype=np.float32)
    t = 0.0
    while t < dur - 0.1:
        n = int(0.4 * SR); x = np.arange(n) / SR
        w = (np.sin(2 * np.pi * 880 * x) + np.sin(2 * np.pi * 1100 * x)) * 0.07
        w *= np.minimum(1, np.minimum(x, 0.4 - x) * 60)
        i0 = int(t * SR); seg = w[: len(out) - i0]
        out[i0:i0 + len(seg)] += seg[:, None]
        t += 0.6 if int(t / 0.6) % 4 != 3 else 1.2
    return out


def doorbell():
    return np.concatenate([tone(660, 660, 0.5, 0.25, 4), tone(523, 523, 0.8, 0.25, 3)])


# ── keyed cats ────────────────────────────────────────────────────────────────
class Cat:
    """A clip keyed into a PNG sequence at a fixed height; frame k by age in seconds."""

    def __init__(self, slug, name, cid, start, dur, height):
        c = clip(cid)
        self.cid, self.start, self.dur = cid, start, min(dur, c["duration"] - start)
        self.dir = os.path.join(WORK, "simple", slug, name)
        os.makedirs(self.dir, exist_ok=True)
        for f in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, f))
        key = C._key_chain(c).replace(C.DESPILL, "despill=type=green:mix=0.35:expand=0")   # less lavender on white cats
        vf = f"fps={FPS},{C._crop_expr(c, 0.08)},{key},scale=-1:{height}"
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-ss", str(start), "-t", str(self.dur),
                        "-i", os.path.join(CLIPS, c["file"]), "-vf", vf,
                        os.path.join(self.dir, "%04d.png")], check=True, capture_output=True)
        self.frames = sorted(os.listdir(self.dir))
        for f in self.frames:                      # some clips carry a dark line on their top edge
            fp = os.path.join(self.dir, f)
            im = Image.open(fp); a = np.asarray(im.getchannel("A")).copy(); a[:max(6, len(a) // 50)] = 0
            im.putalpha(Image.fromarray(a)); im.save(fp)
        box = None                                 # union of the opaque area, so the cut edge sits flush
        for f in self.frames[::5]:
            b = Image.open(os.path.join(self.dir, f)).getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
            if b:
                box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        self.box = box
        self._last = (None, None)

    def at(self, age, loop=False):
        n = len(self.frames)
        k = int(max(0, age) * FPS)
        if loop:                                   # ping-pong so a short clip can hold a long wallpaper
            k %= 2 * n - 2; k = k if k < n else 2 * n - 2 - k
        k = min(n - 1, k)
        if self._last[0] != k:
            im = Image.open(os.path.join(self.dir, self.frames[k])).convert("RGBA")
            self._last = (k, im.crop(self.box) if self.box else im)
        return self._last[1]

    def audio(self, dur=None):
        return decode(os.path.join(CLIPS, clip(self.cid)["file"]), self.start, dur or self.dur, 0.15)


def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    im.putalpha(Image.fromarray(np.minimum(np.asarray(im.getchannel("A")), np.asarray(m))))
    return im


def cat_window(bg, cat, w, h, fit=0.92, r=40):
    """Cat standing on the bottom of a rounded window over its background."""
    win = bg.copy()
    s = min(h * fit / cat.height, w * 1.1 / cat.width)
    c = cat.resize((max(1, int(cat.width * s)), max(1, int(cat.height * s))), Image.BILINEAR)
    comp(win, c, (w - c.width) / 2, h - c.height + 4)
    return rounded(win, r)


def window_bg(name, w, h, blur=4, dim=0):
    bg = cover(Image.open(os.path.join(BACKGROUNDS, name)).convert("RGBA"), w, h)
    bg = bg.filter(ImageFilter.GaussianBlur(blur))
    if dim:
        bg.alpha_composite(Image.new("RGBA", bg.size, (0, 0, 0, int(255 * dim))))
    return bg


def name_chip(text, bg=(255, 255, 255, 235), fg=INK, size=34):
    f = font(size, "Semibold")
    w = int(f.getlength(text)) + 44
    im = Image.new("RGBA", (w, size + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, size + 29), (size + 30) // 2, fill=bg)
    d.text((22, 12), text, font=f, fill=fg)
    return im


def fit_font(text, maxw, size, weight="Regular"):
    while size > 24 and font(size, weight).getlength(text) > maxw:
        size -= 2
    return font(size, weight)


def status_bar(d, clock, col):
    d.text((70, 24), clock, font=font(36, "Semibold"), fill=col)
    x = W - 90
    d.rounded_rectangle((x - 60, 30, x, 58), 8, outline=col, width=3)
    d.rectangle((x - 54, 36, x - 18, 52), fill=col)
    d.rectangle((x + 3, 38, x + 7, 50), fill=col)


# ── format: search ────────────────────────────────────────────────────────────
GOOGLE = [(66, 133, 244), (234, 67, 53), (251, 188, 5), (66, 133, 244), (52, 168, 83), (234, 67, 53)]


def magnifier(d, x, y, r, col, w=4):
    d.ellipse((x, y, x + 2 * r, y + 2 * r), outline=col, width=w)
    d.line((x + 1.7 * r, y + 1.7 * r, x + 2.7 * r, y + 2.7 * r), fill=col, width=w + 1)


def plan_search(s, slug):
    t, plan, track = 0.6, [], []
    WIN_W, WIN_H = RAIL_X - SIDE, 500
    for i, st in enumerate(s["steps"]):
        p = dict(st, t0=t)
        if "q" in st:
            p["type_end"] = t + 0.25 + len(st["q"]) * 0.075
            p["sug_t"] = [p["type_end"] + 0.35 + k * 0.55 for k in range(len(st["s"]))]
            end = p["sug_t"][-1] + st["hold"]
            for k in range(len(st["q"])):
                track.append((t + 0.25 + k * 0.075, click(0.10)))
            for ts in p["sug_t"]:
                track.append((ts, tick()))
        else:
            p["banner_t"] = t + 0.4
            end = p["banner_t"] + st["hold"]
            track.append((p["banner_t"], ding()))
        p["t1"] = end
        p["cat"] = Cat(slug, f"step{i:02d}", st["clip"], st["start"], end - t, int(WIN_H * 1.0))
        p["bg"] = window_bg(st.get("bg", "livingroom.jpg"), WIN_W, WIN_H)
        p["chip"] = name_chip(st["who"])
        track.append((t + 0.1, p["cat"].audio(min(p["cat"].dur, end - t - 0.1))))
        plan.append(p)
        t = end + 0.35
    return plan, track, t + 0.4


def draw_search(frame, t, s, plan):
    d = ImageDraw.Draw(frame)
    status_bar(d, s.get("clock", "11:52"), INK)
    pf = font(46, "Bold")
    lines = wrap(s["pov"], pf, W - 140)
    y = TOP + 16
    for ln in lines:
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, INK, 58); y += 58
    gf = font(118, "Semibold")
    word, x = "Google", (W - gf.getlength("Google")) / 2
    for ch, col in zip(word, GOOGLE):
        d.text((x, 262), ch, font=gf, fill=col); x += gf.getlength(ch)
    cur = next((p for p in plan if p["t0"] <= t < p["t1"] + 0.35), plan[-1])
    # search pill
    d.rounded_rectangle((SIDE, 436, W - SIDE, 556), 60, fill=(0, 0, 0, 25))
    d.rounded_rectangle((SIDE, 430, W - SIDE, 550), 60, fill=(255, 255, 255), outline=(218, 220, 224), width=3)
    magnifier(d, 104, 470, 16, GREY)
    qf = font(44)
    if "q" in cur:
        n = int(len(cur["q"]) * min(1, max(0, (t - cur["t0"] - 0.25) / (cur["type_end"] - cur["t0"] - 0.25))))
        q = cur["q"][:n]
        d.text((170, 464), q, font=qf, fill=INK)
        if int(t * 2.2) % 2 == 0 or t < cur["type_end"]:
            cx = 172 + qf.getlength(q)
            d.line((cx, 466, cx, 518), fill=(26, 115, 232), width=3)
        sf_b, sf = font(40, "Bold"), font(40)
        y = 576
        for k, (txt, ts) in enumerate(zip(cur["s"], cur["sug_t"])):
            if t < ts:
                break
            a = ease((t - ts) / 0.2)
            row = Image.new("RGBA", (W - 120, 96), (0, 0, 0, 0))
            rd = ImageDraw.Draw(row)
            magnifier(rd, 40, 30, 13, (154, 160, 166), 3)
            pre = cur["q"] if txt.startswith(cur["q"]) else ""
            fb, fr = sf_b, sf
            if sf.getlength(pre) + sf_b.getlength(txt[len(pre):]) > W - 260:
                fr = fit_font(txt, W - 260, 40); fb = font(fr.size, "Bold")
            rd.text((110, 24), pre, font=fr, fill=GREY)
            rd.text((110 + fr.getlength(pre), 24), txt[len(pre):], font=fb, fill=INK)
            rd.line((110, 94, W - 160, 94), fill=(232, 234, 237), width=2)
            row.putalpha(row.getchannel("A").point(lambda v, a=a: int(v * a)))
            comp(frame, row, 60, y + (1 - a) * 20)
            y += 96
    # cat window
    wx, wy = SIDE, BOTTOM - 520
    if cur["t0"] <= t:
        win = cat_window(cur["bg"], cur["cat"].at(t - cur["t0"]), RAIL_X - SIDE, 500)
        a = ease((t - cur["t0"]) / 0.25)
        if a < 1:
            win.putalpha(win.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, win, wx, wy)
        comp(frame, cur["chip"], wx + 30, wy + 30)
    if "banner" in cur and t >= cur["banner_t"]:
        b = cur["banner"]
        age = t - cur["banner_t"]
        k = ease_out_back(min(1, age / 0.35))
        card = Image.new("RGBA", (W - 80, 250), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 10, W - 81, 249), 44, fill=(0, 0, 0, 50))
        cd.rounded_rectangle((0, 0, W - 81, 238), 44, fill=(248, 248, 250))
        cd.rounded_rectangle((34, 34, 114, 114), 22, fill=(255, 0, 0))
        cd.polygon([(64, 56), (64, 92), (94, 74)], fill=(255, 255, 255))
        cd.text((140, 36), b["app"].upper(), font=font(30, "Semibold"), fill=GREY)
        cd.text((W - 200, 36), "now", font=font(30), fill=GREY)
        cd.text((140, 78), b["title"], font=font(40, "Semibold"), fill=INK)
        bf = font(40)
        draw_rich(card, 140, 136, wrap(b["body"], bf, W - 280)[:2], bf, INK, 50)
        comp(frame, card, 40, -260 + 590 * k)


# ── format: lockscreen ────────────────────────────────────────────────────────
APP_COL = {"phone": (52, 199, 89), "whatsapp": (37, 211, 102)}


def app_icon(app, size=84):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), size * 0.23, fill=APP_COL[app])
    comp(im, emoji("📞" if app == "phone" else "💬", int(size * 0.6)), size * 0.2, size * 0.2)
    return im


def notif_card(ev, mins_ago):
    cw = RAIL_X - SIDE
    tf, bf, mf = font(37, "Semibold"), font(37), font(30)
    title = ev["title"] + (f" · {ev['sub']}" if ev.get("sub") else "")
    lines = wrap(ev["body"], bf, cw - 200)
    h = 70 + 50 * len(lines) + 26
    im = Image.new("RGBA", (cw, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, cw - 1, h - 1), 44, fill=(246, 246, 248, 228))
    comp(im, app_icon(ev["app"]), 28, (h - 84) / 2)
    tlines = wrap(title, fit_font(title, cw - 330, 37, "Semibold"), cw - 330)[:1]
    draw_rich(im, 136, 22, tlines, fit_font(title, cw - 330, 37, "Semibold"), INK, 46)
    when = "now" if mins_ago == 0 else f"{mins_ago}m ago"
    d.text((cw - 30 - mf.getlength(when), 26), when, font=mf, fill=(120, 120, 128))
    draw_rich(im, 136, 72, lines, bf if ev["app"] != "phone" else font(37), INK, 50)
    return im


def plan_lock(s, slug):
    evs, track = s["events"], []
    end_t = next(e["t"] for e in evs if e.get("end"))
    wp = s["wallpaper"]
    walls = [(0.0, Cat(slug, "wall0", wp["clip"], wp["start"], wp["dur"], 1150),
              window_bg(wp.get("bg", "home.jpg"), W, H, blur=8, dim=0.28))]
    notifs, calls, clocks = [], [], []
    shower_off = end_t
    for i, e in enumerate(evs):
        if "clock" in e:
            clocks.append((e["t"], e["clock"]))
        if "app" in e:
            notifs.append(dict(e)); track.append((e["t"], ding()))
        if "call" in e:
            c = dict(e["call"], t=e["t"])
            c["cat"] = Cat(slug, f"call{i:02d}", c["clip"], c["start"], c["until"] - e["t"], 440)
            c["bg"] = window_bg(c.get("bg", "kitchen.jpg"), 440, 440, blur=3)
            calls.append(c)
            track.append((e["t"], ring(c["until"] - e["t"])))
            track.append((e["t"] + 0.3, c["cat"].audio(min(c["cat"].dur, 2.5)) * 0.8))
        if e.get("doorbell"):
            track.append((e["t"], doorbell()))
        if e.get("shower_off"):
            shower_off = e["t"]
        if "wallpaper" in e:
            w2 = e["wallpaper"]
            cat = Cat(slug, f"wall{i:02d}", w2["clip"], w2["start"], w2["dur"], 1150)
            walls.append((e["t"], cat, window_bg(w2.get("bg", "home.jpg"), W, H, blur=8, dim=0.28)))
            track.append((e["t"], cat.audio()))
        if "sound" in e:
            sd = e["sound"]
            track.append((e["t"], decode(os.path.join(CLIPS, clip(sd["clip"])["file"]), sd["start"], sd["dur"], 0.1)))
    # shower: soft filtered noise bed until the water stops
    sh = lowpass(noise(shower_off, 0.5, 7), 10) * 0.9
    fade = int(0.25 * SR)
    sh[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    sh[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    track.append((0.0, sh))
    return dict(walls=walls, notifs=notifs, calls=calls, clocks=clocks, clear=shower_off), track, end_t


def draw_lock(frame, t, s, P):
    t0, cat, bg = [w for w in P["walls"] if w[0] <= t][-1]
    frame.alpha_composite(bg)
    im = cat.at(t - t0, loop=(t0 == 0))
    comp(frame, im, (W - im.width) / 2, H - im.height + 40)
    d = ImageDraw.Draw(frame)
    clock = [c for c in P["clocks"] if c[0] <= t][-1][1]
    status_bar(d, clock, (255, 255, 255))
    df = font(46, "Semibold")
    d.text(((W - df.getlength(s["date"])) / 2, TOP + 30), s["date"], font=df, fill=(255, 255, 255, 235))
    cf = font(240, "Bold")
    d.text(((W - cf.getlength(clock)) / 2, TOP + 66), clock, font=cf, fill=(255, 255, 255, 240))
    # notification stack: newest on top, older slide down
    shown = [n for n in P["notifs"] if n["t"] <= t][::-1]
    cur_min = int(clock.split(":")[1])
    y = 540
    for i, n in enumerate(shown):
        card = notif_card(n, max(0, cur_min - int(n["clock"].split(":")[1])))
        age = t - n["t"]
        if i == 0 and age < 0.35:
            k = ease_out_back(age / 0.35)
            sc = 0.85 + 0.15 * k
            card = card.resize((int(card.width * sc), max(1, int(card.height * sc))), Image.BILINEAR)
            card.putalpha(card.getchannel("A").point(lambda v, a=min(1, age / 0.2): int(v * a)))
            comp(frame, card, SIDE + (RAIL_X - SIDE - card.width) / 2, y - (1 - k) * 60)
            y += int((card.height + 16) * min(1, k))
            continue
        if y > BOTTOM - 100:
            break
        if i > 0 and t > P["clear"]:                        # water off: everything but the last one slides away
            a = 1 - ease((t - P["clear"] - 0.3) / 0.5)
            if a <= 0:
                continue
            card.putalpha(card.getchannel("A").point(lambda v, a=a: int(v * a)))
        if y + card.height > BOTTOM:                        # fade the ones sinking under the player UI
            a = max(0.0, (BOTTOM - y) / card.height)
            card.putalpha(card.getchannel("A").point(lambda v, a=a: int(v * a)))
        comp(frame, card, SIDE, y)
        y += card.height + 16
    for cx in (150, W - 150):                               # torch + camera
        d.ellipse((cx - 56, H - 230, cx + 56, H - 118), fill=(40, 40, 40, 150))
    comp(frame, emoji("🔦", 56), 122, H - 202)
    comp(frame, emoji("📷", 56), W - 178, H - 202)
    d.rounded_rectangle((W / 2 - 140, H - 40, W / 2 + 140, H - 30), 5, fill=(255, 255, 255))
    for c in P["calls"]:
        if c["t"] <= t < c["until"]:
            draw_call(frame, t, c)


def draw_call(frame, t, c):
    age = t - c["t"]
    a = min(1, age / 0.25, (c["until"] - t) / 0.25)
    ov = Image.new("RGBA", (W, H), (18, 18, 22, 255))
    d = ImageDraw.Draw(ov)
    nf, sf = font(84, "Semibold"), font(40)
    d.text(((W - nf.getlength(c["name"])) / 2, 230), c["name"], font=nf, fill=(255, 255, 255))
    d.text(((W - sf.getlength(c["sub"])) / 2, 340), c["sub"], font=sf, fill=(170, 170, 178))
    D = 440
    pulse = 1 + 0.03 * math.sin(age * 6)
    rr = int(D / 2 * pulse) + 24
    d.ellipse((W / 2 - rr, 700 - rr, W / 2 + rr, 700 + rr), fill=(52, 199, 89, 60))
    sq = c["bg"].copy()
    cat = c["cat"].at(age)
    s = D * 0.95 / cat.height
    cat = cat.resize((int(cat.width * s), int(cat.height * s)), Image.BILINEAR)
    comp(sq, cat, (D - cat.width) / 2, D - cat.height + D * 0.05)
    sq.putalpha(circle_mask(D))
    comp(ov, sq, (W - D) / 2, 700 - D / 2)
    bf = font(34)
    for cx, col, lab, em in ((250, (255, 59, 48), "Decline", "📞"), (RAIL_X - 200, (52, 199, 89), "Accept", "📞")):
        d.ellipse((cx - 85, 1100, cx + 85, 1270), fill=col)
        comp(ov, emoji(em, 80), cx - 40, 1145)
        d.text((cx - bf.getlength(lab) / 2, 1290), lab, font=bf, fill=(255, 255, 255))
    ov.putalpha(int(255 * a))
    frame.alpha_composite(ov)


# ── format: tierlist ──────────────────────────────────────────────────────────
TIERS = [("S", (255, 127, 127)), ("A", (255, 191, 127)), ("B", (255, 223, 127)),
         ("C", (255, 255, 127)), ("D", (191, 255, 127)), ("F", (127, 255, 127))]
ROW_Y0, ROW_H, LBL_W, TILE_W, TILE_H = 236, 112, 130, 160, 100
PRES_Y = 1090
JUDGE_W, JUDGE_H = 340, BOTTOM - 10 - PRES_Y
HOLD_XY = (600, 330)                                  # where the next tile is held up, over the empty right of the grid                                         # presenter strip: item text + judge, above the player UI
TL_BG, ROW_BG = (26, 26, 31), (44, 44, 52)


def tile(e, scale=1.0):
    w, h = int(TILE_W * scale), int(TILE_H * scale)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), int(16 * scale), fill=(250, 250, 250))
    comp(im, emoji(e["emoji"], int(50 * scale)), (w - 50 * scale) / 2, 8 * scale)
    f = fit_font(e["label"], w - 14 * scale, int(24 * scale), "Semibold")
    d.text(((w - f.getlength(e["label"])) / 2, h - 38 * scale), e["label"], font=f, fill=INK)
    return im


def plan_tier(s, slug):
    t, plan, track = 1.2, [], []
    tiles = {e["id"]: e for e in s["items"] if "id" in e}
    for i, it in enumerate(s["items"]):
        p = dict(it, t0=t, reason_t=t + 1.9, drop_t=t + 4.2)
        if it.get("tier") == "blocked" or it.get("to") == "blocked":
            p["new_row"] = True
        p["t1"] = p["drop_t"] + (2.6 if it.get("move") else 1.3)
        p["cat"] = Cat(slug, f"item{i:02d}", it["clip"], it["start"], p["t1"] - t + 0.4, 320)
        p["bg"] = window_bg(it.get("bg", "livingroom.jpg"), JUDGE_W, JUDGE_H, blur=4)
        track.append((t, whoosh()))
        track.append((t + 0.2, p["cat"].audio(min(p["cat"].dur, 4.0)) * 0.9))
        track.append((p["drop_t"] + 0.45, thunk()))
        if it.get("bang"):
            for k, dt in enumerate((0.6, 1.5, 2.1, 3.4, 4.6)):
                track.append((t + dt, bang(0.5 + 0.1 * (k % 2), k)))
        plan.append(p)
        t = p["t1"]
    return dict(plan=plan, tiles=tiles), track, t + 0.2


def tier_rows(t, plan):
    rows = [list(r) for r in TIERS]
    nr = next((p for p in plan if p.get("new_row")), None)
    if nr and t >= nr["drop_t"] - 0.6:
        rows.append(["blocked", (90, 90, 98), ease((t - nr["drop_t"] + 0.6) / 0.5)])
    return rows


def slot_xy(row_i, col):
    return SIDE + LBL_W + 12 + col * (TILE_W + 10), ROW_Y0 + row_i * (ROW_H + 6) + (ROW_H - TILE_H) / 2


def draw_tier(frame, t, s, P):
    plan = P["plan"]
    frame.paste(TL_BG + (255,), (0, 0, W, H))
    d = ImageDraw.Draw(frame)
    pf = fit_font(s["pov"], W - 2 * SIDE, 50, "Bold")
    lines = wrap(s["pov"], pf, W - 2 * SIDE)
    y = TOP + 6
    for ln in lines:
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, (255, 255, 255), 62); y += 62
    rows = tier_rows(t, plan)
    names = [r[0] for r in rows]
    for i, r in enumerate(rows):
        grow = r[2] if len(r) > 2 else 1
        ry = ROW_Y0 + i * (ROW_H + 6)
        rh = ROW_H * grow
        if rh < 2:
            continue
        d.rectangle((0, ry, W, ry + rh), fill=ROW_BG)
        d.rectangle((0, ry, SIDE + LBL_W, ry + rh), fill=r[1])
        lf = font(62 if len(r[0]) == 1 else 32, "Bold")
        col = (20, 20, 20) if len(r[0]) == 1 else (255, 255, 255)
        d.text((SIDE + (LBL_W - lf.getlength(r[0])) / 2, ry + rh / 2 - lf.size * 0.62), r[0], font=lf, fill=col)
    # where every tile is right now
    placed = {}                                       # id -> (row name, landed at)
    for p in plan:
        if "id" in p and t >= p["drop_t"]:
            placed[p["id"]] = (p["tier"], p["drop_t"])
        if p.get("move") and t >= p["drop_t"]:
            placed[p["move"]] = (p["to"], p["drop_t"])
    order = sorted(placed.items(), key=lambda kv: kv[1][1])
    cols = {}
    for tid, (row, landed) in order:
        ri = names.index(row) if row in names else len(names) - 1
        col = cols.get(row, 0); cols[row] = col + 1
        tx, ty = slot_xy(ri, col)
        age = t - landed
        e = P["tiles"][tid]
        if age < 0.45:                                # flying in from the presenter (or from its old row)
            src = next(p for p in plan if p.get("id") == tid)
            mover = next((p for p in plan if p.get("move") == tid and p["drop_t"] == landed), None)
            if mover:
                ri0 = names.index(src["tier"]); c0 = sum(1 for x, (r, l) in order if r == src["tier"] and l < src["drop_t"])
                sx, sy = slot_xy(ri0, c0); ss = 1.0
            else:
                sx, sy, ss = HOLD_XY[0], HOLD_XY[1], 1.4
            k = ease(age / 0.45)
            sc = ss + (1 - ss) * k
            comp(frame, tile(e, sc), sx + (tx - sx) * k, sy + (ty - sy) * k - math.sin(k * math.pi) * 80)
        else:
            comp(frame, tile(e), tx, ty)
    # presenter: item text, reason, judge window
    cur = next((p for p in plan if p["t0"] <= t < p["t1"]), plan[-1] if t >= plan[-1]["t0"] else None)
    if cur is None:
        return
    age = t - cur["t0"]
    py = PRES_Y
    a = ease(age / 0.3)
    head = "next up" if "id" in cur else "breaking"
    d.text((SIDE + 10, py), head.upper(), font=font(32, "Bold"), fill=(255, 196, 0) if "id" in cur else (255, 90, 80))
    tf = font(42, "Bold")
    ly = py + 48
    for ln in wrap(cur["text"], tf, 470)[:3]:
        draw_rich(frame, SIDE + 10 - (1 - a) * 30, ly, [ln], tf, (255, 255, 255), 52); ly += 52
    if t >= cur["reason_t"]:
        rf = font(34)
        ra = ease((t - cur["reason_t"]) / 0.3)
        layer = Image.new("RGBA", (500, 140), (0, 0, 0, 0))
        draw_rich(layer, 0, 0, wrap(cur["reason"], rf, 470)[:3], rf, (200, 200, 210), 44)
        layer.putalpha(layer.getchannel("A").point(lambda v, ra=ra: int(v * ra)))
        comp(frame, layer, SIDE + 10, ly + 10)
    if "id" in cur and t < cur["drop_t"]:
        comp(frame, tile(P["tiles"][cur["id"]], 1.4), *HOLD_XY)
    win = cat_window(cur["bg"], cur["cat"].at(age), JUDGE_W, JUDGE_H, fit=0.95, r=32)
    comp(frame, win, RAIL_X - JUDGE_W, PRES_Y)
    comp(frame, name_chip("judge: " + s.get("judge", "the cat"), size=24), RAIL_X - JUDGE_W + 14, PRES_Y + 14)
    if cur.get("bang") and age > 0.6:                 # patakha flashes
        fl = max(0.0, 1 - ((age - 0.6) % 1.1) / 0.25)
        if fl > 0:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 210, 120, int(60 * fl))))


# ── the reel ──────────────────────────────────────────────────────────────────
FORMATS = {"search": (plan_search, draw_search, (255, 255, 255)),
           "lockscreen": (plan_lock, draw_lock, (0, 0, 0)),
           "tierlist": (plan_tier, draw_tier, TL_BG)}


def load_format(name):
    """Built-in formats live above; any other `format` is engine/formats/<name>.py,
    a module exposing PLAN(s, slug) -> (state, track, end_t), DRAW(frame, t, s, state), BG."""
    if name in FORMATS:
        return FORMATS[name]
    import importlib
    m = importlib.import_module(f"formats.{name}")
    return m.PLAN, m.DRAW, m.BG


def render(path):
    s = json.load(open(path))
    slug = os.path.splitext(os.path.basename(path))[0]
    plan_fn, draw_fn, bgcol = load_format(s["format"])
    P, track, end_t = plan_fn(s, slug)
    total = int(end_t * FPS)
    os.makedirs(OUTPUT, exist_ok=True)
    work = os.path.join(WORK, "simple", slug)
    os.makedirs(work, exist_ok=True)
    silent = os.path.join(work, "video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                           "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    for fi in range(total):
        t = fi / FPS
        frame = Image.new("RGBA", (W, H), bgcol + (255,))
        draw_fn(frame, t, s, P)
        ff.stdin.write(frame.convert("RGB").tobytes())
        if fi % 150 == 0:
            print(f"  frame {fi}/{total}", flush=True)
    ff.stdin.close(); ff.wait()

    n = int(end_t * SR)
    mix = np.zeros((n, 2), dtype=np.float32)
    for t0, a in track:
        i0 = int(max(0, t0) * SR)
        if i0 >= n:
            continue
        seg = a[: n - i0]
        mix[i0:i0 + len(seg)] += seg
    mix = np.tanh(mix * 1.1) * 0.92
    wav = os.path.join(work, "audio.f32")
    mix.astype(np.float32).tofile(wav)
    out = os.path.join(OUTPUT, s.get("output", slug + ".mp4"))
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", silent,
                    "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", out], check=True)
    print(f"  -> {out}  ({end_t:.1f}s)")
    return out


def used_clips(s):
    ids = set(s.get("clips_used", []))
    for k in ("steps", "events", "items"):
        for e in s.get(k, []):
            for sub in (e, e.get("call") or {}, e.get("wallpaper") or {}, e.get("sound") or {}):
                if sub.get("clip"):
                    ids.add(sub["clip"])
    if s.get("wallpaper"):
        ids.add(s["wallpaper"]["clip"])
    return sorted(ids)


def register(path):
    """Queue the reel in data/videos.db with the script's `youtube` block (same as chat_render)."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from engine import db as DB
    s = json.load(open(path))
    slug = os.path.splitext(os.path.basename(path))[0]
    yt = s.get("youtube", {})
    con = DB.connect(); DB.init(con)
    v = DB.get_video(con, slug)
    if v and v["status"] in ("posted", "scheduled"):
        print(f"  {slug} is already {v['status']}; DB left as is")
    else:
        DB.upsert_video(con, {
            "slug": slug, "sort_order": v["sort_order"] if v else DB.max_sort_order(con) + 1,
            "pov": yt.get("pov", s["title"]), "title": yt.get("title", f"{s['title']} 🐱 #shorts"),
            "description": yt.get("description", ""), "tags": yt.get("tags", []),
            "file": f"output/{s.get('output', slug + '.mp4')}", "status": "queued", "kind": "short",
        })
        print(f"  queued {slug} in videos.db")
    DB.record_clips(con, slug, used_clips(s))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("usage: python3 engine/simple_render.py data/formats/<slug>.json [--register]")
    render(args[0])
    if "--register" in sys.argv:
        register(args[0])
