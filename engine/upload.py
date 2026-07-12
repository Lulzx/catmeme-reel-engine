"""Upload rendered reels to YouTube; tracking lives in data/videos.db (SQLite).

Reads upload metadata from the DB (engine/db.py), pushes the mp4 via the YouTube
Data API v3, then writes status/video_id/publish time back and regenerates the
human-readable youtube.md.

Native scheduling: `--at` / `--schedule-queue` upload privately now with a
`publishAt`, and YouTube auto-publishes them public at that time.

One-time setup (Google Cloud OAuth) is in docs/12-youtube-upload.md. You need
client_secret.json (Desktop OAuth client) + token.json at the repo root (both
gitignored). token.json is created on first `--auth`.

Usage:
  python -m engine.upload --next                       upload next queued (public)
  python -m engine.upload <slug>                        upload a specific video
  python -m engine.upload <slug> --privacy unlisted     override privacy
  python -m engine.upload <slug> --at 2026-06-28T03:00:00Z   schedule one
  python -m engine.upload --schedule-queue --start-in 6 --every 6   schedule the queue
  python -m engine.upload --status                      print the posting table
  python -m engine.upload --sync                        regenerate youtube.md
  python -m engine.upload --auth                        run OAuth flow only
"""
import argparse
import datetime
import os
import sys

from engine.paths import ROOT
from engine import db

YT_MD         = os.path.join(ROOT, "youtube.md")
VIDEOS_JSON   = os.path.join(ROOT, "data", "videos.json")
CLIENT_SECRET = os.path.join(ROOT, "client_secret.json")
TOKEN         = os.path.join(ROOT, "token.json")
SCOPES        = ["https://www.googleapis.com/auth/youtube.upload",
                 "https://www.googleapis.com/auth/youtube.readonly"]

STATUS_ICON = {"posted": "✅", "scheduled": "🕒", "queued": "⏳", "authored": "📝"}
DONE = ("posted", "scheduled")   # already on YouTube — never re-uploaded by --next

TRACKED = ["data/videos.json", "youtube.md"]   # auto-committed on state change


def git_sync(message):
    """Commit + push the tracked JSON/md snapshot after the schedule changes.
    Best-effort: never breaks the upload flow if git is unavailable or offline.
    Set CRS_NO_GIT=1 (e.g. on a deployed mirror) to skip git entirely."""
    import subprocess
    if os.environ.get("CRS_NO_GIT"):
        return

    def g(*args, **kw):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, **kw)
    try:
        if not g("status", "--porcelain", "--", *TRACKED).stdout.strip():
            return                                  # nothing changed
        g("add", "--", *TRACKED)
        if g("commit", "-q", "-m", message, "--", *TRACKED).returncode != 0:
            return
        push = g("push", "-q", "origin", "HEAD")
        print("✓ videos.json committed + pushed" if push.returncode == 0
              else "✓ videos.json committed (push failed — push manually)")
    except Exception as e:
        print(f"(git auto-sync skipped: {e})")


# ── youtube.md (human view, regenerated from the DB) ────────────────────────
def render_md(con):
    ch = db.meta_get(con, "channel", {})
    vids = db.list_videos(con)
    nxt = db.next_to_post(con)
    lines = [
        f"# YouTube posting log — {ch.get('name','')}",
        "",
        f"**Channel:** {ch.get('url','')}",
        "**Format:** vertical cat-meme POV Shorts, rendered by this repo's pipeline.",
        "",
        "> Generated from `data/videos.db` by `engine/upload.py` — the DB is the source of truth.",
        "> Ask \"which video should I post next?\" and I'll read it and hand you the metadata.",
        "",
        "Status: ✅ posted · 🕒 scheduled (auto-publishes later) · ⏳ queued (rendered) · 📝 authored",
        "",
        "## Posting log",
        "",
        "| # | Slug | POV | Status | Posted / Publishes | File |",
        "|---|------|-----|--------|--------|------|",
    ]
    for i, v in enumerate(vids, 1):
        icon = STATUS_ICON.get(v["status"], v["status"])
        when = v.get("posted") or v.get("publish_at") or "—"
        lines.append(f"| {i} | {v['slug']} | {v['pov']} | {icon} {v['status']} | "
                     f"{when} | {v.get('file') or '—'} |")
    lines += [
        "",
        f"**Recommended next:** {nxt if nxt else '— all posted/scheduled —'}",
        "Upload it with `python -m engine.upload --next`.",
        "",
        "---",
        "",
        "## Upload metadata (paste-ready)",
        "",
    ]
    for v in vids:
        icon = STATUS_ICON.get(v["status"], "")
        lines += [
            f"### {v['slug']} {icon}",
            f"- **Title:** {v['title']}",
            "- **Description:**",
            "  ```",
            *["  " + ln for ln in (v["description"] or "").split("\n")],
            "  ```",
            f"- **Tags:** {', '.join(v['tags'])}",
            "",
        ]
    with open(YT_MD, "w") as f:
        f.write("\n".join(lines))
    db.export_json(con, VIDEOS_JSON)   # git-tracked JSON snapshot of the DB


# ── description helpers ──────────────────────────────────────────────────────
def _chapter_block(chapters):
    """Render saga chapters as a YouTube-parseable timestamp list. YouTube only
    shows a chapter UI when the first stamp is 0:00 and there are ≥3 ascending
    stamps — so we emit nothing (harmless) for shorter/sparse sagas."""
    if not chapters or len(chapters) < 3:
        return ""
    lines = []
    for c in chapters:
        sec = int(c.get("at", 0))
        lines.append(f"{sec // 60}:{sec % 60:02d} {c.get('title', '')}".rstrip())
    if not lines[0].startswith("0:00"):
        return ""
    return "\n\nChapters:\n" + "\n".join(lines)


def _build_description(v):
    """The upload description: the stored text plus auto chapter timestamps."""
    return (v.get("description") or "") + _chapter_block(v.get("chapters"))


# ── youtube api ─────────────────────────────────────────────────────────────
def get_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Missing Google API libraries. Install: pip install -r requirements.txt")

    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET):
                sys.exit(f"Missing {CLIENT_SECRET}. See docs/12-youtube-upload.md.")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(con, slug, privacy=None, publish_at=None):
    """Upload one video. If publish_at (RFC3339 UTC) is given, it goes up private
    and YouTube auto-publishes it public at that time."""
    from googleapiclient.http import MediaFileUpload

    v = db.get_video(con, slug)
    if not v:
        sys.exit(f"Unknown slug '{slug}'.")
    path = os.path.join(ROOT, v["file"]) if v.get("file") else None
    if not path or not os.path.exists(path):
        sys.exit(f"Video file not found for '{slug}': {v.get('file')!r}\n"
                 f"Render it first:  python engine/render.py data/stories/{slug}.json")

    d = db.meta_get(con, "defaults", {})
    status = {
        "privacyStatus": "private" if publish_at else (privacy or d.get("privacy", "public")),
        "selfDeclaredMadeForKids": d.get("made_for_kids", False),
    }
    if publish_at:
        status["publishAt"] = publish_at
    body = {
        "snippet": {"title": v["title"][:100], "description": _build_description(v),
                    "tags": v["tags"], "categoryId": d.get("categoryId", "15")},
        "status": status,
    }

    youtube = get_service()
    media = MediaFileUpload(path, chunksize=1024 * 1024 * 8, resumable=True,
                            mimetype="video/mp4")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    when = f"publishes {publish_at}" if publish_at else status["privacyStatus"]
    print(f"Uploading {slug} → {v['title']!r} ({when})")
    resp = None
    while resp is None:
        chunk, resp = req.next_chunk()
        if chunk:
            print(f"  {int(chunk.progress() * 100)}%")
    vid = resp["id"]
    url = f"https://youtu.be/{vid}"
    if publish_at:
        db.set_fields(con, slug, status="scheduled", publish_at=publish_at, video_id=vid)
        print(f"Done: {url} — goes public {publish_at}")
    else:
        db.set_fields(con, slug, status="posted",
                      posted=datetime.date.today().isoformat(), video_id=vid)
        print(f"Done: {url}")
    render_md(con)
    return url


def _latest_publish(con):
    """Latest publishAt already on the books, so a new batch continues the grid."""
    times = []
    for v in db.list_videos(con):
        if v.get("publish_at"):
            times.append(datetime.datetime.strptime(
                v["publish_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc))
    return max(times) if times else None


def fill_schedule(con, every_h, max_n=None):
    """Upload queued videos with publishAt continuing the every_h grid from the
    last scheduled video. Stops gracefully when the daily API quota runs out —
    the rest stay queued for the next run (e.g. a daily cron after quota reset)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    base = _latest_publish(con)
    start = (base + datetime.timedelta(hours=every_h)) if base else (now + datetime.timedelta(hours=every_h))
    if start < now:                       # past grid point -> next future slot
        start = now + datetime.timedelta(hours=every_h)
    slugs = [v["slug"] for v in db.list_videos(con)
             if v["status"] not in DONE and v.get("file")]
    if max_n:
        slugs = slugs[:max_n]
    if not slugs:
        print("Nothing queued to schedule.")
        return
    done = 0
    for i, slug in enumerate(slugs):
        t = start + datetime.timedelta(hours=every_h * i)
        try:
            upload(con, slug, publish_at=t.strftime("%Y-%m-%dT%H:%M:%SZ"))
            done += 1
        except Exception as e:
            if "quota" in str(e).lower():
                print(f"\nDaily upload quota reached after {done} video(s). "
                      f"{len(slugs)-done} stay queued for the next run.")
                return
            raise
    print(f"\nScheduled {done} video(s).")


def schedule_queue(con, every_h, start_in_h):
    """Upload every still-queued video now, each private with a publishAt staggered
    by every_h hours, first one start_in_h hours from now."""
    base = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=start_in_h)
    slugs = [v["slug"] for v in db.list_videos(con)
             if v["status"] not in DONE and v.get("file")]
    if not slugs:
        print("Nothing queued to schedule.")
        return
    for i, slug in enumerate(slugs):
        t = base + datetime.timedelta(hours=every_h * i)
        upload(con, slug, publish_at=t.strftime("%Y-%m-%dT%H:%M:%SZ"))


# ── cli ─────────────────────────────────────────────────────────────────────
def print_status(con):
    nxt = db.next_to_post(con)
    for i, v in enumerate(db.list_videos(con), 1):
        icon = STATUS_ICON.get(v["status"], v["status"])
        when = v.get("posted") or v.get("publish_at") or ""
        mark = "  ← next" if v["slug"] == nxt else ""
        print(f"{i}. {icon} {v['slug']:<28} {v['status']:<10} {when:<22}{mark}")


def main():
    p = argparse.ArgumentParser(description="Upload reels to YouTube.")
    p.add_argument("slug", nargs="?", help="video slug to upload")
    p.add_argument("--next", action="store_true", help="upload the next queued video")
    p.add_argument("--privacy", choices=["public", "unlisted", "private"],
                   help="override privacy for this upload")
    p.add_argument("--at", metavar="RFC3339",
                   help="schedule auto-publish at a time (uploads private now)")
    p.add_argument("--schedule-queue", action="store_true",
                   help="upload all queued videos now, auto-publishing on a stagger")
    p.add_argument("--fill-schedule", action="store_true",
                   help="schedule queued videos continuing the grid from the last "
                        "scheduled one; stops gracefully at the daily quota")
    p.add_argument("--max", type=int, default=None, metavar="N",
                   help="cap how many to schedule this run (with --fill-schedule)")
    p.add_argument("--every", type=float, default=6.0, metavar="HOURS",
                   help="hours between scheduled publishes")
    p.add_argument("--start-in", type=float, default=6.0, metavar="HOURS",
                   help="hours from now for the first scheduled publish")
    p.add_argument("--status", action="store_true", help="print posting table only")
    p.add_argument("--sync", action="store_true", help="regenerate youtube.md from the DB")
    p.add_argument("--auth", action="store_true", help="run OAuth flow only")
    a = p.parse_args()

    con = db.connect()
    db.init(con)

    if a.auth:
        get_service()
        print(f"Authorized. Token saved to {TOKEN}")
        return
    if a.sync:
        render_md(con)
        print(f"Regenerated {YT_MD}")
        return
    if a.status:
        print_status(con)
        return
    if a.schedule_queue:
        schedule_queue(con, every_h=a.every, start_in_h=a.start_in)
        git_sync("chore: update videos.json (schedule queue)")
        return
    if a.fill_schedule:
        fill_schedule(con, every_h=a.every, max_n=a.max)
        git_sync("chore: update videos.json (fill schedule)")
        return

    slug = a.slug or db.next_to_post(con)
    if not slug:
        print("Nothing queued — every video is posted or scheduled.")
        return
    if not db.get_video(con, slug):
        sys.exit(f"Unknown slug '{slug}'.")
    if db.get_video(con, slug)["status"] in DONE and not a.slug:
        print(f"'{slug}' is already {db.get_video(con, slug)['status']}.")
        return

    upload(con, slug, privacy=a.privacy, publish_at=a.at)
    git_sync(f"chore: update videos.json ({slug} {'scheduled' if a.at else 'posted'})")


if __name__ == "__main__":
    main()
