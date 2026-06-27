#!/usr/bin/env python3
"""Web backend for the cat-meme reel engine.

Wraps the existing engine (catalog / matcher / renderer) in a small REST + SSE
API and serves the built HeroUI frontend (web/dist) so the whole studio runs
from one process:

    python3 engine/server.py            # -> http://localhost:8000

Endpoints
  GET  /api/catalog                 every described clip (+ frame / clip urls)
  GET  /api/scenes                  bundled background scene library
  GET  /api/stories                 story summaries
  GET  /api/stories/{slug}          full story + the clip each beat resolves to
  PUT  /api/stories/{slug}          save edited story json
  GET  /api/outputs                 rendered reels (+ duration / size / poster)
  GET  /api/match                   live matcher: want=a,b&query=..&limit=n
  GET  /api/render/{slug}/stream    run a render, stream ffmpeg logs over SSE

Static media is served under /media/{frames,clips,output,scenes,posters}.
"""
import os, sys, json, subprocess, time

ENGINE = os.path.dirname(os.path.abspath(__file__))
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import paths, match as M
from paths import (CLIPS, BACKGROUNDS, STORIES, OUTPUT, FRAMES, WORK, CATALOG)

paths.ensure()
POSTERS = os.path.join(WORK, "posters")
os.makedirs(POSTERS, exist_ok=True)
WEB_DIST = os.path.join(os.path.dirname(ENGINE), "web", "dist")

app = FastAPI(title="Cat Reel Studio")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

# --- catalog (loaded once, refreshed if the file changes) --------------------
_catalog_cache = {"mtime": 0, "data": []}
def catalog():
    try:
        mt = os.path.getmtime(CATALOG)
    except OSError:
        return []
    if mt != _catalog_cache["mtime"]:
        _catalog_cache["data"] = M.load_catalog()
        _catalog_cache["mtime"] = mt
    return _catalog_cache["data"]

def clip_view(c):
    """A catalog clip enriched with media URLs for the frontend."""
    return {**c,
            "frame": f"/media/frames/{c['id']}.jpg",
            "clip":  f"/media/clips/{c['file']}"}

@app.get("/api/health")
def health():
    return {"ok": True, "clips": len(catalog())}

@app.get("/api/catalog")
def api_catalog():
    return [clip_view(c) for c in catalog()]

@app.get("/api/scenes")
def api_scenes():
    out = []
    if os.path.isdir(BACKGROUNDS):
        for fn in sorted(os.listdir(BACKGROUNDS)):
            if fn.lower().endswith((".jpg", ".jpeg", ".png")):
                out.append({"name": os.path.splitext(fn)[0],
                            "url": f"/media/scenes/{fn}"})
    return out

# --- stories -----------------------------------------------------------------
def _story_path(slug):
    p = os.path.join(STORIES, slug + ".json")
    if not os.path.exists(p):
        raise HTTPException(404, f"no story '{slug}'")
    return p

def story_summary(slug, data):
    return {"slug": slug,
            "title": data.get("title", slug),
            "pov": data.get("pov", ""),
            "output": data.get("output", "final.mp4"),
            "beats": len(data.get("beats", [])),
            "outro": data.get("outro", "")}

@app.get("/api/stories")
def api_stories():
    out = []
    for fn in sorted(os.listdir(STORIES)):
        if fn.endswith(".json"):
            slug = fn[:-5]
            try:
                with open(os.path.join(STORIES, fn)) as f:
                    out.append(story_summary(slug, json.load(f)))
            except Exception:
                continue
    return out

@app.get("/api/stories/{slug}")
def api_story(slug: str):
    with open(_story_path(slug)) as f:
        data = json.load(f)
    cat = catalog()
    by_id = {c["id"]: c for c in cat}
    used = []
    # mirror the renderer's resolution (no-repeat exclude) so the preview is honest
    for beat in data.get("beats", []):
        for c in beat.get("cast", []):
            clip = None
            if c.get("clip"):
                clip = by_id.get(c["clip"])
            else:
                _, clip, matched = M.best(c.get("want", []), c.get("query", ""),
                                          cat, exclude=used)
                if clip is None:
                    _, clip, matched = M.best(c.get("want", []), c.get("query", ""), cat)
                c["matched"] = matched
            if clip:
                used.append(clip["id"])
                c["resolved"] = {"id": clip["id"], "primary": clip["primary"],
                                 "quality": clip["quality"],
                                 "frame": f"/media/frames/{clip['id']}.jpg"}
    return {"slug": slug, "raw": data}

@app.put("/api/stories/{slug}")
async def api_save_story(slug: str, request: Request):
    body = await request.body()
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"invalid JSON: {e}")
    if not isinstance(data, dict) or "beats" not in data:
        raise HTTPException(400, "story must be an object with a 'beats' list")
    path = os.path.join(STORIES, slug + ".json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"ok": True, "slug": slug}

# --- outputs (rendered reels) ------------------------------------------------
def _ffprobe_dur(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=nk=1:nw=1", path],
            capture_output=True, text=True, timeout=20)
        return round(float(r.stdout.strip() or 0), 1)
    except Exception:
        return 0.0

def _poster(name, video_path):
    """Generate (once) a poster jpg for a rendered reel."""
    poster = os.path.join(POSTERS, name + ".jpg")
    if not os.path.exists(poster) or os.path.getmtime(poster) < os.path.getmtime(video_path):
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", "0.6",
            "-i", video_path, "-vframes", "1", "-vf", "scale=540:-1", poster],
            check=False, timeout=30)
    return f"/media/posters/{name}.jpg" if os.path.exists(poster) else None

@app.get("/api/outputs")
def api_outputs():
    out = []
    if os.path.isdir(OUTPUT):
        for fn in sorted(os.listdir(OUTPUT)):
            if not fn.lower().endswith((".mp4", ".mov", ".webm")):
                continue
            p = os.path.join(OUTPUT, fn)
            st = os.stat(p)
            out.append({"name": fn, "url": f"/media/output/{fn}",
                        "size": st.st_size, "mtime": st.st_mtime,
                        "duration": _ffprobe_dur(p),
                        "poster": _poster(fn, p)})
    out.sort(key=lambda o: o["mtime"], reverse=True)
    return out

# --- matcher playground ------------------------------------------------------
@app.get("/api/match")
def api_match(want: str = "", query: str = "", limit: int = 12):
    wants = [w.strip() for w in want.split(",") if w.strip()]
    ranked = M.match(wants, query, catalog())
    results = []
    for sc, c, matched in ranked[:limit]:
        results.append({"score": round(sc, 2), "matched": matched,
                        "id": c["id"], "primary": c["primary"],
                        "quality": c["quality"], "emotions": c["emotions"],
                        "duration": c["duration"], "orientation": c["orientation"],
                        "frame": f"/media/frames/{c['id']}.jpg",
                        "clip": f"/media/clips/{c['file']}"})
    return results

# --- render (streamed logs over SSE) -----------------------------------------
@app.get("/api/render/{slug}/stream")
def api_render(slug: str):
    path = _story_path(slug)
    with open(path) as f:
        out_name = json.load(f).get("output", "final.mp4")

    def sse(obj):
        return f"data: {json.dumps(obj)}\n\n"

    def gen():
        yield sse({"line": f"$ render {slug}", "kind": "cmd"})
        # -u / PYTHONUNBUFFERED so the renderer's per-beat prints stream live
        # instead of block-buffering until the process exits.
        proc = subprocess.Popen([sys.executable, "-u", os.path.join(ENGINE, "render.py"), path],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1,
                                env={**os.environ, "PYTHONUNBUFFERED": "1"})
        for line in proc.stdout:
            yield sse({"line": line.rstrip("\n")})
        proc.wait()
        ok = proc.returncode == 0
        yield sse({"done": True, "code": proc.returncode, "ok": ok,
                   "output": out_name if ok else None,
                   "url": f"/media/output/{out_name}?t={int(time.time())}" if ok else None})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})

# --- static media ------------------------------------------------------------
for route, folder in (("/media/frames", FRAMES), ("/media/clips", CLIPS),
                      ("/media/output", OUTPUT), ("/media/scenes", BACKGROUNDS),
                      ("/media/posters", POSTERS)):
    os.makedirs(folder, exist_ok=True)
    app.mount(route, StaticFiles(directory=folder), name=route)

# --- built frontend (mounted last so /api wins) ------------------------------
if os.path.isdir(WEB_DIST):
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
else:
    @app.get("/")
    def _no_build():
        return JSONResponse({"error": "frontend not built",
                             "hint": "cd web && npm run build"}, status_code=503)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    print(f"Cat Reel Studio  ->  http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
