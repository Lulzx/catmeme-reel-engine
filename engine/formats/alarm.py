"""alarm: the phone's Clock app on the night of something important. The alarm
list is set up, each alarm rings with the label past-you wrote, gets snoozed,
the battery drains with every ring, and the phone dies before the last one.
Then it's 9:47, charging, and the notifications explain what it cost.
The sleeping cat lives in a window at the bottom the whole time.

Script: `alarms` [{time, label}], `sleep` / `wake` clips, timed `events` with a
`state` of list | ring | idle | dead | charging, see data/formats/*.json.
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw

from simple_render import (Cat, cat_window, window_bg, name_chip, fit_font, ease, tick, tone,
                           noise, W, H, SR, CLIPS, clip, decode)
from chat_render import font, emoji, wrap, draw_rich, line_w, comp, ease_out_back

BG = (8, 8, 12)
ORANGE, GREEN, RED, MUTED = (255, 159, 10), (52, 199, 89), (255, 69, 58), (142, 142, 147)
WIN = (60, 1000, 820, 410)                      # x, y, w, h of the cat window, clear of the Shorts rail
SAFE_L, SAFE_R, SAFE_T = 60, W - 60, 150        # engine/safe_zone.py
ICON = {"battery": ((52, 199, 89), "🔋"), "uber": ((0, 0, 0), "🚕"), "whatsapp": ((37, 211, 102), "💬"),
        "phone": ((52, 199, 89), "📞"), "indigo": ((32, 42, 138), "✈️")}


def alarm_beeps(dur):
    """iOS-ish radar alarm: triple beep, pause, repeat."""
    out = np.zeros((int(dur * SR), 2), dtype=np.float32)
    t = 0.0
    while t < dur:
        for k in range(3):
            b = tone(1480, 1480, 0.09, 0.28, 8)
            i0 = int((t + k * 0.14) * SR)
            seg = b[: max(0, len(out) - i0)]
            out[i0:i0 + len(seg)] += seg
        t += 0.8
    return out


def power_down():
    return tone(420, 70, 0.6, 0.25, 4)


def chime():
    return np.concatenate([tone(988, 988, 0.1, 0.16, 14), tone(1319, 1319, 0.25, 0.14, 8)])


def battery_icon(d, x, y, pct, charging=False, col=(255, 255, 255), scale=1.0):
    w, h = 60 * scale, 28 * scale
    d.rounded_rectangle((x, y, x + w, y + h), 8 * scale, outline=col, width=max(2, int(3 * scale)))
    d.rectangle((x + w + 3 * scale, y + 8 * scale, x + w + 7 * scale, y + h - 8 * scale), fill=col)
    fill = GREEN if charging else (RED if pct <= 10 else col)
    iw = max(3 * scale, (w - 12 * scale) * pct / 100)
    d.rectangle((x + 6 * scale, y + 6 * scale, x + 6 * scale + iw, y + h - 6 * scale), fill=fill)


def status(d, clock, pct, charging=False):
    d.text((70, 24), clock, font=font(36, "Semibold"), fill=(255, 255, 255))
    pf = font(30, "Semibold")
    txt = f"{pct}%"
    bx = W - 110
    d.text((bx - 18 - pf.getlength(txt), 26), txt, font=pf, fill=RED if pct <= 10 and not charging else (255, 255, 255))
    battery_icon(d, bx, 30, pct, charging)


def notif(app, title, body, when="now", small=False):
    cw = SAFE_R - SAFE_L
    bf = font(32 if small else 37)
    lh = 42 if small else 50
    lines = wrap(body, bf, cw - 190)
    h = (64 if small else 74) + lh * len(lines) + (18 if small else 24)
    im = Image.new("RGBA", (cw, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, cw - 1, h - 1), 44, fill=(242, 242, 246, 235))
    col, em = ICON[app]
    d.rounded_rectangle((28, (h - 84) / 2, 112, (h + 84) / 2), 20, fill=col)
    comp(im, emoji(em, 52), 44, (h - 52) / 2)
    tf = font(32 if small else 37, "Semibold")
    d.text((136, 18 if small else 22), title, font=tf, fill=(20, 20, 24))
    mf = font(28)
    d.text((cw - 30 - mf.getlength(when), 22), when, font=mf, fill=(120, 120, 128))
    draw_rich(im, 136, 62 if small else 74, lines, bf, (20, 20, 24), lh)
    return im


def battery_chip(frame, pct, charging=False):
    """The drain is the setup, so the % lives inside the safe area, not just the status bar."""
    d = ImageDraw.Draw(frame)
    f = font(40, "Semibold")
    txt = f"{pct}%"
    x1 = SAFE_R - 10
    bx = x1 - 86
    battery_icon(d, bx, 248, pct, charging, scale=1.3)
    d.text((bx - 14 - f.getlength(txt), 236), txt, font=f, fill=RED if pct <= 10 and not charging else (255, 255, 255))


def PLAN(s, slug):
    evs, track = s["events"], []
    end_t = next(e["t"] for e in evs if e.get("end"))
    sl, wk = s["sleep"], s["wake"]
    wake_t = next(e["wake_at"] for e in evs if e.get("wake_at"))
    P = {"evs": [e for e in evs if not e.get("end")],
         "sleep": Cat(slug, "sleep", sl["clip"], sl["start"], sl["dur"], 420),
         "wake": Cat(slug, "wake", wk["clip"], wk["start"], wk["dur"], 420),
         "night": window_bg(sl.get("bg", "home.jpg"), WIN[2], WIN[3], blur=5, dim=0.45),
         "day": window_bg(wk.get("bg", "home.jpg"), WIN[2], WIN[3], blur=5),
         "wake_t": wake_t}
    # purring bed under the whole night, looped from the sleeping clip
    purr = decode(os.path.join(CLIPS, clip(sl["clip"])["file"]), sl["start"], sl["dur"], 0.3) * 0.9
    t = 0.0
    while t < wake_t - 0.2:
        seg = purr[: int((wake_t - t) * SR)]
        track.append((t, seg)); t += len(purr) / SR
    track.append((wake_t, P["wake"].audio()))
    for e in evs:
        st = e.get("state")
        if st == "ring":
            track.append((e["t"], alarm_beeps(e["until"] - e["t"])))
            track.append((e["until"] - 0.05, tick() * 3 if e["action"] == "snooze" else power_down()))
        if e.get("banner"):
            track.append((e["t"] + 0.3, chime()))
        if st == "charging":
            track.append((e["t"], tone(523, 784, 0.25, 0.18, 6)))
            for k in range(len(e["notifs"])):
                track.append((e["t"] + 0.8 + k * e["notif_gap"], chime()))
    return P, track, end_t


def draw_cat_window(frame, t, s, P):
    x, y, w, h = WIN
    if t < P["wake_t"]:
        im = cat_window(P["night"], P["sleep"].at(t, loop=True), w, h, fit=0.8)
        chip = name_chip("you · asleep")
    else:
        im = cat_window(P["day"], P["wake"].at(t - P["wake_t"]), w, h, fit=0.95)
        chip = name_chip("you · 9:47 am")
    comp(frame, im, x, y)
    comp(frame, chip, x + 30, y + 30)


def centered(d, text, y, f, col):
    d.text(((W - f.getlength(text)) / 2, y), text, font=f, fill=col)


def DRAW(frame, t, s, P):
    cur = [e for e in P["evs"] if e["t"] <= t][-1]
    st, age = cur["state"], t - cur["t"]
    d = ImageDraw.Draw(frame)
    if st != "dead":
        status(d, cur.get("clock", s["alarms"][cur["alarm"]]["time"] if st == "ring" else "4:58"),
               cur.get("battery", 14), charging=(st == "charging"))
    pf = fit_font(s["pov"], SAFE_R - SAFE_L - 40, 44, "Bold")
    y = 165
    for ln in wrap(s["pov"], pf, SAFE_R - SAFE_L - 40):
        draw_rich(frame, (W - line_w(ln)) / 2, y, [ln], pf, (255, 255, 255), 58); y += 58

    if st != "dead":
        battery_chip(frame, cur.get("battery", 14), charging=(st == "charging"))

    if st == "list":
        d.text((SAFE_L, 236), "Alarms", font=font(64, "Bold"), fill=(255, 255, 255))
        for i, a in enumerate(s["alarms"]):
            ry = 330 + i * 128
            k = ease((age - 0.3 - i * 0.35) / 0.3)
            if k <= 0:
                continue
            rw = SAFE_R - SAFE_L
            row = Image.new("RGBA", (rw, 128), (0, 0, 0, 0))
            rd = ImageDraw.Draw(row)
            rd.text((0, 2), a["time"], font=font(64, "Light"), fill=(255, 255, 255))
            rd.text((4, 80), a["label"], font=fit_font(a["label"], rw - 200, 36), fill=(190, 190, 196))
            rd.rounded_rectangle((rw - 124, 34, rw - 4, 96), 31, fill=GREEN)
            rd.ellipse((rw - 64, 38, rw - 8, 92), fill=(255, 255, 255))
            rd.line((0, 126, rw, 126), fill=(44, 44, 48), width=2)
            row.putalpha(row.getchannel("A").point(lambda v, k=k: int(v * k)))
            comp(frame, row, 60, ry + (1 - k) * 30)

    elif st == "ring":
        a = s["alarms"][cur["alarm"]]
        shake = math.sin(age * 40) * 6 if (age % 0.8) < 0.4 else 0
        comp(frame, emoji("⏰", 72), W / 2 - 36 + shake, 236)
        centered(d, a["time"], 300, font(200, "Semibold"), (255, 255, 255))
        lf = font(50, "Semibold")
        ly = 560
        for ln in wrap(a["label"], lf, SAFE_R - SAFE_L - 60):
            draw_rich(frame, (W - line_w(ln)) / 2, ly, [ln], lf, (255, 255, 255), 62); ly += 62
        if cur.get("snoozed"):
            centered(d, f"snoozed {cur['snoozed']} time{'s' if cur['snoozed'] > 1 else ''}", ly + 10, font(34), MUTED)
        press = cur["until"] - t < 0.25 and cur["action"] == "snooze"
        col = (200, 120, 0) if press else ORANGE
        d.rounded_rectangle((140, 760, W - 140, 870), 55, fill=col)
        centered(d, "Snooze", 784, font(54, "Semibold"), (0, 0, 0))
        centered(d, "Stop", 900, font(42, "Semibold"), ORANGE)
        if cur["action"] == "dead" and cur["until"] - t < 0.35:   # screen flickers out
            fl = (cur["until"] - t) / 0.35
            frame.alpha_composite(Image.new("RGBA", (W, WIN[1] - 10), (0, 0, 0, int(255 * (1 - fl)))))

    elif st == "idle":
        centered(d, s["date"], 300, font(44, "Semibold"), (235, 235, 240))
        centered(d, cur["clock"], 350, font(200, "Semibold"), (255, 255, 255))
        b = cur.get("banner")
        if b and age > 0.3:
            k = ease_out_back(min(1, (age - 0.3) / 0.35))
            card = notif(b["app"], b["title"], b["body"])
            comp(frame, card, SAFE_L, 640 - (1 - k) * 80)

    elif st == "dead":
        fade = ease(age / 0.6)
        bx, by = W / 2 - 110, 480
        d.rounded_rectangle((bx, by, bx + 200, by + 96), 22, outline=(90, 90, 96), width=8)
        d.rectangle((bx + 208, by + 30, bx + 222, by + 66), fill=(90, 90, 96))
        if int(age * 1.5) % 2 == 0:
            d.rectangle((bx + 16, by + 16, bx + 30, by + 80), fill=RED)
        if age > 1.2:
            centered(d, "5:40 am", 640, font(40), (90, 90, 96))

    elif st == "charging":
        d.text((SAFE_L, 236), s["date"], font=font(40, "Semibold"), fill=(235, 235, 240))
        centered(d, cur["clock"], 280, font(150, "Semibold"), (255, 255, 255))
        cf = font(34, "Semibold")
        txt = f"⚡ charging · {cur['battery']}%"
        ln = wrap(txt, cf, W)
        draw_rich(frame, (W - line_w(ln[0])) / 2, 448, ln, cf, GREEN, 44)
        ny = 504
        shown = [n for k, n in enumerate(cur["notifs"]) if age >= 0.8 + k * cur["notif_gap"]]
        for k, n in enumerate(shown[::-1]):
            card = notif(n["app"], n["title"], n["body"], n.get("when", "now"), small=True)
            if ny + card.height > WIN[1] - 6:
                break
            na = age - 0.8 - (len(shown) - 1 - k) * cur["notif_gap"]
            if k == 0 and na < 0.35:
                kk = ease_out_back(na / 0.35)
                card.putalpha(card.getchannel("A").point(lambda v, a=min(1, na / 0.2): int(v * a)))
                comp(frame, card, SAFE_L, ny - (1 - kk) * 60)
            else:
                comp(frame, card, SAFE_L, ny)
            ny += card.height + 10
    draw_cat_window(frame, t, s, P)
