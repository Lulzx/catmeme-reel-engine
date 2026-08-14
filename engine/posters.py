"""Generate local 9:16 thumbnail candidates from rendered Shorts.

YouTube does not accept uploaded custom thumbnails for Shorts. These posters are
used by the local studio and can guide frame selection in YouTube's mobile upload
flow. A story may set ``thumbnail_clip``; current authored stories put that clip
on the final narrative beat, immediately before the 2.6-second outro.
"""
import json
import os
import subprocess
import sys

from engine.paths import OUTPUT, STORIES, WORK

POSTERS = os.path.join(WORK, "posters")


def duration(path):
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(proc.stdout.strip())


def poster_time(slug, video_path):
    story_path = os.path.join(STORIES, slug + ".json")
    if not os.path.exists(story_path):
        return 0.6
    story = json.load(open(story_path))
    if not story.get("thumbnail_clip"):
        return 0.6
    # Target the middle of the final story beat, before the standard 2.6s outro.
    return max(0.6, duration(video_path) - 4.1)


def generate(slug, video_path=None, output_path=None):
    video_path = video_path or os.path.join(OUTPUT, slug + ".mp4")
    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)
    os.makedirs(POSTERS, exist_ok=True)
    output_path = output_path or os.path.join(POSTERS, slug + ".mp4.jpg")
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss",
         f"{poster_time(slug, video_path):.2f}", "-i", video_path,
         "-vframes", "1", "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease",
         "-q:v", "2", output_path],
        check=True,
    )
    return output_path


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        slug = os.path.splitext(os.path.basename(arg))[0]
        print(generate(slug))
