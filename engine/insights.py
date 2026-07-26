"""Pull live per-video stats and viewer comments straight from the Data API.

    python3 -m engine.insights            # stats table, ranked by views/day
    python3 -m engine.insights --comments # every comment thread, newest first
    python3 -m engine.insights --json     # machine-readable dump

Uses the same OAuth token as engine/upload.py (needs the youtube.readonly scope).
Writes a snapshot to work/insights.json so analysis doesn't re-burn quota.
"""
import datetime
import json
import os
import sys

from engine.paths import ROOT
from engine import db
from engine.upload import get_service

SNAPSHOT = os.path.join(ROOT, "work", "insights.json")


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse(ts):
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fetch_stats(yt, ids):
    """statistics + status for every id, batched 50 at a time (1 quota unit each)."""
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        resp = yt.videos().list(part="statistics,status,snippet",
                                id=",".join(chunk)).execute()
        for item in resp.get("items", []):
            s = item.get("statistics", {})
            out[item["id"]] = {
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
                "privacy": item.get("status", {}).get("privacyStatus"),
                "published": item.get("snippet", {}).get("publishedAt"),
                "title": item.get("snippet", {}).get("title"),
            }
    return out


def fetch_comments(yt, video_id, limit=100):
    """Top-level comments + replies for one video. Returns [] for disabled/absent."""
    threads = []
    try:
        resp = yt.commentThreads().list(part="snippet,replies", videoId=video_id,
                                        maxResults=min(limit, 100),
                                        order="time", textFormat="plainText").execute()
    except Exception as exc:                      # comments off, or video not live yet
        if "commentsDisabled" in str(exc) or "videoNotFound" in str(exc):
            return []
        raise
    for t in resp.get("items", []):
        top = t["snippet"]["topLevelComment"]["snippet"]
        threads.append({
            "author": top.get("authorDisplayName"),
            "text": top.get("textDisplay", "").strip(),
            "likes": top.get("likeCount", 0),
            "at": top.get("publishedAt"),
            "replies": [r["snippet"].get("textDisplay", "").strip()
                        for r in t.get("replies", {}).get("comments", [])],
        })
    return threads


def collect(with_comments=True):
    con = db.connect()
    rows = [dict(r) for r in con.execute(
        "select slug, pov, title, status, publish_at, posted, video_id "
        "from videos where video_id is not null and video_id != ''")]
    yt = get_service()
    stats = fetch_stats(yt, [r["video_id"] for r in rows])

    now = _now()
    videos = []
    for r in rows:
        st = stats.get(r["video_id"])
        if not st:
            continue
        pub = st.get("published") or r.get("publish_at")
        live_days = 0.0
        if pub:
            live_days = max((now - _parse(pub)).total_seconds() / 86400, 0.0)
        rec = {**r, **st, "live_days": round(live_days, 2)}
        # a video scheduled for the future isn't live yet — don't rank it
        rec["is_live"] = st["privacy"] == "public" and live_days > 0.05
        rec["views_per_day"] = round(st["views"] / live_days, 1) if live_days > 0.5 else None
        rec["like_rate"] = round(100 * st["likes"] / st["views"], 2) if st["views"] else 0.0
        videos.append(rec)

    if with_comments:
        for v in videos:
            v["comment_threads"] = fetch_comments(yt, v["video_id"]) if v["comments"] else []

    snap = {"pulled_at": now.isoformat(), "videos": videos}
    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    with open(SNAPSHOT, "w") as fh:
        json.dump(snap, fh, indent=2)
    return snap


def main():
    args = sys.argv[1:]
    snap = collect(with_comments="--no-comments" not in args)
    videos = snap["videos"]
    live = [v for v in videos if v["is_live"]]

    if "--json" in args:
        print(json.dumps(snap, indent=2))
        return

    if "--comments" in args:
        for v in sorted(live, key=lambda v: -v["comments"]):
            if not v.get("comment_threads"):
                continue
            print(f"\n=== {v['slug']}  ({v['views']} views, {v['comments']} comments)")
            for c in v["comment_threads"]:
                print(f"  [{c['likes']:>3}♥] {c['author']}: {c['text']}")
                for rep in c["replies"]:
                    print(f"        ↳ {rep}")
        return

    total_v = sum(v["views"] for v in live)
    total_c = sum(v["comments"] for v in live)
    print(f"{len(live)} live · {total_v:,} views · {total_c} comments "
          f"· {total_v // max(len(live), 1):,} avg/reel\n")
    ranked = sorted((v for v in live if v["views_per_day"] is not None),
                    key=lambda v: -v["views_per_day"])
    print(f"{'slug':<34}{'views':>8}{'v/day':>8}{'like%':>7}{'cmts':>6}{'days':>6}")
    for v in ranked:
        print(f"{v['slug']:<34}{v['views']:>8}{v['views_per_day']:>8}"
              f"{v['like_rate']:>7}{v['comments']:>6}{v['live_days']:>6.1f}")


if __name__ == "__main__":
    main()
