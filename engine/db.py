"""SQLite tracking store for the YouTube pipeline.

Source of truth = data/videos.db (replaces youtube.json). Holds:
  videos      one row per reel: status, schedule, upload metadata, video_id
  clip_usage  which catalog clips each video used (for cross-video diversity)
  meta        channel info + upload defaults

youtube.md is regenerated from this DB by engine/upload.py --sync.
"""
import json, os, sqlite3
from engine.paths import DATA

DB_PATH = os.path.join(DATA, "videos.db")

VIDEO_COLS = ["slug", "sort_order", "pov", "title", "description", "tags",
              "file", "status", "posted", "publish_at", "video_id"]


def connect(path=None):
    con = sqlite3.connect(path or DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS videos (
        slug        TEXT PRIMARY KEY,
        sort_order  INTEGER,
        pov         TEXT,
        title       TEXT,
        description TEXT,
        tags        TEXT,                       -- JSON array
        file        TEXT,
        status      TEXT DEFAULT 'queued',      -- authored|queued|scheduled|posted
        posted      TEXT,
        publish_at  TEXT,
        video_id    TEXT
    );
    CREATE TABLE IF NOT EXISTS clip_usage (
        slug    TEXT,
        clip_id TEXT,
        PRIMARY KEY (slug, clip_id)
    );
    """)
    con.commit()


# ── meta ────────────────────────────────────────────────────────────────────
def meta_set(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)))
    con.commit()


def meta_get(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


# ── videos ──────────────────────────────────────────────────────────────────
def _row_to_video(r):
    d = {k: r[k] for k in VIDEO_COLS}
    d["tags"] = json.loads(d["tags"]) if d["tags"] else []
    return d


def upsert_video(con, v):
    tags = json.dumps(v.get("tags", []))
    con.execute("""
        INSERT INTO videos (slug,sort_order,pov,title,description,tags,file,status,posted,publish_at,video_id)
        VALUES (:slug,:sort_order,:pov,:title,:description,:tags,:file,:status,:posted,:publish_at,:video_id)
        ON CONFLICT(slug) DO UPDATE SET
            sort_order=excluded.sort_order, pov=excluded.pov, title=excluded.title,
            description=excluded.description, tags=excluded.tags, file=excluded.file,
            status=excluded.status, posted=excluded.posted,
            publish_at=excluded.publish_at, video_id=excluded.video_id
    """, {
        "slug": v["slug"], "sort_order": v.get("sort_order", 0), "pov": v.get("pov"),
        "title": v.get("title"), "description": v.get("description"), "tags": tags,
        "file": v.get("file"), "status": v.get("status", "queued"),
        "posted": v.get("posted"), "publish_at": v.get("publish_at"),
        "video_id": v.get("video_id"),
    })
    con.commit()


def set_fields(con, slug, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    con.execute(f"UPDATE videos SET {cols} WHERE slug=?", (*fields.values(), slug))
    con.commit()


def get_video(con, slug):
    r = con.execute("SELECT * FROM videos WHERE slug=?", (slug,)).fetchone()
    return _row_to_video(r) if r else None


def list_videos(con):
    rows = con.execute("SELECT * FROM videos ORDER BY sort_order, slug").fetchall()
    return [_row_to_video(r) for r in rows]


def next_to_post(con):
    r = con.execute(
        "SELECT slug FROM videos WHERE status NOT IN ('posted','scheduled') "
        "ORDER BY sort_order, slug LIMIT 1").fetchone()
    return r["slug"] if r else None


def max_sort_order(con):
    r = con.execute("SELECT MAX(sort_order) AS m FROM videos").fetchone()
    return r["m"] or 0


# ── clip usage (diversity) ──────────────────────────────────────────────────
def record_clips(con, slug, clip_ids):
    con.executemany("INSERT OR IGNORE INTO clip_usage(slug,clip_id) VALUES(?,?)",
                    [(slug, c) for c in clip_ids])
    con.commit()


def all_used_clips(con):
    return [r["clip_id"] for r in con.execute("SELECT clip_id FROM clip_usage").fetchall()]


# ── two-way sync between two videos.db files (local <-> deployed server) ─────
# Status lifecycle, least-to-most advanced. A reel only ever moves forward, so on
# a conflict the further-along side wins for the upload/scheduling fields.
STATUS_RANK = {"authored": 0, "queued": 1, "scheduled": 2, "posted": 3}


def _clip_usage_rows(con):
    return [(r["slug"], r["clip_id"])
            for r in con.execute("SELECT slug, clip_id FROM clip_usage").fetchall()]


def _meta_rows(con):
    return {r["key"]: r["value"]
            for r in con.execute("SELECT key, value FROM meta").fetchall()}


def merge(local_path, remote_path):
    """Reconcile two videos.db files and write the merged result back to BOTH, so
    an authoring machine and the deployed server converge without either side
    clobbering the other. Used by deploy.py to sync the SQLite store.

    Per video (keyed by slug):
      • content   (pov, title, description, tags, file, sort_order) comes from
        LOCAL — the authoring source of truth; remote-only rows keep their own.
      • lifecycle (status, posted, publish_at, video_id) comes from whichever side
        is further along by STATUS_RANK, because uploads and scheduling happen on
        the server. Ties keep the side that already has a video_id.
      • clip_usage is unioned; meta (channel/defaults) is filled in from either
        side, local winning on a genuine conflict.

    Rows are only ever added or advanced, never deleted. Returns a summary dict."""
    lcon = connect(local_path); init(lcon)
    rcon = connect(remote_path); init(rcon)
    lv = {v["slug"]: v for v in list_videos(lcon)}
    rv = {v["slug"]: v for v in list_videos(rcon)}

    merged = {}
    for slug in set(lv) | set(rv):
        l, r = lv.get(slug), rv.get(slug)
        if not r:                      # local-only -> ship to server as-is
            merged[slug] = l; continue
        if not l:                      # server-only -> pull back to local as-is
            merged[slug] = r; continue
        row = dict(l)                  # local content wins
        lr, rr = STATUS_RANK.get(l["status"], 0), STATUS_RANK.get(r["status"], 0)
        adv = r if (rr > lr or (rr == lr and r.get("video_id"))) else l
        for k in ("status", "posted", "publish_at", "video_id"):
            row[k] = adv.get(k)
        row["tags"] = l.get("tags") or r.get("tags") or []
        merged[slug] = row

    for con in (lcon, rcon):           # write merged videos to both
        for v in merged.values():
            upsert_video(con, v)
    usage = sorted(set(_clip_usage_rows(lcon)) | set(_clip_usage_rows(rcon)))
    metas = {**_meta_rows(rcon), **_meta_rows(lcon)}   # local meta wins
    for con in (lcon, rcon):
        con.executemany("INSERT OR IGNORE INTO clip_usage(slug,clip_id) VALUES(?,?)", usage)
        for k, val in metas.items():
            con.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, val))
        con.commit()

    summary = {"total": len(merged),
               "to_remote": sorted(s for s in lv if s not in rv),
               "to_local":  sorted(s for s in rv if s not in lv)}
    lcon.close(); rcon.close()
    return summary


# ── git-friendly JSON export (videos.db stays local; this is what's tracked) ─
def export_json(con, path):
    """Write a versionable JSON snapshot of the catalog of videos. The SQLite DB
    is the working store (local, gitignored); this JSON is committed so the
    posting state is visible/portable on GitHub."""
    data = {
        "channel": meta_get(con, "channel", {}),
        "defaults": meta_get(con, "defaults", {}),
        "videos": list_videos(con),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ── one-time migration from youtube.json ────────────────────────────────────
def migrate_from_json(con, json_path):
    data = json.load(open(json_path))
    ch = data.get("channel", {})
    meta_set(con, "channel", ch)
    meta_set(con, "defaults", data.get("defaults", {}))
    for i, slug in enumerate(data["order"]):
        v = dict(data["videos"][slug]); v["slug"] = slug; v["sort_order"] = i
        upsert_video(con, v)
    return len(data["order"])
