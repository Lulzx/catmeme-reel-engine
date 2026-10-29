#!/usr/bin/env python3
"""Where the YouTube Shorts player covers a 1080x1920 frame, measured from a phone
screenshot of a live reel (2026-10-29). Keep text, faces and anything the joke
needs inside the safe area; the covered strips can hold only background.

  top     y < TOP              back / search / menu buttons
  rail    x > RAIL_X, y > RAIL_Y   like, comment, save, share, remix, sound
  bottom  y > BOTTOM           "remix this scene", channel name, caption, comment bar
  sides   x < SIDE or x > W - SIDE   cropped off on tall phones (video is zoomed to fill)

    python3 engine/safe_zone.py output/<slug>.mp4 out.png 3 15 30   # frames with the zones tinted red
"""
import io, subprocess, sys
from PIL import Image, ImageDraw

W, H = 1080, 1920
TOP, BOTTOM, SIDE = 150, 1420, 60
RAIL_X, RAIL_Y = 900, 1000


def safe_box(y0, y1):
    """Usable x range for content spanning rows y0..y1."""
    return SIDE, (RAIL_X if y1 > RAIL_Y else W - SIDE)


def overlay(im):
    """Tint the covered areas red, for checking a frame by eye."""
    im = im.convert("RGBA")
    s = im.width / W
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    red = (255, 0, 0, 90)
    for box in [(0, 0, W, TOP), (0, BOTTOM, W, H), (RAIL_X, RAIL_Y, W, BOTTOM),
                (0, TOP, SIDE, BOTTOM), (W - SIDE, TOP, W, RAIL_Y)]:
        d.rectangle([v * s for v in box], fill=red)
    edge = (255, 0, 0, 255)                     # solid boundary, so the tint can't blend into a pink UI
    d.line([(SIDE * s, TOP * s), ((W - SIDE) * s, TOP * s)], fill=edge, width=2)
    d.line([(SIDE * s, BOTTOM * s), (RAIL_X * s, BOTTOM * s)], fill=edge, width=2)
    d.line([(RAIL_X * s, RAIL_Y * s), (RAIL_X * s, BOTTOM * s)], fill=edge, width=2)
    d.line([(SIDE * s, TOP * s), (SIDE * s, BOTTOM * s)], fill=edge, width=2)
    d.line([((W - SIDE) * s, TOP * s), ((W - SIDE) * s, RAIL_Y * s), (RAIL_X * s, RAIL_Y * s)], fill=edge, width=2)
    return Image.alpha_composite(im, lay).convert("RGB")


def grab(path, out, times, width=360):
    ims = []
    for t in times:
        b = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t), "-i", path,
                            "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True, check=True).stdout
        im = Image.open(io.BytesIO(b)); im.thumbnail((width, width * 2))
        ims.append(overlay(im))
    sheet = Image.new("RGB", (sum(i.width + 8 for i in ims), ims[0].height), (255, 0, 255))
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0)); x += im.width + 8
    sheet.save(out)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit("usage: python3 engine/safe_zone.py <video.mp4> <out.png> t1 [t2 ...]")
    grab(sys.argv[1], sys.argv[2], [float(t) for t in sys.argv[3:]])
