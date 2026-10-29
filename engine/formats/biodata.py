"""Matrimonial biodata: Mummy fills in your biodata field by field. Each value is
typed, held long enough to read, then backspaced and "improved". The photo in the
frame is a live cat that reacts to every edit; the last field can swap the photo.

Script keys: fields[] of {label, value, fix?, clip, start, bg, swap?}, events not used.
"""
import numpy as np
from PIL import Image, ImageDraw

from simple_render import Cat, cat_window, window_bg, fit_font, ease, tick
from chat_render import W, H, FPS, SR, font, emoji, wrap, draw_rich, line_w, comp, click, tone, ease_out_back

BG = (250, 243, 224)
MAROON, INK, GOLD = (128, 20, 32), (40, 30, 30), (196, 150, 60)
PH = ((W - 360) // 2, 330, 360, 420)        # photo frame
ROW0, ROW_H, LBL_X, VAL_X = 830, 84, 84, 330
VAL_R = 880                                  # shorts safe zone: keeps clear of the like/share rail (engine/safe_zone.py)
TYPE, BACK = 0.065, 0.028


def plan(s, slug):
    t, rows, track = 1.4, [], []
    for i, f in enumerate(s["fields"]):
        r = dict(f, t0=t)
        r["type_end"] = t + len(f["value"]) * TYPE
        for k in range(len(f["value"])):
            track.append((t + k * TYPE, click(0.09)))
        t = r["type_end"] + f.get("hold", 1.6)
        if f.get("fix"):
            r["back0"] = t
            r["back_end"] = t + len(f["value"]) * BACK
            for k in range(len(f["value"])):
                track.append((t + k * BACK, click(0.06)))
            r["fix0"] = r["back_end"] + 0.25
            r["fix_end"] = r["fix0"] + len(f["fix"]) * TYPE
            for k in range(len(f["fix"])):
                track.append((r["fix0"] + k * TYPE, click(0.09)))
            t = r["fix_end"] + f.get("hold2", 1.3)
        if f.get("swap"):
            r["swap_t"] = r["type_end"] + 0.6
            t = r["swap_t"] + f.get("hold2", 4.2)
        r["t1"] = t
        rows.append(r)
        t += 0.3
    end_t = t + 0.2
    photos = []
    for i, r in enumerate(rows):
        start_t = r.get("swap_t", r["t0"])
        nxt = rows[i + 1].get("swap_t", rows[i + 1]["t0"]) if i + 1 < len(rows) else end_t
        cat = Cat(slug, f"photo{i:02d}", r["clip"], r.get("start", 0), nxt - start_t + 0.3, PH[3])
        photos.append(dict(t=start_t, cat=cat, bg=window_bg(r.get("bg", "home.jpg"), PH[2], PH[3], blur=6)))
        track.append((start_t + 0.05, cat.audio(min(cat.dur, nxt - start_t)) * r.get("vol", 1.0)))
        if r.get("swap"):
            track.append((start_t, tone(1600, 1600, 0.05, 0.25, 30)))      # camera shutter-ish
            track.append((start_t + 0.03, tone(400, 200, 0.12, 0.3, 20)))
    # soft drone under the whole thing so the typing isn't in a vacuum
    n = int(end_t * SR); x = np.arange(n) / SR
    drone = (np.sin(2 * np.pi * 146.8 * x) * 0.025 + np.sin(2 * np.pi * 220 * x) * 0.018) * \
        (1 + 0.2 * np.sin(2 * np.pi * 0.3 * x))
    fade = int(0.8 * SR)
    drone[:fade] *= np.linspace(0, 1, fade); drone[-fade:] *= np.linspace(1, 0, fade)
    track.append((0.0, np.repeat(drone[:, None], 2, axis=1).astype(np.float32)))
    return dict(rows=rows, photos=photos), track, end_t


def value_at(r, t):
    """What the value field shows at time t (typing, holding, backspacing, retyping)."""
    v = r["value"]
    if t < r["t0"]:
        return None, False
    if t < r["type_end"]:
        return v[:int((t - r["t0"]) / TYPE) + 1], True
    if not r.get("fix") or t < r["back0"]:
        return v, False
    if t < r["back_end"]:
        return v[:max(0, len(v) - int((t - r["back0"]) / BACK) - 1)], True
    if t < r["fix0"]:
        return "", True
    if t < r["fix_end"]:
        return r["fix"][:int((t - r["fix0"]) / TYPE) + 1], True
    return r["fix"], False


def draw(frame, t, s, st):
    d = ImageDraw.Draw(frame)
    d.rectangle((26, 26, W - 26, H - 26), outline=MAROON, width=8)
    d.rectangle((44, 44, W - 44, H - 44), outline=GOLD, width=3)
    for cx, cy in ((44, 44), (W - 44, 44), (44, H - 44), (W - 44, H - 44)):
        comp(frame, emoji("🌸", 56), cx - 28, cy - 28)
    pf = fit_font(s["pov"], W - 160, 40, "Bold")
    d.text(((W - pf.getlength(s["pov"])) / 2, 164), s["pov"], font=pf, fill=INK)
    sf = font(28, "Semibold")
    head = "|| shree ganeshaya namah ||"
    d.text(((W - sf.getlength(head)) / 2, 222), head, font=sf, fill=MAROON)
    comp(frame, emoji("🪔", 34), (W - sf.getlength(head)) / 2 - 48, 220)
    comp(frame, emoji("🪔", 34), (W + sf.getlength(head)) / 2 + 14, 220)
    bf = font(56, "Heavy")
    d.text(((W - bf.getlength("BIODATA")) / 2, 256), "BIODATA", font=bf, fill=MAROON)
    # photo
    x, y, w, h = PH
    d.rectangle((x - 16, y - 16, x + w + 16, y + h + 16), fill=GOLD)
    d.rectangle((x - 6, y - 6, x + w + 6, y + h + 6), fill=MAROON)
    ph = [p for p in st["photos"] if p["t"] <= t]
    p = ph[-1] if ph else st["photos"][0]
    win = cat_window(p["bg"], p["cat"].at(t - p["t"]), w, h, fit=0.95, r=2)
    comp(frame, win, x, y)
    swap = next((r for r in st["rows"] if r.get("swap") and t >= r["swap_t"]), None)
    if swap:
        age = t - swap["swap_t"]
        if age < 0.25:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * (1 - age / 0.25)))))
        k = ease_out_back(min(1, max(0, age - 0.5) / 0.35))
        if age > 0.5:
            stamp = Image.new("RGBA", (380, 120), (0, 0, 0, 0))
            sd = ImageDraw.Draw(stamp)
            sd.rounded_rectangle((0, 0, 379, 119), 16, outline=(210, 30, 30), width=8)
            stf = font(64, "Heavy")
            sd.text(((380 - stf.getlength("UPDATED")) / 2, 18), "UPDATED", font=stf, fill=(210, 30, 30))
            stamp = stamp.rotate(-14, expand=True, resample=Image.BICUBIC)
            sc = 1.6 - 0.6 * k
            stamp = stamp.resize((int(stamp.width * sc), int(stamp.height * sc)), Image.BILINEAR)
            comp(frame, stamp, x + w - stamp.width + 60, y + h - stamp.height + 30)
    # fields
    lf, vf = font(38, "Bold"), font(38)
    vw = VAL_R - VAL_X
    for i, r in enumerate(st["rows"]):
        ry = ROW0 + i * ROW_H
        if t < r["t0"] - 0.4:
            continue
        a = ease((t - r["t0"] + 0.4) / 0.3)
        col = tuple(int(255 - (255 - c) * a) for c in MAROON)
        d.text((LBL_X, ry), r["label"], font=lf, fill=col)
        d.text((VAL_X - 30, ry), ":", font=lf, fill=col)
        d.line((VAL_X, ry + 52, VAL_R, ry + 52), fill=(225, 210, 180), width=2)
        v, active = value_at(r, t)
        if v is None:
            continue
        vf2 = fit_font(v or " ", vw, 38) if len(wrap(v or " ", vf, vw)) > 1 else vf
        draw_rich(frame, VAL_X, ry, wrap(v or " ", vf2, vw)[:1], vf2, INK, 46)
        if r["t0"] <= t < r["t1"]:
            cx = VAL_X + line_w(wrap(v or " ", vf2, vw)[0]) + 4 if v else VAL_X
            if active or int(t * 2.4) % 2 == 0:
                d.line((cx, ry + 4, cx, ry + 46), fill=MAROON, width=3)
            tag = "✏️ mummy is editing: " + r["label"]       # one pill under the photo, not per row
            tf = font(28, "Semibold")
            tw = line_w(wrap(tag, tf, 600)[0]) + 32
            ty = PH[1] + PH[3] + 26
            d.rounded_rectangle(((W - tw) / 2, ty, (W + tw) / 2, ty + 44), 22, fill=MAROON)
            draw_rich(frame, (W - tw) / 2 + 16, ty + 6, wrap(tag, tf, 600), tf, (255, 255, 255), 34)


PLAN, DRAW = plan, draw
