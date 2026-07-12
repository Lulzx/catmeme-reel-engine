"""Author a wojak-style cat story as simple JSON; this builds the Remotion
manifest. Semantic in -> deterministic out: resolves clips (match.py), synthesizes
narration (KittenTTS), times captions (whisper.cpp), computes grounded geometry +
mood grading. Remotion just renders the manifest.

  python3 engine/saga_build.py data/sagas/<slug>.json
  -> work/manifests/<slug>.json   (render with remotion/scripts/render-local.mjs)
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # engine/
import paths  # noqa: E402
import match as M  # noqa: E402
import geometry as G  # noqa: E402
import cutouts as C  # noqa: E402
import tts as TTS  # noqa: E402
import captions as CAP  # noqa: E402

MANIFESTS = os.path.join(paths.WORK, "manifests")


def resolve_bg(bgspec, mood):
    grade = G.mood(mood)["bg"]
    bgspec = bgspec or {}
    img = bgspec.get("img") or bgspec.get("place")
    if img and os.path.exists(os.path.join(paths.BACKGROUNDS, f"{img}.jpg")):
        return {"kind": "themed", "src": f"bg/{img}.jpg", "grade": grade}
    return {"kind": "flat", "color": grade["tint"], "color2": "#0c0d12", "grade": grade}


def resolve_char(spec, mood, catalog, used, W, H, default_size=0.82, default_pos=0.5):
    if spec.get("clip"):
        clip = next(x for x in catalog if x["id"] == spec["clip"])
    else:
        _, clip, _ = M.best(spec.get("want", []), spec.get("query", ""), catalog,
                            exclude=list(used))
    if clip is None:
        raise SystemExit(f"no clip matches {spec.get('want') or spec.get('query')!r}")
    used.append(clip["id"])
    size = spec.get("size", default_size)
    pos = spec.get("pos", default_pos)
    baseline = spec.get("baseline", 1.06)
    char = {
        "id": clip["id"],
        "rect": G.sprite_box(clip, W, H, size=size, pos=pos, baseline=baseline),
        "flip": spec.get("flip", False),
        "enter": spec.get("enter", "pop"),
        "filter": G.mood(mood)["char"]["filter"],
    }
    if spec.get("name"):
        char["label"] = spec["name"]
    animated = spec["animated"] if "animated" in spec else C.should_animate(clip)
    if animated:
        info = C.extract_sequence(clip, start=spec.get("clip_start", 0.0),
                                  dur=spec.get("clip_dur"), fps=18)
        char.update({"kind": "animated", "src": f"seq/{clip['id']}",
                     "seqCount": info["count"], "seqFps": info["fps"]})
    else:
        C.extract_sprite(clip, t=spec.get("clip_t"))
        char.update({"kind": "sprite", "src": f"sprites/{clip['id']}.png"})
    return char


def build(story_path):
    story = json.load(open(story_path))
    slug = story["slug"]
    cv = story.get("canvas", {})
    W, H, FPS = cv.get("w", 1920), cv.get("h", 1080), cv.get("fps", 30)
    vcfg = story.get("voice", {})
    provider = vcfg.get("provider", "piper")
    narrator = vcfg.get("narrator", TTS.DEFAULT_VOICE)
    pace = story.get("pace", {})
    tail_default, tempo = pace.get("tail", 0.4), pace.get("tempo", 1.0)
    catalog = M.load_catalog()
    used = []

    # 1) narration (one wav per scene with vo)
    wavs, durs, scripts = {}, {}, {}
    for sc in story["scenes"]:
        vo = sc.get("vo", "")
        if not vo:
            continue
        wav = os.path.join(paths.WORK, "audio", slug, f"{sc['id']}.wav")
        durs[sc["id"]] = TTS.synth(vo, wav, voice=sc.get("voice", narrator),
                                   provider=provider, tempo=tempo)
        wavs[sc["id"]] = wav
        scripts[sc["id"]] = vo
        print(f"  tts {sc['id']}: {durs[sc['id']]:.2f}s")

    # 2) caption timings (whisper for the clock; the script supplies the words)
    print("  transcribing…")
    toks = CAP.tokens_for(wavs, scripts)

    # 3) assemble scenes
    scenes = []
    for sc in story["scenes"]:
        sid = sc["id"]
        mood = sc.get("mood", "neutral")
        dur = durs.get(sid, 2.0) + sc.get("tail", tail_default)
        out = {"id": sid, "durationInFrames": round(dur * FPS),
               "tokens": toks.get(sid, []), "transition": sc.get("transition", "fade")}
        if sc.get("vo"):
            out["audio"] = f"audio/{slug}/{sid}.wav"
        if sc.get("caption"):
            out["caption"] = sc["caption"]

        if sc.get("kind") == "transformation":
            out["kind"] = "transformation"
            out["background"] = {"kind": "flat", "color": "#000000"}
            out["characters"] = []
            panels = []
            for pi, p in enumerate(sc["panels"]):
                pm = p.get("mood", mood)
                cast = dict(p.get("cast", {}))
                cast.setdefault("pos", 0.27 if pi == 0 else 0.73)
                cast.setdefault("size", 0.74)
                panels.append({
                    "label": p.get("label"),
                    "background": resolve_bg(p.get("bg"), pm),
                    "character": resolve_char(cast, pm, catalog, used, W, H),
                })
            out["panels"] = panels
        else:
            out["kind"] = "scene"
            out["background"] = resolve_bg(sc.get("bg"), mood)
            cast = sc.get("cast", [])
            if isinstance(cast, dict):
                cast = [cast]
            n = len(cast)
            defpos = G.DEFAULT_POS.get(n, [(j + 0.5) / n for j in range(n)])
            chars = []
            for j, cspec in enumerate(cast):
                cspec = dict(cspec)
                cspec.setdefault("pos", defpos[j])
                cspec.setdefault("size", 0.82 if n == 1 else 0.62)
                chars.append(resolve_char(cspec, mood, catalog, used, W, H))
            out["characters"] = chars
        scenes.append(out)

    manifest = {"id": slug, "fps": FPS, "width": W, "height": H,
                "assetsBase": "", "scenes": scenes}
    if story.get("music"):
        manifest["music"] = story["music"]
    os.makedirs(MANIFESTS, exist_ok=True)
    outp = os.path.join(MANIFESTS, f"{slug}.json")
    json.dump(manifest, open(outp, "w"), indent=2)
    total = sum(s["durationInFrames"] for s in scenes)
    print(f"wrote {outp}  ({len(scenes)} scenes, {total} frames, {total/FPS:.1f}s)")
    return outp


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 engine/saga_build.py data/sagas/<slug>.json")
    build(sys.argv[1])
