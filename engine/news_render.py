#!/usr/bin/env python3
"""Prime-time debate reels: a household crime covered like national breaking news.
A screaming anchor, a split-screen panel that grows from 1 to 6 cats, an all-caps
headline, a quote box, a scrolling ticker, crosstalk, and an EXCLUSIVE night-vision
CCTV reveal with an ENHANCE zoom.

    python3 engine/news_render.py data/news/<slug>.json              ->  output/<slug>.mp4
    python3 engine/news_render.py data/news/<slug>.json --register   ... + queue it in videos.db

Frames are drawn by fframes (engine/ff_debate, Rust + SVG on the GPU via Skia/Metal).
This script only prepares what it reads, under work/news/<slug>/media/:

  track_<who>.mp4   per panelist: frame i is exactly what that tile shows at reel
                    frame i (speaking segment, crosstalk, or a quiet ping-pong loop),
                    still on green; fframes keys it with an SkSL shader
  bg_<who>.jpg      the tile background, pre-blurred
  cctv.mp4          the night-vision footage, ENHANCE zoom included
  audio.wav         the mix: clip audio + synthesised sting/beeps/news bed
  timeline.json     the resolved script for the Rust side

See docs/21-prime-time-debate.md and data/news/*.json.
"""
import json, os, random, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import BACKGROUNDS, CLIPS, OUTPUT, ROOT, WORK
import cutouts as C
from chat_render import FPS, SR, clip, decode, tone
import voice as VO

FF_PROJECT = os.path.join(ROOT, "engine", "ff_debate")
FF_BIN = os.path.join(FF_PROJECT, "target", "release", "ff_debate")
TRACK_H = 720                       # source height the tiles sample from
CCTV_W, CCTV_H = 1080, 1036         # the tile area, which the CCTV fills


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", *args], check=True)


# ── audio ─────────────────────────────────────────────────────────────────────
def noise_sweep(dur, vol, rising=True):
    n = int(dur * SR)
    rng = np.random.default_rng(3)
    x = rng.standard_normal(n).astype(np.float32)
    env = np.linspace(0, 1, n) if rising else np.linspace(1, 0, n)
    y = np.zeros(n, dtype=np.float32)
    a = 0.0
    for i in range(0, n, 256):   # one-pole lowpass whose cutoff follows the envelope
        c = 0.02 + 0.5 * env[i]
        seg = x[i:i + 256]
        out = np.empty_like(seg)
        for j, v in enumerate(seg):
            a += c * (v - a); out[j] = a
        y[i:i + 256] = out
    y *= env * vol
    return np.repeat(y[:, None], 2, axis=1)


def boom(vol=0.7):
    a = tone(70, 38, 0.9, vol, 5)
    hit = tone(160, 60, 0.12, vol * 0.6, 25)
    a[:len(hit)] += hit
    return a


def news_bed(dur):
    """Low pulse every half second + an offbeat tick, the 'debate is live' bed."""
    n = int(dur * SR)
    bed = np.zeros((n, 2), dtype=np.float32)
    pulse, tick = tone(55, 50, 0.35, 0.10, 9), tone(2400, 2400, 0.03, 0.025, 120)
    for i in range(int(dur / 0.5)):
        s = int(i * 0.5 * SR)
        e = min(n, s + len(pulse)); bed[s:e] += pulse[:e - s]
        s2 = int((i * 0.5 + 0.25) * SR)
        e2 = min(n, s2 + len(tick))
        if s2 < n:
            bed[s2:e2] += tick[:e2 - s2]
    return bed


def mix_audio(s, panel, ev, end_t, out):
    of = lambda ty: [e for e in ev if e["type"] == ty]
    track, voice = [], []
    for e in of("voice"):
        voice.append((e["t"], decode(e["wav"], 0, e["dur"] + 0.1, fade_out=0.05) * 1.6))
    for e in of("sting"):
        track += [(e["t"] - 0.35, noise_sweep(0.4, 0.35)), (e["t"], boom())]
    for e in of("speak"):
        if e.get("silent"):
            continue
        c = panel[e["who"]]["clip"]
        track.append((e["t"], decode(os.path.join(CLIPS, c["file"]), e["start"], e["dur"],
                                     fade_out=0.25)))
    for e in of("chaos"):
        for k, p in panel.items():
            a = decode(os.path.join(CLIPS, p["clip"]["file"]), p["spec"].get("loud", 0.0),
                       e["until"] - e["t"])
            track.append((e["t"] + random.Random(k).random() * 0.2, a * 0.6))
    for e in of("cctv"):
        c = panel[e["who"]]["clip"]
        track.append((e["t"], decode(os.path.join(CLIPS, c["file"]), e["start"], e["dur"],
                                     fade_out=0.25) * 0.8))
        if e.get("enhance") is not None:
            for i in range(3):
                track.append((e["enhance"] + i * 0.15, tone(1500, 1500, 0.06, 0.18, 20)))
    for e in of("bars"):
        track.append((e["t"], tone(1000, 1000, e.get("beep", 1.6), 0.16, 0.01)))
    stings = of("sting")
    bed_end = min([e["t"] for e in of("bars")] + [end_t])
    track.append((stings[0]["until"] if stings else 0, news_bed(bed_end)))

    n = int(end_t * SR)

    def lay(items):
        buf = np.zeros((n, 2), dtype=np.float32)
        for t0, a in items:
            i0 = int(max(0, t0) * SR)
            if i0 >= n:
                continue
            seg = a[: n - i0]
            buf[i0:i0 + len(seg)] += seg
        return buf

    mix = lay(track)
    if voice:
        # duck the cats, stings and bed by 9 dB under the announcer, with short ramps
        env = np.ones(n, dtype=np.float32)
        ramp = int(0.15 * SR)
        for e in of("voice"):
            a, b = int((e["t"] - 0.15) * SR), int((e["t"] + e["dur"] + 0.25) * SR)
            env[max(0, a):min(n, b)] = np.minimum(env[max(0, a):min(n, b)], 0.35)
        kernel = np.ones(ramp, dtype=np.float32) / ramp
        env = np.convolve(env, kernel, mode="same")
        mix = mix * env[:, None] + lay(voice)
    mix = np.tanh(mix * 1.1) * 0.92
    raw = out + ".f32"
    mix.astype(np.float32).tofile(raw)
    ff("-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", raw, "-c:a", "pcm_s16le", out)
    os.remove(raw)


# ── per-panelist tracks ───────────────────────────────────────────────────────
def active(lst, t):
    return next((e for e in lst if e["t"] <= t < e["until"]), None)


def tile_sec(key, spec, t, speaks, chaos):
    """Which second of the panelist's clip their tile shows at reel time t."""
    sp = active(speaks, t)
    if sp and sp["who"] == key and not sp.get("silent") and t < sp["t"] + sp["dur"]:
        return sp["start"] + (t - sp["t"])
    ch = active(chaos, t)
    if ch:
        return spec.get("loud", 0.0) + (t - ch["t"])
    a, span = spec.get("idle", 0.0), spec.get("idle_span", 1.2)
    p = (t * 0.8) % (2 * span)            # ping-pong, so a listener keeps moving without a jump
    return a + (p if p < span else 2 * span - p)


def build_track(key, p, total, speaks, chaos, work, media):
    """Green-screen crop of the clip, re-sequenced so frame i is what the tile shows at frame i."""
    c, spec = p["clip"], p["spec"]
    src = os.path.join(work, "src", key)
    seq = os.path.join(work, "seq", key)
    for d in (src, seq):
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    ff("-t", str(min(c["duration"], 12)), "-i", os.path.join(CLIPS, c["file"]),
       "-vf", f"fps={FPS},{C._crop_expr(c, 0.06)},scale=-2:{TRACK_H}", os.path.join(src, "%04d.png"))
    frames = sorted(os.listdir(src))
    for i in range(total):
        k = int(tile_sec(key, spec, i / FPS, speaks, chaos) * FPS)
        os.symlink(os.path.join(src, frames[max(0, min(len(frames) - 1, k))]),
                   os.path.join(seq, f"{i:05d}.png"))
    # 4:4:4 so the GPU key sees full-resolution chroma on the cat's edges
    ff("-framerate", str(FPS), "-i", os.path.join(seq, "%05d.png"), "-c:v", "libx264",
       "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv444p",
       os.path.join(media, f"track_{key}.mp4"))
    w, h = (int(x) for x in subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0", os.path.join(media, f"track_{key}.mp4")],
        capture_output=True, text=True, check=True).stdout.strip().split(","))
    return w / h


def bake_cctv(e, p, media):
    """Night-vision footage: the clip keyed onto its room, ENHANCE zoom, grain and scanlines."""
    c = p["clip"]
    dur = e["until"] - e["t"]
    ch = int(CCTV_H * e.get("fit", 0.62)) // 2 * 2
    x0, y0, x1, y1 = c["bbox"]
    pad = 0.06
    cw = ch * (min(1, x1 + pad) - max(0, x0 - pad)) * c["width"] / (
        (min(1, y1 + pad) - max(0, y0 - pad)) * c["height"])
    cx = (CCTV_W - cw) / 2 + CCTV_W * 0.06
    cy = CCTV_H - ch - CCTV_H * 0.06
    fx, fy = cx + cw / 2, cy + ch * e.get("face_y", 0.3)
    te, z = e.get("enhance", e["until"]) - e["t"], e.get("zoom", 2.4)
    k = f"min(1,max(0,(it-{te})/0.45))"
    zoom = f"1+{z - 1}*(1-pow(1-{k},3))"
    graph = (
        f"[0:v]scale={CCTV_W}:{CCTV_H}:force_original_aspect_ratio=increase,"
        f"crop={CCTV_W}:{CCTV_H},format=rgba[bg];"
        f"[1:v]fps={FPS},{C._crop_expr(c, pad)},{C._key_chain(c)},scale=-2:{ch}[cat];"
        f"[bg][cat]overlay=x={cx:.0f}:y={cy:.0f}:eof_action=repeat:format=auto,"
        f"zoompan=z='{zoom}':x='max(0,min(iw-iw/zoom,{fx:.0f}-iw/zoom/2))'"
        f":y='max(0,min(ih-ih/zoom,{fy:.0f}-ih/zoom/2))':d=1:s={CCTV_W}x{CCTV_H}:fps={FPS},"
        f"hue=s=0,eq=contrast=1.35:brightness=0.04,noise=alls=22:allf=t,"
        f"colorchannelmixer=rr=0.42:gg=1:bb=0.5,"
        f"drawgrid=w=iw:h=4:t=1:c=black@0.8,vignette=angle=PI/3.2,format=yuv420p"
    )
    ff("-loop", "1", "-framerate", str(FPS), "-i", os.path.join(BACKGROUNDS, e.get("bg", "kitchen.jpg")),
       "-ss", str(e["start"]), "-t", str(e["dur"]), "-i", os.path.join(CLIPS, c["file"]),
       "-filter_complex", graph, "-t", f"{dur:.3f}", "-r", str(FPS),
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", os.path.join(media, "cctv.mp4"))


# ── the reel ──────────────────────────────────────────────────────────────────
def prepare(path):
    s = json.load(open(path))
    slug = os.path.splitext(os.path.basename(path))[0]
    work = os.path.join(WORK, "news", slug)
    media = os.path.join(work, "media")
    shutil.rmtree(media, ignore_errors=True); os.makedirs(media)
    panel = {k: {"spec": v, "clip": clip(v["clip"])} for k, v in s["panel"].items()}
    ev = sorted(s["events"], key=lambda e: e["t"])
    end_t = next(e["t"] for e in ev if e["type"] == "end")
    total = int(end_t * FPS)
    of = lambda ty: [e for e in ev if e["type"] == ty]
    speaks, chaos = of("speak"), of("chaos")
    vo = s.get("voice", {})
    for e in of("voice"):
        e["wav"], e["dur"] = VO.speak(e["text"], vo["id"], vo.get("model", VO.DEFAULT_MODEL),
                                      e.get("speed", vo.get("speed", 1.0)))
        nxt = next((x for x in speaks + chaos if x["t"] > e["t"] and not x.get("silent")), None)
        end = e["t"] + e["dur"]
        print(f"  voice {e['t']:5.1f}-{end:5.1f}  {e['text']}"
              + (f"   !! runs into {nxt.get('who', 'crosstalk')} at {nxt['t']}" if nxt and end > nxt["t"] else ""))
    for e in speaks:
        e.setdefault("until", e["t"] + e.get("dur", 2.0))
        if e.get("silent"):
            e["dur"] = 0
            continue
        # the cat keeps talking for as long as it holds the spotlight, not just for
        # its first burst; `dur` is only a floor for lines with no `until`
        room = panel[e["who"]]["clip"]["duration"] - e["start"]
        e["dur"] = max(0.3, min(max(e.get("dur", 0), e["until"] - e["t"]), room))

    jobs, others = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for k, p in panel.items():
            jobs.append((k, pool.submit(build_track, k, p, total, speaks, chaos, work, media)))
            bg = p["spec"].get("bg", "home.jpg")
            if bg != "studio":
                others.append(pool.submit(ff, "-i", os.path.join(BACKGROUNDS, bg), "-vf",
                                          "scale=1080:-2,gblur=sigma=5", "-q:v", "3",
                                          os.path.join(media, f"bg_{k}.jpg")))
        for e in of("cctv"):
            others.append(pool.submit(bake_cctv, e, panel[e["who"]], media))
        others.append(pool.submit(mix_audio, s, panel, ev, end_t, os.path.join(media, "audio.wav")))
    for f in others:
        f.result()                        # surface any ffmpeg failure
    aspects = {k: f.result() for k, f in jobs}

    def rgb(hexstr):
        v = int(hexstr, 16)
        return [(v >> 16) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255]

    name = lambda e: e.get("name") or s["panel"][e["who"]]["name"]
    timeline = {
        "duration": end_t, "clock": s.get("clock", "9:00 PM"), "market": s.get("market", ""),
        "panel": {k: {"name": p["spec"]["name"], "role": p["spec"].get("role", ""),
                      "studio": p["spec"].get("bg") == "studio", "fit": p["spec"].get("fit", 0.88),
                      "aspect": aspects[k], "key": rgb(p["clip"]["key_color"])}
                  for k, p in panel.items()},
        "stings": [{"t": e["t"], "until": e["until"], "text": e.get("text", "BREAKING NEWS"),
                    "exclusive": e.get("style") == "exclusive"} for e in of("sting")],
        "layouts": [{"t": e["t"], "tiles": e["tiles"]} for e in of("layout")],
        "headlines": [{"t": e["t"], "text": e["text"]} for e in of("headline")],
        "tickers": [{"t": e["t"], "text": e["text"]} for e in of("ticker")],
        "quotes": [{"t": e["t"], "name": name(e), "text": e["quote"]}
                   for e in sorted(speaks + chaos + of("cctv"), key=lambda e: e["t"]) if e.get("quote")],
        "speaks": [{"t": e["t"], "until": e["until"], "who": e["who"]} for e in speaks],
        "chaos": [{"t": e["t"], "until": e["until"]} for e in chaos],
        "cctv": [{"t": e["t"], "until": e["until"], "enhance": e.get("enhance"),
                  "label": e.get("label", "CAM 02  KITCHEN"), "clock": e.get("clock", "02:14:07"),
                  "date": e.get("date", "27-10-2026")} for e in of("cctv")],
        "bars": [{"t": e["t"], "who": e["who"]} for e in of("bars")],
    }
    with open(os.path.join(media, "timeline.json"), "w") as f:
        json.dump(timeline, f, indent=1, ensure_ascii=False)
    return s, slug, media


def render(path):
    s, slug, media = prepare(path)
    subprocess.run(["cargo", "build", "--release", "-q"], cwd=FF_PROJECT, check=True)
    os.makedirs(OUTPUT, exist_ok=True)
    out = os.path.join(OUTPUT, s.get("output", slug + ".mp4"))
    subprocess.run([FF_BIN, "render", "-o", out], check=True, env={**os.environ, "FF_WORK": media})
    print(f"  -> {out}")
    return out


def register(path):
    """Queue the rendered reel in data/videos.db (same contract as chat_render.register)."""
    sys.path.insert(0, ROOT)
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
    DB.record_clips(con, slug, sorted({p["clip"] for p in s["panel"].values()}))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("usage: python3 engine/news_render.py data/news/<slug>.json [--register] [--prep-only]")
    if "--prep-only" in sys.argv:
        print(prepare(args[0])[2])
    else:
        render(args[0])
    if "--register" in sys.argv:
        register(args[0])
