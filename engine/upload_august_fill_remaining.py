"""Resume the August-fill uploads after YouTube's daily account cap resets.

Safe to rerun: existing video IDs are skipped and publish times are derived from
the tracked batch order, so a retry cannot shift the six-hour grid.
"""
import datetime
from pathlib import Path

from engine import db
from engine import upload as up
from engine.paths import ROOT

BATCH = Path(ROOT) / "data" / "august-fill-2026-08-14.txt"
START = datetime.datetime(2026, 8, 17, 20, 37, 27,
                          tzinfo=datetime.timezone.utc)


def main():
    slugs = BATCH.read_text().split()
    con = db.connect()
    db.init(con)
    done = 0
    try:
        for index, slug in enumerate(slugs):
            video = db.get_video(con, slug)
            if not video:
                raise RuntimeError(f"Batch story is not registered: {slug}")
            if video.get("video_id"):
                continue
            publish_at = (
                START + datetime.timedelta(hours=6 * index)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                url = up.upload(con, slug, publish_at=publish_at)
                done += 1
                print(f"SCHEDULED {slug} {publish_at} {url}", flush=True)
            except Exception as exc:
                reason = up._daily_limit_reason(exc)
                if reason:
                    print(f"STOP: {reason}; resume after the account resets.")
                    break
                raise
    finally:
        up.render_md(con)
        con.close()
    print(f"Scheduled {done} additional video(s).")


if __name__ == "__main__":
    main()
