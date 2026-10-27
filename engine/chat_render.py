#!/usr/bin/env python3
"""Group-chat reels: the story plays out as a family group chat where every
member is a cat. Texts pop in, video notes play the keyed cat clip (with its
real audio) inside a circle, and the header shows who is typing.

    python3 engine/chat_render.py data/chats/<slug>.json              ->  output/<slug>.mp4
    python3 engine/chat_render.py data/chats/<slug>.json --register   ... + queue it in videos.db

A chat script is a cast (`people`) plus timed `events`:
  chip | image | text | compose | status | typing | video | system | delete | react | end
`t: -1` means "already in the chat when the reel starts". See data/chats/*.json.

Frames are drawn with Pillow and piped into ffmpeg; the audio bed is mixed in
numpy from the clips' own sound plus synthesized message pops.
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import BACKGROUNDS, CLIPS, OUTPUT, WORK
import cutouts as C

W, H, FPS, SR = 1080, 1920, 30, 48000

# ── layout ────────────────────────────────────────────────────────────────────
STATUS_H, HEADER_H, INPUT_H = 64, 150, 170
VIEW_Y0 = STATUS_H + HEADER_H           # chat viewport top
VIEW_Y1 = H - INPUT_H                   # chat viewport bottom
AVATAR = 76
IN_X = 20 + AVATAR + 14                 # incoming bubble left edge
OUT_R = W - 26                          # outgoing bubble right edge
MAX_TEXT_W = 680
GAP, GAP_SENDER = 12, 26
NOTE_D = 600                            # video note diameter

# ── palette ───────────────────────────────────────────────────────────────────
WALL, HEADER_BG = (239, 234, 226), (0, 128, 105)
OUT_BG, IN_BG = (217, 253, 211), (255, 255, 255)
INK, META, TICK = (17, 27, 33), (102, 119, 129), (83, 189, 235)
CHIP_BG, CHIP_INK = (255, 255, 255), (84, 101, 111)
SYS_BG = (255, 243, 196)
GREEN = (0, 168, 132)

SF = "/System/Library/Fonts/SFNS.ttf"
SF_IT = "/System/Library/Fonts/SFNSItalic.ttf"
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"
SCRIPT = "/System/Library/Fonts/Supplemental/SnellRoundhand.ttc"

_F, _E = {}, {}


def font(size, weight="Regular", italic=False):
    key = (size, weight, italic)
    if key not in _F:
        f = ImageFont.truetype(SF_IT if italic else SF, size)
        if weight.encode() in f.get_variation_names():   # Pillow returns bytes names
            f.set_variation_by_name(weight.encode())
        _F[key] = f
    return _F[key]


def emoji(cluster, size):
    key = (cluster, size)
    if key not in _E:
        ef = _F.setdefault("emoji", ImageFont.truetype(EMOJI, 160))
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), cluster, font=ef, embedded_color=True)
        _E[key] = im.resize((size, size), Image.LANCZOS)
    return _E[key]


def comp(dst, src, x, y):
    """alpha_composite that tolerates negative / overflowing offsets."""
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    dst.alpha_composite(src.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))


# ── rich text (words + colour emoji) ──────────────────────────────────────────
def _is_emoji(c):
    o = ord(c)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0x2B50, 0x2B55)


def tokens(text):
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if _is_emoji(c):
            j = i + 1
            while j < len(text):
                o = ord(text[j])
                if o in (0xFE0F, 0x20E3) or 0x1F3FB <= o <= 0x1F3FF:
                    j += 1
                elif o == 0x200D and j + 1 < len(text):
                    j += 2
                else:
                    break
            out.append(("e", text[i:j])); i = j
        elif c in " \n":
            out.append(("s", c)); i += 1
        else:
            j = i
            while j < len(text) and text[j] not in " \n" and not _is_emoji(text[j]):
                j += 1
            out.append(("w", text[i:j])); i = j
    return out


def wrap(text, f, maxw):
    es, sp = round(f.size * 1.18), f.getlength(" ")
    lines, x = [[]], 0
    for kind, s in tokens(text):
        if kind == "s":
            if s == "\n":
                lines.append([]); x = 0
            else:
                lines[-1].append(("s", s, sp)); x += sp
            continue
        w = f.getlength(s) if kind == "w" else es + 4
        if x + w > maxw and any(t[0] != "s" for t in lines[-1]):
            lines.append([]); x = 0
        lines[-1].append((kind, s, w)); x += w
    for ln in lines:
        while ln and ln[0][0] == "s": ln.pop(0)
        while ln and ln[-1][0] == "s": ln.pop()
    return lines


def line_w(ln):
    return sum(t[2] for t in ln)


def draw_rich(im, x0, y, lines, f, fill, lh):
    d, es = ImageDraw.Draw(im), round(f.size * 1.18)
    asc = f.getmetrics()[0]
    for ln in lines:
        x = x0
        for kind, s, w in ln:
            if kind == "w":
                d.text((x, y), s, font=f, fill=fill)
            elif kind == "e":
                comp(im, emoji(s, es), x + 2, y + asc - es * 0.86)
            x += w
        y += lh


def rich_size(text, f, maxw, lh):
    lines = wrap(text, f, maxw)
    return lines, max((line_w(l) for l in lines), default=0), lh * len(lines)


# ── assets: sprites, avatars, backgrounds ─────────────────────────────────────
_CAT = None


def clip(cid):
    global _CAT
    _CAT = _CAT or {c["id"]: c for c in C.load_catalog()}
    return _CAT[cid]


def sprite(cid):
    p = os.path.join(C.SPRITES, f"{cid}.png")
    if not os.path.exists(p):
        C.extract_sprite(clip(cid))
    return Image.open(p).convert("RGBA")


def circle_mask(d, ss=4):
    m = Image.new("L", (d * ss, d * ss), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d * ss - 1, d * ss - 1), fill=255)
    return m.resize((d, d), Image.LANCZOS)


def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


PASTELS = [(255, 224, 178), (200, 230, 201), (187, 222, 251), (248, 187, 208), (225, 190, 231)]


def avatar(cid, d=AVATAR, tint=0):
    sp = sprite(cid)
    side = min(sp.width, sp.height)
    head = sp.crop(((sp.width - side) // 2, 0, (sp.width - side) // 2 + side, side))
    av = Image.new("RGBA", (d, d), PASTELS[tint % len(PASTELS)] + (255,))
    comp(av, head.resize((d, d), Image.LANCZOS), 0, d * 0.06)
    av.putalpha(circle_mask(d))
    return av


def wallpaper():
    im = Image.new("RGBA", (W, VIEW_Y1 - VIEW_Y0), WALL + (255,))
    glyphs = ["🐾", "🐟", "🧶", "🐭", "🥛"]
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    i = 0
    for row, y in enumerate(range(-20, im.height, 150)):
        for x in range(-40 + (row % 2) * 90, W, 180):
            g = emoji(glyphs[i % len(glyphs)], 54).convert("LA").convert("RGBA")
            g = g.rotate((i * 37) % 60 - 30, resample=Image.BICUBIC, expand=True)
            comp(layer, g, x, y); i += 1
    a = layer.getchannel("A").point(lambda v: v * 0.07)
    layer.putalpha(a)
    im.alpha_composite(layer)
    return im


def good_morning_card(cat_id, size=640):
    bg = cover(Image.open(os.path.join(BACKGROUNDS, "mountain.jpg")).convert("RGBA"), size, size)
    warm = Image.new("RGBA", (size, size))
    wd = ImageDraw.Draw(warm)
    for y in range(size):
        k = y / size
        wd.line([(0, y), (size, y)], fill=(255, int(140 + 60 * k), int(60 + 120 * k), 110))
    bg.alpha_composite(warm)
    cat = sprite(cat_id)
    s = size * 0.56 / cat.height
    cat = cat.resize((int(cat.width * s), int(cat.height * s)), Image.LANCZOS)
    comp(bg, cat, size - cat.width + 10, size - cat.height)
    d = ImageDraw.Draw(bg)
    gm = ImageFont.truetype(SCRIPT, 118, index=1)
    for i, word in enumerate(["Good", "Morning"]):
        x, y = 40 + i * 50, 40 + i * 110
        d.text((x + 4, y + 5), word, font=gm, fill=(120, 0, 30, 200))
        d.text((x, y), word, font=gm, fill=(255, 214, 79), stroke_width=4, stroke_fill=(178, 34, 52))
    for e, x, y, sz in [("🌹", 30, size - 120, 90), ("🌹", 120, size - 100, 70), ("✨", size - 120, 30, 80),
                        ("✨", 420, 200, 56), ("🙏", 40, 300, 70)]:
        comp(bg, emoji(e, sz), x, y)
    f = font(36, "Bold")
    d.text((40, 400), "have a blessed day", font=f, fill=(255, 255, 255), stroke_width=3,
           stroke_fill=(150, 40, 60))
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), 20, fill=255)
    bg.putalpha(m)
    return bg


# ── chat items ────────────────────────────────────────────────────────────────
FWD = "Forwarded many times"


def fwd_label(d, x, y, f):
    """WhatsApp's double-arrow forward mark, drawn (SF has no glyph for it)."""
    for dx in (0, 10):
        d.line([(x + dx, y + 26), (x + dx + 6, y + 16), (x + dx + 18, y + 16)], fill=META, width=3)
        d.line([(x + dx + 12, y + 10), (x + dx + 18, y + 16), (x + dx + 12, y + 22)], fill=META, width=3)
    d.text((x + 38, y), FWD, font=f, fill=META)


def ticks(d, x, y, col=TICK):
    for dx in (0, 11):
        d.line([(x + dx, y + 11), (x + dx + 7, y + 18), (x + dx + 20, y + 2)], fill=col, width=3)


def bubble_shape(w, h, side, fill):
    im = Image.new("RGBA", (w + 16, h + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ox = 0 if side == "right" else 16
    d.rounded_rectangle((ox, 3, ox + w, h + 3), 26, fill=(0, 0, 0, 22))
    d.rounded_rectangle((ox, 0, ox + w, h), 26, fill=fill)
    if side == "right":
        d.polygon([(w - 30, 0), (w + 14, 0), (w - 6, 26)], fill=fill)
    else:
        d.polygon([(46, 0), (2, 0), (22, 26)], fill=fill)
    return im, ox


def text_bubble(person, text, time, side, forwarded=False, deleted=False):
    body = font(44); lh = 56
    name_f, fwd_f, meta_f = font(33, "Semibold"), font(31, italic=True), font(27)
    if deleted:
        text = "🚫 This message was deleted"
        body = font(42, italic=True)
    lines, tw, th = rich_size(text, body, MAX_TEXT_W, lh)
    meta_w = meta_f.getlength(time) + (44 if side == "right" else 0)
    head = []
    if side == "left":
        head.append(("name", person["name"], name_f.getlength(person["name"]), 44))
    if forwarded:
        head.append(("fwd", FWD, fwd_f.getlength(FWD) + 38, 42))
    hw = max((h[2] for h in head), default=0)
    last = line_w(lines[-1]) if lines else 0
    inline = last + meta_w + 22 <= MAX_TEXT_W
    cw = max(tw, hw, last + meta_w + 22 if inline else meta_w)
    ch = sum(h[3] for h in head) + th + (0 if inline else 34)
    pad_x, pad_t, pad_b = 28, 16, 16
    bw, bh = int(cw + 2 * pad_x), int(ch + pad_t + pad_b)
    im, ox = bubble_shape(bw, bh, side, OUT_BG if side == "right" else IN_BG)
    d = ImageDraw.Draw(im)
    x, y = ox + pad_x, pad_t
    for kind, s, _, hh in head:
        if kind == "name":
            d.text((x, y), s, font=name_f, fill=person["color"])
        else:
            fwd_label(d, x, y, fwd_f)
        y += hh
    draw_rich(im, x, y, lines, body, META if deleted else INK, lh)
    my = bh - pad_b - 30
    mx = ox + bw - pad_x - meta_w
    d.text((mx, my), time, font=meta_f, fill=META)
    if side == "right":
        ticks(d, mx + meta_f.getlength(time) + 10, my + 6)
    return im


def chip(text, bg=CHIP_BG):
    f = font(31, "Medium")
    w = int(f.getlength(text)) + 48
    im = Image.new("RGBA", (w, 58), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 2, w - 1, 57), 18, fill=(0, 0, 0, 18))
    d.rounded_rectangle((0, 0, w - 1, 55), 18, fill=bg)
    d.text((24, 9), text, font=f, fill=CHIP_INK)
    return im


def image_bubble(person, card, time, forwarded):
    name_f, fwd_f, meta_f = font(33, "Semibold"), font(31, italic=True), font(27)
    top = 44 + (42 if forwarded else 0)
    bw, bh = card.width + 16, card.height + top + 24
    im, ox = bubble_shape(bw, bh, "left", IN_BG)
    d = ImageDraw.Draw(im)
    d.text((ox + 22, 14), person["name"], font=name_f, fill=person["color"])
    if forwarded:
        fwd_label(d, ox + 22, 58, fwd_f)
    comp(im, card, ox + 8, top + 14)
    tw = meta_f.getlength(time)
    d.text((ox + bw - tw - 26, bh - 50), time, font=meta_f, fill=(255, 255, 255),
           stroke_width=2, stroke_fill=(0, 0, 0, 120))
    return im


def typing_bubble(t):
    w, h = 150, 84
    im, ox = bubble_shape(w, h, "left", IN_BG)
    d = ImageDraw.Draw(im)
    for i in range(3):
        bounce = max(0.0, math.sin((t * 7) - i * 0.9)) * 10
        cx, cy = ox + 42 + i * 33, h / 2 - bounce
        d.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=(144, 160, 170))
    return im


class Item:
    def __init__(self, ev, side, person=None):
        self.ev, self.t0, self.side, self.person = ev, ev["t"], side, person
        self.t1 = ev.get("until") if ev["type"] == "typing" else None
        self.variants = []          # [(t, image)]
        self.badge = None           # (t, emoji)
        self.from_ = ev.get("from")

    def image(self, t):
        cur = None
        for vt, im in self.variants:
            if vt <= t:
                cur = im
        return cur

    def height(self, t):
        h = self.image(t).height
        if self.badge and t >= self.badge[0]:
            h += 34
        return h


class VideoNote(Item):
    def __init__(self, ev, person, slug, idx):
        super().__init__(ev, "left", person)
        c = clip(ev["clip"])
        self.dir = os.path.join(WORK, "chat", slug, f"note{idx:02d}")
        os.makedirs(self.dir, exist_ok=True)
        for f in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, f))
        vf = f"fps={FPS},{C._crop_expr(c, 0.08)},{C._key_chain(c)},scale=-1:{int(NOTE_D * 1.08)}"
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-ss", str(ev["start"]), "-t", str(ev["dur"]),
                        "-i", os.path.join(CLIPS, c["file"]), "-vf", vf,
                        os.path.join(self.dir, "%04d.png")], check=True, capture_output=True)
        self.frames = sorted(os.listdir(self.dir))
        bg = Image.open(os.path.join(BACKGROUNDS, ev.get("bg", "home.jpg"))).convert("RGBA")
        self.bg = cover(bg, NOTE_D, NOTE_D).filter(ImageFilter.GaussianBlur(5))
        self.mask = circle_mask(NOTE_D)
        self.name_f, self.meta_f = font(31, "Semibold"), font(29, "Semibold")
        self._cache = {}

    def frame_at(self, t):
        n = len(self.frames)
        k = min(n - 1, max(0, int((t - self.t0) * FPS)))
        if k in self._cache:
            return self._cache[k]
        sq = self.bg.copy()
        cat = Image.open(os.path.join(self.dir, self.frames[k])).convert("RGBA")
        s = min(NOTE_D * self.ev.get("fit", 0.95) / cat.height, NOTE_D * 1.3 / cat.width)
        cat = cat.resize((int(cat.width * s), int(cat.height * s)), Image.LANCZOS)
        comp(sq, cat, (NOTE_D - cat.width) / 2, NOTE_D - cat.height + NOTE_D * 0.06)
        sq.putalpha(self.mask)
        top = 54
        im = Image.new("RGBA", (NOTE_D + 20, NOTE_D + top + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        nm = self.person["name"]
        nw = self.name_f.getlength(nm) + 36
        d.rounded_rectangle((0, 0, nw, 46), 16, fill=(255, 255, 255))
        d.text((18, 6), nm, font=self.name_f, fill=self.person["color"])
        cy = top
        d.ellipse((0, cy + 4, NOTE_D + 12, NOTE_D + cy + 12), fill=(0, 0, 0, 30))
        d.ellipse((0, cy, NOTE_D + 8, NOTE_D + cy + 8), fill=(255, 255, 255))
        comp(im, sq, 4, cy + 4)
        prog = (k + 1) / n
        if prog < 1:
            d.arc((0, cy, NOTE_D + 8, NOTE_D + cy + 8), -90, -90 + 360 * prog, fill=GREEN, width=9)
        label = self.ev.get("label", "")
        lw = self.meta_f.getlength(label) + 70
        d.rounded_rectangle((40, cy + NOTE_D - 70, 40 + lw, cy + NOTE_D - 22), 24, fill=(0, 0, 0, 140))
        d.polygon([(60, cy + NOTE_D - 58), (60, cy + NOTE_D - 34), (80, cy + NOTE_D - 46)],
                  fill=(255, 255, 255))
        d.text((92, cy + NOTE_D - 64), label, font=self.meta_f, fill=(255, 255, 255))
        if k == n - 1 or k == 0:
            self._cache[k] = im
        return im

    def image(self, t):
        return self.frame_at(t)


# ── audio ─────────────────────────────────────────────────────────────────────
def decode(path, start, dur, fade_out=0.03):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-ss", str(start), "-t", str(dur), "-i", path,
                          "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()
    rms = float(np.sqrt(np.mean(a ** 2))) if len(a) else 0
    if rms > 1e-4:
        a *= min(4.0, 0.14 / rms)
    fade = min(len(a), int(0.03 * SR))
    if fade:
        a[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    tail = min(len(a), int(fade_out * SR))
    if tail:
        a[-tail:] *= np.linspace(1, 0, tail, dtype=np.float32)[:, None]
    return a


def tone(f0, f1, dur, vol, decay=30.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = np.linspace(f0, f1, n)
    w = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * decay) * vol
    att = min(n, int(0.004 * SR))
    w[:att] *= np.linspace(0, 1, att)
    return np.repeat(w[:, None], 2, axis=1).astype(np.float32)


def click(vol=0.12):
    n = int(0.012 * SR)
    rng = np.random.default_rng(len(_SFX))
    w = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 600) * vol
    return np.repeat(w[:, None], 2, axis=1).astype(np.float32)


_SFX = {}
SFX = {
    "send":    lambda: tone(520, 1150, 0.09, 0.22, 25),
    "receive": lambda: np.concatenate([tone(1000, 1000, 0.05, 0.2, 40), tone(1450, 1450, 0.08, 0.2, 35)]),
    "system":  lambda: tone(760, 760, 0.07, 0.10, 40),
    "delete":  lambda: tone(620, 240, 0.16, 0.22, 14),
    "react":   lambda: tone(820, 1700, 0.06, 0.2, 30),
}


def sfx(name):
    if name not in _SFX:
        _SFX[name] = SFX[name]()
    return _SFX[name]


# ── the reel ──────────────────────────────────────────────────────────────────
def ease_out_back(x):
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def render(path):
    s = json.load(open(path))
    slug = os.path.splitext(os.path.basename(path))[0]
    people = s["people"]
    for i, (pid, p) in enumerate(people.items()):
        p["side"] = "right" if pid == "me" else "left"
        if p.get("avatar"):
            p["avatar_im"] = avatar(p["avatar"], tint=i)
    events = s["events"]
    end_t = next(e["t"] for e in events if e["type"] == "end")
    total = int(end_t * FPS)

    items, by_id, statuses, composes, banners = [], {}, [], [], []
    track = []                                    # (t, samples)
    for idx, ev in enumerate(events):
        ty, p = ev["type"], people.get(ev.get("from"))
        it = None
        if ty == "chip":
            it = Item(ev, "center"); it.variants.append((-9, chip(ev["text"])))
        elif ty == "system":
            it = Item(ev, "center"); it.variants.append((-9, chip(ev["text"], SYS_BG)))
            track.append((ev["t"], sfx("system")))
        elif ty == "image":
            it = Item(ev, "left", p)
            card = good_morning_card(ev.get("card_cat", "101"))
            it.variants.append((-9, image_bubble(p, card, ev.get("time", ""), ev.get("forwarded"))))
        elif ty == "text":
            it = Item(ev, p["side"], p)
            it.variants.append((-9, text_bubble(p, ev["text"], ev.get("time", ""), p["side"],
                                                ev.get("forwarded"))))
            track.append((ev["t"], sfx("send" if p["side"] == "right" else "receive")))
        elif ty == "typing":
            it = Item(ev, "left", p); it.typing = True
        elif ty == "video":
            it = VideoNote(ev, p, slug, idx)
            c = clip(ev["clip"])
            track.append((ev["t"], sfx("receive")))
            track.append((ev["t"] + 0.05, decode(os.path.join(CLIPS, c["file"]), ev["start"], ev["dur"])))
        elif ty == "status":
            statuses.append(ev)
        elif ty == "compose":
            composes.append(ev)
            n = len(ev["text"])
            for k in range(n):
                track.append((ev["t"] + (ev["until"] - ev["t"]) * k / n, click()))
        elif ty == "delete":
            tgt = by_id[ev["target"]]
            tp = tgt.person
            tgt.variants.append((ev["t"], text_bubble(tp, "", tgt.ev.get("time", ""), tgt.side,
                                                      deleted=True)))
            track.append((ev["t"], sfx("delete")))
        elif ty == "react":
            tgt = by_id[ev["target"]]
            tgt.badge = (ev["t"], ev["emoji"])
            if ev.get("by"):
                banners.append((ev, people[ev["by"]], f'reacted {ev["emoji"]} to: "{tgt.ev["text"]}"'))
            track.append((ev["t"], sfx("react")))
            snd = ev.get("sound")
            if snd:
                c = clip(snd["clip"])
                track.append((ev["t"] + 0.1, decode(os.path.join(CLIPS, c["file"]), snd["start"], snd["dur"])))
        if it:
            items.append(it)
            if ev.get("id"):
                by_id[ev["id"]] = it

    wall = wallpaper()
    group = s["group"]
    gav = Image.new("RGBA", (92, 92), (220, 220, 220, 255))
    for i, cid in enumerate(group.get("avatars", [])[:4]):
        a = avatar(cid, 46, i).convert("RGBA")
        gav.paste(a, ((i % 2) * 46, (i // 2) * 46))
    gav.putalpha(circle_mask(92))

    os.makedirs(OUTPUT, exist_ok=True)
    silent = os.path.join(WORK, "chat", slug, "video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                           "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)

    scroll = None
    for fi in range(total):
        t = fi / FPS
        vis = [it for it in items if it.t0 <= t and (it.t1 is None or t < it.t1)]
        rows, prev = [], None
        for it in vis:
            im = typing_bubble(t) if getattr(it, "typing", False) else it.image(t)
            gap = GAP_SENDER if (it.from_ != prev or it.side == "center") else GAP
            rows.append((it, im, gap))
            prev = it.from_
        content = 30 + sum(g + (im.height + (34 if it.badge and t >= it.badge[0] else 0))
                           for it, im, g in rows) + 30
        view_h = VIEW_Y1 - VIEW_Y0
        target = max(0, content - view_h)
        scroll = target if scroll is None else scroll + (target - scroll) * 0.32

        frame = Image.new("RGBA", (W, H), WALL + (255,))
        chat = wall.copy()
        y = 30 - scroll
        for it, im, gap in rows:
            y += gap
            age = t - it.t0
            img = im
            if 0 <= age < 0.22 and it.t0 >= 0:
                k = ease_out_back(age / 0.22)
                sc = max(0.05, 0.55 + 0.45 * k)
                img = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
                a = img.getchannel("A").point(lambda v, m=min(1, age / 0.12): int(v * m))
                img.putalpha(a)
            dy = im.height - img.height
            if it.side == "center":
                x = (W - img.width) / 2
            elif it.side == "right":
                x = OUT_R - img.width
            else:
                x = IN_X - 16
                av = it.person.get("avatar_im") if it.person else None
                if av:
                    comp(chat, av, 20, y)
            comp(chat, img, x, y + dy)
            h = im.height
            if it.badge and t >= it.badge[0]:
                ba = t - it.badge[0]
                k = ease_out_back(min(1, ba / 0.25))
                bs = max(8, int(64 * (0.4 + 0.6 * k)))
                pill = Image.new("RGBA", (bs + 22, bs + 12), (0, 0, 0, 0))
                ImageDraw.Draw(pill).rounded_rectangle((0, 0, bs + 21, bs + 11), (bs + 12) // 2,
                                                       fill=(255, 255, 255), outline=(225, 225, 225), width=2)
                comp(pill, emoji(it.badge[1], bs), 11, 6)
                bx = (x + 30) if it.side == "right" else (x + 40)
                comp(chat, pill, bx, y + h - 22 - (pill.height - 68) / 2)
                h += 34
            y += h
        comp(frame, chat, 0, VIEW_Y0)
        draw_chrome(frame, t, s, statuses, composes, gav)
        for ev, who, body in banners:
            draw_banner(frame, t, ev, who, body)
        ff.stdin.write(frame.convert("RGB").tobytes())
        if fi % 60 == 0:
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
    wav = os.path.join(WORK, "chat", slug, "audio.f32")
    mix.astype(np.float32).tofile(wav)
    out = os.path.join(OUTPUT, s.get("output", slug + ".mp4"))
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", silent,
                    "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", out], check=True)
    print(f"  -> {out}")
    return out


def draw_banner(frame, t, ev, who, body):
    """iOS-style notification that drops over the header, for the reaction punchline."""
    age, dur = t - ev["t"], ev.get("banner_dur", 2.4)
    if not 0 <= age <= dur:
        return
    k = ease_out_back(min(1, age / 0.3)) if age < dur - 0.25 else (dur - age) / 0.25
    bw, bh = W - 48, 168
    card = Image.new("RGBA", (bw, bh + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 8, bw - 1, bh + 8), 40, fill=(0, 0, 0, 40))
    d.rounded_rectangle((0, 0, bw - 1, bh), 40, fill=(250, 250, 250))
    av = who.get("avatar_im")
    if av:
        comp(card, av.resize((96, 96), Image.LANCZOS), 30, (bh - 96) // 2)
    d.text((148, 28), who["name"], font=font(36, "Semibold"), fill=INK)
    d.text((bw - 100, 30), "now", font=font(30), fill=META)
    bf = font(36)
    draw_rich(card, 148, 80, wrap(body, bf, bw - 190)[:1], bf, INK, 46)
    comp(frame, card, 24, -bh - 20 + (bh + 50) * k)


def draw_chrome(frame, t, s, statuses, composes, gav):
    d = ImageDraw.Draw(frame)
    d.rectangle((0, 0, W, STATUS_H + HEADER_H), fill=HEADER_BG)
    d.text((48, 12), s.get("clock", "9:41"), font=font(34, "Semibold"), fill=(255, 255, 255))
    bx = W - 110
    d.rounded_rectangle((bx, 22, bx + 54, 46), 7, outline=(255, 255, 255), width=3)
    d.rounded_rectangle((bx + 5, 27, bx + 40, 41), 3, fill=(255, 255, 255))
    d.rectangle((bx + 57, 30, bx + 61, 38), fill=(255, 255, 255))
    for i in range(4):
        hh = 8 + i * 5
        d.rounded_rectangle((W - 200 + i * 12, 44 - hh, W - 193 + i * 12, 44), 2, fill=(255, 255, 255))
    hy = STATUS_H
    d.line([(46, hy + 52), (28, hy + 75), (46, hy + 98)], fill=(255, 255, 255), width=6, joint="curve")
    comp(frame, gav, 66, hy + 29)
    tf = font(42, "Semibold")
    lines = wrap(s["group"]["name"], tf, 600)
    draw_rich(frame, 180, hy + 26, lines, tf, (255, 255, 255), 50)
    sub = s["group"]["members"]
    for st in statuses:
        if st["t"] <= t < st["until"]:
            sub = st["text"]
    d.text((180, hy + 82), sub, font=font(30), fill=(220, 240, 235))
    vx = W - 190
    d.rounded_rectangle((vx, hy + 58, vx + 46, hy + 92), 8, outline=(255, 255, 255), width=4)
    d.polygon([(vx + 50, hy + 75), (vx + 66, hy + 62), (vx + 66, hy + 88)], fill=(255, 255, 255))
    for i in range(3):
        d.ellipse((W - 56, hy + 56 + i * 14, W - 47, hy + 65 + i * 14), fill=(255, 255, 255))

    y0 = VIEW_Y1 + 20
    d.rectangle((0, VIEW_Y1, W, H), fill=WALL)
    d.rounded_rectangle((20, y0, W - 150, y0 + 100), 50, fill=(255, 255, 255))
    typed = ""
    for c in composes:
        if c["t"] <= t < c["until"]:
            n = len(c["text"])
            typed = c["text"][: max(1, int(n * (t - c["t"]) / (c["until"] - c["t"])) + 1)]
        elif c["until"] <= t < c["until"] + 0.06:
            typed = c["text"]
    d.ellipse((44, y0 + 30, 84, y0 + 70), outline=META, width=3)
    d.arc((54, y0 + 40, 74, y0 + 62), 20, 160, fill=META, width=3)
    if typed:
        f = font(44)
        lines = wrap(typed, f, 2000)
        draw_rich(frame, 106, y0 + 22, lines[:1], f, INK, 56)
        if int(t * 2.5) % 2 == 0:
            cx = 106 + line_w(lines[0]) + 4
            d.line([(cx, y0 + 24), (cx, y0 + 76)], fill=GREEN, width=3)
    else:
        d.text((106, y0 + 25), "Message", font=font(44), fill=META)
        cx = W - 230
        d.rounded_rectangle((cx, y0 + 34, cx + 44, y0 + 70), 8, outline=META, width=3)
        d.ellipse((cx + 13, y0 + 43, cx + 31, y0 + 61), outline=META, width=3)
    d.ellipse((W - 126, y0, W - 26, y0 + 100), fill=GREEN)
    mx, my = W - 76, y0 + 50
    if typed:
        d.polygon([(mx - 18, my - 22), (mx + 24, my), (mx - 18, my + 22), (mx - 10, my)], fill=(255, 255, 255))
    else:
        d.rounded_rectangle((mx - 10, my - 26, mx + 10, my + 8), 10, fill=(255, 255, 255))
        d.arc((mx - 20, my - 12, mx + 20, my + 18), 0, 180, fill=(255, 255, 255), width=4)
        d.line([(mx, my + 18), (mx, my + 28)], fill=(255, 255, 255), width=4)
    d.rounded_rectangle((W / 2 - 140, H - 18, W / 2 + 140, H - 8), 5, fill=(30, 30, 30))


def used_clips(s):
    """Every catalog clip the reel shows or plays, for the clip_usage diversity table."""
    ids = {e["clip"] for e in s["events"] if e.get("clip")}
    ids |= {e["sound"]["clip"] for e in s["events"] if e.get("sound")}
    ids |= {e["card_cat"] for e in s["events"] if e.get("card_cat")}
    ids |= {p["avatar"] for p in s["people"].values() if p.get("avatar")}
    return sorted(ids)


def register(path):
    """Queue the rendered reel in data/videos.db with the script's `youtube` metadata,
    so `python -m engine.upload <slug>` and the schedulers pick it up like any story."""
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
        sys.exit("usage: python3 engine/chat_render.py data/chats/<slug>.json [--register]")
    render(args[0])
    if "--register" in sys.argv:
        register(args[0])
