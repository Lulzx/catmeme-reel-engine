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
  GET  /api/sagas                   long-form saga summaries
  GET  /api/sagas/{slug}            full saga json
  PUT  /api/sagas/{slug}            save edited saga json
  GET  /api/sagas/{slug}/build-render/stream  build+render a saga locally (SSE)
  GET  /api/outputs                 rendered reels (+ duration / size / poster)
  GET  /api/match                   live matcher: want=a,b&query=..&limit=n
  GET  /api/render/{slug}/stream    run a render, stream ffmpeg logs over SSE

Static media is served under /media/{frames,clips,output,scenes,posters}.
"""
import os, sys, json, re, subprocess, time, datetime

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
for _p in (ENGINE, REPO):           # ENGINE for top-level imports, REPO for `engine.*`
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import paths, match as M
from paths import (CLIPS, BACKGROUNDS, STORIES, SAGAS, OUTPUT, FRAMES, WORK, CATALOG, DATA)
from engine import db as DB, upload as UP

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

# --- sagas (long-form narrated stories) --------------------------------------
def _saga_path(slug):
    p = os.path.join(SAGAS, slug + ".json")
    if not os.path.exists(p):
        raise HTTPException(404, f"no saga '{slug}'")
    return p

def saga_summary(slug, data):
    scenes = data.get("scenes", [])
    return {"slug": slug,
            "title": data.get("title", slug),
            "output": data.get("output", f"{slug}.mp4"),
            "scenes": len(scenes),
            "narrator": (data.get("voice") or {}).get("narrator", "")}

@app.get("/api/sagas")
def api_sagas():
    out = []
    if os.path.isdir(SAGAS):
        for fn in sorted(os.listdir(SAGAS)):
            if fn.endswith(".json"):
                slug = fn[:-5]
                try:
                    with open(os.path.join(SAGAS, fn)) as f:
                        out.append(saga_summary(slug, json.load(f)))
                except Exception:
                    continue
    return out

@app.get("/api/sagas/{slug}")
def api_saga(slug: str):
    with open(_saga_path(slug)) as f:
        data = json.load(f)
    return {"slug": slug, "raw": data}

@app.put("/api/sagas/{slug}")
async def api_save_saga(slug: str, request: Request):
    body = await request.body()
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"invalid JSON: {e}")
    if not isinstance(data, dict) or "scenes" not in data:
        raise HTTPException(400, "saga must be an object with a 'scenes' list")
    os.makedirs(SAGAS, exist_ok=True)
    with open(os.path.join(SAGAS, slug + ".json"), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"ok": True, "slug": slug}

@app.get("/api/sagas/{slug}/build-render/stream")
def api_saga_render(slug: str):
    """Build the saga's manifest, render it locally with Remotion, and register
    it in the DB as a queued long-form video — streamed as SSE log lines. This is
    the slow path (TTS + whisper + headless-Chrome render): minutes, not seconds."""
    _saga_path(slug)                      # 404 early if the saga doesn't exist
    out_name = f"{slug}.mp4"

    def sse(obj):
        return f"data: {json.dumps(obj)}\n\n"

    def gen():
        yield sse({"line": f"$ saga build + render {slug}", "kind": "cmd"})
        proc = subprocess.Popen([sys.executable, "-u",
                                 os.path.join(ENGINE, "saga_render.py"), slug],
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

# --- posting schedule (content calendar) -------------------------------------
@app.get("/api/schedule")
def api_schedule():
    """The posting log/schedule (from the git-tracked videos.json snapshot),
    enriched with poster + local-render + YouTube URLs for the calendar UI."""
    p = os.path.join(DATA, "videos.json")
    if not os.path.exists(p):
        return {"channel": {}, "defaults": {}, "videos": []}
    with open(p) as f:
        data = json.load(f)
    for v in data.get("videos", []):
        name = os.path.basename(v.get("file") or "")
        vp = os.path.join(OUTPUT, name) if name else ""
        has = bool(name) and os.path.exists(vp)
        v["output_url"] = f"/media/output/{name}" if has else None
        v["poster"] = _poster(name, vp) if has else None
        v["youtube_url"] = f"https://youtu.be/{v['video_id']}" if v.get("video_id") else None
        v["place"] = _dominant_place(v["slug"])
    return data

def _dominant_place(slug):
    """Most-used background scene across a story's beats (drives lane filtering)."""
    p = os.path.join(STORIES, slug + ".json")
    if not os.path.exists(p):
        return None
    try:
        beats = json.load(open(p)).get("beats", [])
    except Exception:
        return None
    counts = {}
    for b in beats:
        pl = (b.get("bg") or {}).get("place")
        if pl:
            counts[pl] = counts.get(pl, 0) + 1
    return max(counts, key=counts.get) if counts else None

@app.post("/api/schedule/{slug}/reschedule")
async def api_reschedule(slug: str, request: Request):
    """Move a scheduled reel to a new publish time (drag-to-reschedule).
    Updates publishAt on YouTube + the DB, regenerates videos.json, git-syncs."""
    body = await request.json()
    pub = (body or {}).get("publish_at")
    if not pub:
        raise HTTPException(400, "publish_at (RFC3339) required")
    con = DB.connect(); DB.init(con)
    v = DB.get_video(con, slug)
    if not v:
        raise HTTPException(404, f"no video '{slug}'")
    if v["status"] != "scheduled" or not v["video_id"]:
        raise HTTPException(400, "only scheduled (not-yet-public) reels can be rescheduled")
    try:
        yt = UP.get_service()
        yt.videos().update(part="status", body={"id": v["video_id"], "status": {
            "privacyStatus": "private", "publishAt": pub, "selfDeclaredMadeForKids": False,
        }}).execute()
    except Exception as e:
        raise HTTPException(502, f"YouTube update failed: {e}")
    DB.set_fields(con, slug, publish_at=pub)
    UP.render_md(con)                          # rewrites youtube.md + data/videos.json
    UP.git_sync(f"chore: reschedule {slug} -> {pub}")
    return {"ok": True, "slug": slug, "publish_at": pub}

# --- live analytics (views/likes) --------------------------------------------
@app.get("/api/analytics")
def api_analytics():
    """Per-video viewCount/likeCount for everything we've uploaded. Needs the
    youtube.readonly scope — returns {error:'reauth'} if the token lacks it."""
    con = DB.connect(); DB.init(con)
    ids = [v["video_id"] for v in DB.list_videos(con) if v.get("video_id")]
    if not ids:
        return {"stats": {}}
    try:
        yt = UP.get_service()
        stats = {}
        for i in range(0, len(ids), 50):
            resp = yt.videos().list(part="statistics,status",
                                    id=",".join(ids[i:i + 50])).execute()
            for it in resp.get("items", []):
                s = it.get("statistics", {})
                stats[it["id"]] = {
                    "views": int(s.get("viewCount", 0)),
                    "likes": int(s.get("likeCount", 0)),
                    "comments": int(s.get("commentCount", 0)),
                    "privacy": it.get("status", {}).get("privacyStatus"),
                }
        return {"stats": stats}
    except Exception as e:
        msg = str(e)
        if "insufficient" in msg.lower() or "scope" in msg.lower() or "403" in msg:
            return {"error": "reauth",
                    "detail": "needs youtube.readonly — run: python3 -m engine.upload --auth"}
        return {"error": "failed", "detail": msg}

# --- generate batch: scaffold drafts, render + schedule (streamed) -----------
import author as AUTHOR

@app.post("/api/draft")
async def api_draft(request: Request):
    """Scaffold a draft story from a POV premise; returns its slug."""
    body = await request.json()
    pov = (body or {}).get("pov", "").strip()
    scene = (body or {}).get("scene", "home")
    if not pov:
        raise HTTPException(400, "pov required")
    return {"slug": AUTHOR.write_draft(pov, scene)}

def _register_story(con, slug):
    """Upsert a rendered story into the DB as queued, synthesising metadata."""
    s = json.load(open(os.path.join(STORIES, slug + ".json")))
    pov = s.get("pov", "")
    if DB.get_video(con, slug):
        DB.set_fields(con, slug, file=f"output/{slug}.mp4", status="queued")
        return
    bare = re.sub(r"(?i)^pov:\s*", "", pov).strip()
    DB.upsert_video(con, {
        "slug": slug, "sort_order": DB.max_sort_order(con) + 1, "pov": pov,
        "title": f"{pov} 🐱 #shorts",
        "description": f"{bare}\n\nNew cat POVs every few days 🐾\n#shorts #catmemes #pov #relatable #funnycats #fyp",
        "tags": ["cat memes", "pov", "relatable", "funny cats", "shorts"],
        "file": f"output/{slug}.mp4", "status": "queued",
        "posted": None, "publish_at": None, "video_id": None,
    })

def _schedule_pending(con, every_h=6):
    base = UP._latest_publish(con)
    now = datetime.datetime.now(datetime.timezone.utc)
    start = (base + datetime.timedelta(hours=every_h)) if base else (now + datetime.timedelta(hours=every_h))
    if start < now:
        start = now + datetime.timedelta(hours=every_h)
    slugs = [v["slug"] for v in DB.list_videos(con)
             if v["status"] not in ("posted", "scheduled") and v.get("file")]
    for i, slug in enumerate(slugs):
        t = start + datetime.timedelta(hours=every_h * i)
        url = UP.upload(con, slug, publish_at=t.strftime("%Y-%m-%dT%H:%M:%SZ"))
        yield slug, url

@app.get("/api/batch/stream")
def api_batch():
    """Render every pending story (cursed-clip-safe, diversity-seeded) then
    schedule them onto the publish grid — streamed as SSE log lines."""
    def sse(o): return f"data: {json.dumps(o)}\n\n"

    def gen():
        con = DB.connect(); DB.init(con)
        done = {v["slug"] for v in DB.list_videos(con) if v["status"] in ("posted", "scheduled")}
        pending = [fn[:-5] for fn in sorted(os.listdir(STORIES))
                   if fn.endswith(".json") and fn[:-5] not in done]
        if not pending:
            yield sse({"line": "Nothing pending — every story is already scheduled.", "kind": "cmd"})
            yield sse({"done": True, "ok": True, "rendered": []}); return
        yield sse({"line": f"$ batch: {len(pending)} pending — {', '.join(pending)}", "kind": "cmd"})
        seed = DB.all_used_clips(con)
        rendered = []
        for slug in pending:
            yield sse({"line": f"── rendering {slug} ──", "kind": "cmd"})
            proc = subprocess.Popen([sys.executable, "-u", os.path.join(ENGINE, "render.py"),
                                     os.path.join(STORIES, slug + ".json")],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    bufsize=1, env={**os.environ, "PYTHONUNBUFFERED": "1",
                                                    "RENDER_SEED": json.dumps(seed)})
            clips = []
            for line in proc.stdout:
                line = line.rstrip("\n")
                yield sse({"line": line})
                m = re.search(r"\[([0-9]{3}(?:,[0-9]{3})*)\]", line)
                if m:
                    clips += m.group(1).split(",")
            proc.wait()
            if proc.returncode == 0:
                seed += clips
                DB.record_clips(con, slug, clips)
                _register_story(con, slug)
                rendered.append(slug)
                yield sse({"line": f"✓ {slug} rendered", "kind": "ok"})
            else:
                yield sse({"line": f"✗ {slug} failed to render", "kind": "err"})
        if rendered:
            yield sse({"line": "── uploading + scheduling ──", "kind": "cmd"})
            try:
                for slug, url in _schedule_pending(con):
                    yield sse({"line": f"🕒 {slug} → {url}"})
            except Exception as e:
                yield sse({"line": f"schedule error: {e}", "kind": "err"})
            UP.render_md(con); UP.git_sync("chore: batch generate + schedule")
        yield sse({"done": True, "ok": True, "rendered": rendered})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

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
