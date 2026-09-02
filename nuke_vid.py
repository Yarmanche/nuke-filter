#!/usr/bin/env python3
"""
Video/GIF/photo filter — grayscale + colored box logo via ffmpeg.

Positions: center (default), tl, tr, bl, br, ml, mr, mt, mb
Usage:
  python3 nuke_vid.py video.mp4 --pos center
  python3 nuke_vid.py clip.gif --pos br
  python3 nuke_vid.py video.mp4 --pos tl --width 0.4 --out out.mp4
  python3 nuke_vid.py video.mp4 --pos custom --fx 0.5 --fy 0.8

Quality (locked, do not tune down):
  mp4: libx264 crf 23, faststart, aac audio
  gif: two-pass palette with bayer dither; native fps preserved, max width 720
"""
import argparse, os, subprocess, sys

import config

DEFAULT_LOGO = config.LOGO
LOGO = DEFAULT_LOGO  # override via --logo

POS = {
    "center": "(W-w)/2:(H-h)/2",
    "tl": "20:20", "tr": "W-w-20:20", "bl": "20:H-h-20", "br": "W-w-20:H-h-20",
    "ml": "20:(H-h)/2", "mr": "W-w-20:(H-h)/2", "mt": "(W-w)/2:20", "mb": "(W-w)/2:H-h-20",
}

def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except (ValueError, IndexError):
        sys.exit(f"ffprobe failed on {path}: {(r.stderr or 'no video stream').strip()[:200]}")

def resolve_pos(pos, fx=None, fy=None):
    """Return (ox, oy) overlay expressions for a position spec."""
    if pos == "custom":
        if fx is None or fy is None:
            sys.exit("pos=custom needs fx and fy (0-1, box CENTER)")
        return f"W*{fx}-w/2", f"H*{fy}-h/2"
    if pos not in POS:
        sys.exit(f"pos must be one of: {', '.join(POS)} or custom")
    return POS[pos].split(":")

def run(inp, out, pos="center", width=0.55, max_gif_w=720, gif_fps=25, fx=None, fy=None):
    ox, oy = resolve_pos(pos, fx, fy)
    iw, _ = probe(inp)
    logo_w = int(iw * width)

    if out.lower().endswith(".gif"):
        # two-pass palette GIF. Preserve native res/fps when sane; only tame huge inputs.
        fc = (f"[0:v]hue=s=0,scale='min({max_gif_w},iw)':-2:flags=lanczos[bg];"
              f"[1:v]scale={logo_w}:-1[logo];"
              f"[bg][logo]overlay=x={ox}:y={oy}[base];"
              f"[base]split[s0][s1];"
              f"[s0]palettegen=stats_mode=diff[p];"
              f"[s1][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle")
        cmd = ["ffmpeg", "-y", "-i", inp, "-i", LOGO, "-filter_complex", fc, out]
    else:
        fc = (f"[0:v]hue=s=0[bg];"
              f"[1:v]scale={logo_w}:-1[logo];"
              f"[bg][logo]overlay=x={ox}:y={oy},"
              f"format=yuv420p[v]")
        cmd = ["ffmpeg", "-y", "-i", inp, "-i", LOGO, "-filter_complex", fc,
               "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "23",
               "-preset", "medium", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r

def run_photo(inp, out, pos="center", width=0.55, fx=None, fy=None):
    """Single-image variant: grayscale + logo stamp via ffmpeg (image2, no video codec)."""
    ox, oy = resolve_pos(pos, fx, fy)
    iw, _ = probe(inp)
    logo_w = int(iw * width)
    fc = (f"[0:v]hue=s=0[bg];"
          f"[1:v]scale={logo_w}:-1[logo];"
          f"[bg][logo]overlay=x={ox}:y={oy},format=rgb24[v]")
    cmd = ["ffmpeg", "-y", "-i", inp, "-i", LOGO, "-filter_complex", fc,
           "-map", "[v]", "-frames:v", "1", out]
    return subprocess.run(cmd, capture_output=True, text=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--pos", default="center", help=f"one of: {', '.join(POS)}")
    ap.add_argument("--width", type=float, default=config.LOGO_WIDTH, help="logo width as fraction of video width")
    ap.add_argument("--out", default=None)
    ap.add_argument("--logo", default=None, help="path to logo PNG/SVG (defaults to bundled asset)")
    a = ap.parse_args()
    global LOGO
    if a.logo: LOGO = a.logo
    out = a.out or os.path.splitext(a.input)[0] + "_nuked" + os.path.splitext(a.input)[1]
    r = run(a.input, out, a.pos, a.width)
    if r.returncode != 0 or not os.path.exists(out):
        print(r.stderr[-800:]); sys.exit(1)
    print(f"[OK] {out}  ({os.path.getsize(out)/1e6:.1f} MB, was {os.path.getsize(a.input)/1e6:.1f} MB)")

if __name__ == "__main__":
    main()
