# 13. Deployment & SQLite sync

The web UI ([`web/`](../web), see [`web/README.md`](../web/README.md)) is deployed at
**https://cats.lulzx.space**. This doc covers how a local change reaches that server in
one command, and — the tricky part — how the **SQLite tracking store** stays in sync
when both the laptop and the server can write to it.

## One command: `deploy.py`

From the repo root:

```bash
python3 deploy.py                 # full deploy (build → push → sync → restart)
python3 deploy.py --no-web        # data-only: skip the web build + dist upload
python3 deploy.py --db-only       # only reconcile the SQLite store
python3 deploy.py --no-code       # skip git push/pull (deploy uncommitted dist/db)
python3 deploy.py --dry-run       # print the plan, change nothing
```

It runs as an animated checklist (a lime braille spinner per step that resolves to
`✓`/`✗` with the elapsed time; it degrades to plain lines when stdout isn't a TTY, e.g.
in CI):

```
  ▮ Cat Reel Studio deploy → lulz:/opt/cats

  ✓  preflight             — lulz:/opt/cats        0.4s
  ✓  build web             — web/dist built        4.1s
  ✓  push code → server    — Already up to date.   1.2s
  ✓  sync web/dist         — dist synced           0.6s
  ✓  sync sqlite (merge)   — 29 rows, +1→server    1.5s
  ✓  sync media            — 29 reels              3.0s
  ✓  restart + health      — service active, health 200   2.4s

  ● deployed in 45.9s · https://cats.lulzx.space
```

### Steps, in order

| # | step | what it does |
|---|------|--------------|
| 1 | **preflight** | confirm `ssh`/`scp`/`rsync` exist locally and the server + `$CRS_REMOTE` are reachable |
| 2 | **build web** | `npm run build` **locally** — the server's Node 18 is too old for Vite 8 |
| 3 | **push code** | `git push` then `git pull --ff-only` on the server (Python/engine changes) |
| 4 | **sync web/dist** | `rsync --delete web/dist/ → server` (the built SPA the backend serves) |
| 5 | **sync sqlite** | pull the server DB, **merge** with local, push the merged DB back (see below) |
| 6 | **sync media** | `rsync` `output/*.mp4` + `work/posters/` → server so reels play on the dashboard |
| 7 | **restart** | `systemctl restart` the service, then health-check `/api/health` |

Any step failing aborts the deploy and prints the captured command output.

### Configuration (env vars, with defaults)

```
CRS_HOST=lulz            # ssh alias / host
CRS_REMOTE=/opt/cats     # app dir on the server
CRS_SERVICE=cats.service # systemd unit
CRS_PORT=8765            # local port the backend binds on the server
```

Nothing secret lives in the repo — the host is an `ssh` alias (configured in
`~/.ssh/config`) and the dashboard's basic-auth password is held only on the server
(Caddy) and in the operator's notes, never committed.

## The server (what `deploy.py` targets)

```
laptop ──ssh/rsync──▶  VPS (ssh alias `lulz`)
                       ├─ /opt/cats                 shallow git clone of this repo
                       │   ├─ .venv                 fastapi · uvicorn · pillow · google-*
                       │   ├─ web/dist              built SPA (rsynced; never built here)
                       │   ├─ output/*.mp4          rendered reels (rsynced)
                       │   ├─ work/posters/*.jpg    poster thumbnails
                       │   └─ data/videos.db        the SQLite store (merged, not clobbered)
                       ├─ systemd: cats.service     → .venv/bin/python engine/server.py
                       │   env PORT=8765, CRS_NO_GIT=1, bound 127.0.0.1:8765
                       └─ Caddy (cats.lulzx.space)  TLS + basic_auth + reverse_proxy :8765
                                                    (+ SSE flush for the render/batch streams)
```

- **`CRS_NO_GIT=1`** stops the server's pipeline from making its own git commits (the
  laptop owns git; the server is a runtime mirror).
- The server can **schedule + draft + view analytics** but **cannot render** — the large
  `clips/` library isn't rsynced. Render locally, then deploy the `output/*.mp4`.

## SQLite sync — the hard part

`data/videos.db` is the source of truth for the posting pipeline (one row per reel:
status, schedule, upload metadata, `video_id`). It is **git-ignored** — the committed
`data/videos.json` + `youtube.md` are human/diff-friendly snapshots, not the store.

The problem: **both ends write to it.**

- The **laptop** authors reels and registers them (new rows, content edits).
- The **server** is where reels actually upload + schedule on the live YouTube channel,
  so it sets `status`, `publish_at`, `video_id` on existing rows.

Copying the file in either direction would clobber one side's work. So `deploy.py` does a
**row-level two-way merge** (`db.merge(local_path, remote_path)` in
[`engine/db.py`](../engine/db.py)) instead of a file copy:

```
1. cp  server:data/videos.db          → server:…/videos.db.bak   (backup)
   cp  local  data/videos.db          → data/videos.db.bak       (backup)
2. scp server:data/videos.db          → .deploy/remote.videos.db (pull)
3. db.merge("data/videos.db", ".deploy/remote.videos.db")        (reconcile, writes BOTH)
4. scp merged → server:data/videos.db.new ; ssh mv … videos.db   (atomic push)
5. restart cats.service                                          (reopens the DB)
```

### Merge policy (per reel, keyed by `slug`)

| field group | fields | winner |
|-------------|--------|--------|
| **content** | `pov`, `title`, `description`, `tags`, `file`, `sort_order` | **local** (the authoring source of truth) |
| **lifecycle** | `status`, `posted`, `publish_at`, `video_id` | the **further-along** side by `STATUS_RANK` (`authored < queued < scheduled < posted`); ties keep the side that already has a `video_id` |
| **clip_usage** | which catalog clips each reel used | **union** of both |
| **meta** | channel info, upload defaults | filled from either side, local wins a true conflict |

- Rows present on only one side are **added** to the other.
- Rows are only ever **added or advanced — never deleted** (deletion is always manual).
- Both `.db` files end up identical, so the next deploy is a no-op convergence.

After a deploy, regenerate the committed snapshots if the local DB gained rows:

```bash
python3 -m engine.upload --sync     # rewrites youtube.md + data/videos.json from the DB
git add youtube.md data/videos.json && git commit -m "chore: update posting snapshot"
```

## Registering a rendered reel into the DB

A reel rendered outside the web "Generate batch" flow (e.g. via the `make-reel` skill)
exists only as `data/stories/<slug>.json` + `output/<slug>.mp4` — it isn't in the DB yet.
Register it as `queued` (rendered, not yet on the publish grid), mirroring the server's
`_register_story`:

```python
import json, os, re, sys; sys.path.insert(0, "engine")
import db as DB, match as M, upload as UP
from paths import STORIES

con = DB.connect(); DB.init(con); cat = M.load_catalog()
slug = "husband-curfew-6pm"
s = json.load(open(os.path.join(STORIES, slug + ".json")))
pov = s.get("pov", "")

used = []                                    # record clip usage (cross-video diversity)
for b in s["beats"]:
    for c in b.get("cast", []):
        _, clip, _ = M.best(c.get("want", []), c.get("query", ""), cat, exclude=used)
        used.append(clip["id"])
DB.record_clips(con, slug, used)

bare = re.sub(r"(?i)^pov:\s*", "", pov).strip()
DB.upsert_video(con, {
    "slug": slug, "sort_order": DB.max_sort_order(con) + 1, "pov": pov,
    "title": f"{pov} 🐱 #shorts",
    "description": f"{bare}\n\nNew cat POVs every few days 🐾\n#shorts #catmemes #pov",
    "tags": ["cat memes", "pov", "relatable", "funny cats", "shorts"],
    "file": f"output/{slug}.mp4", "status": "queued",
    "posted": None, "publish_at": None, "video_id": None,
})
UP.render_md(con)                            # refresh youtube.md + data/videos.json
```

Then `python3 deploy.py --db-only` (plus a media sync) pushes it to the dashboard. To
actually **schedule** it onto the live channel, use the UI's "Generate → Render &
schedule" or `python3 -m engine.upload --schedule-queue` (see
[12-youtube-upload.md](12-youtube-upload.md)) — that uploads to the real YouTube channel.

## Troubleshooting

| symptom | fix |
|---------|-----|
| `preflight` fails | check `ssh lulz` works and `$CRS_REMOTE` exists; `ssh-add` your key |
| `build web` fails | run `npm --prefix web install`, then `npm --prefix web run build` to see the real error |
| reels don't appear on the dashboard | confirm `sync media` ran and `--db-only` wasn't set; the row needs `file` + an `output/<slug>.mp4` on the server |
| a reel's state looks stale after deploy | the server may be the further-along side — the merge keeps its `scheduled`/`posted` lifecycle by design |
| need to roll back the DB | both ends keep `data/videos.db.bak` from the last deploy |
| restart shows non-`active` | `ssh lulz journalctl -u cats.service -n 50` |
