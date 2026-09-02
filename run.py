#!/usr/bin/env python3
"""
Boxed-photo filter — grayscale + centered colored box logo, using GIMP (batch).

Usage:
  python3 run.py photo.jpg                      # one file -> out/photo.jpg
  python3 run.py folder/                        # every image in folder -> out/
  python3 run.py *.jpg                          # shell glob
  python3 run.py in.jpg --text "YOUR BRAND"     # change logo text
  python3 run.py in.jpg --color 200,30,30       # change box color (R,G,B)
  python3 run.py in.jpg --box-width 0.34        # box width as fraction of image
  python3 run.py in.jpg --grain                 # add light 90s film grain too

Requires: GIMP 3 (system package), Pillow, a bold font (auto-detected).
"""
import argparse, os, subprocess, sys, tempfile

import config

LOGO = config.LOGO  # override via --logo
IMG_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic"}

def render_logo(text, rgb, out_path):
    from PIL import Image, ImageDraw, ImageFont
    fpath = config.find_font()
    if fpath:
        font = ImageFont.truetype(fpath, 200)
    else:
        try:
            font = ImageFont.load_default(size=200)
        except TypeError:
            font = ImageFont.load_default()
    tb = font.getbbox(text)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    # match reference: text fills 93% box width, 64% box height
    box_h = int(th / 0.64)
    box_w = int(tw / 0.93)
    x0 = (box_w - tw) // 2 - tb[0]
    y0 = (box_h - th) // 2 - tb[1]
    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, box_w - 1, box_h - 1], fill=(*rgb, 255))
    d.text((x0, y0), text, font=font, fill=(255, 255, 255, 255))
    img.save(out_path)
    return out_path

def add_grain(img_path):
    """Light 90s-style film grain via Pillow (fast, subtle)."""
    from PIL import Image, ImageChops, ImageFilter
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    # blurred monochrome noise, overlaid on the (already grayscaled) image
    noise = Image.effect_noise((w, h), 32).filter(ImageFilter.GaussianBlur(0.6))
    gray = img.convert("L").convert("RGB")
    return ImageChops.overlay(gray, Image.merge("RGB", (noise, noise, noise)))

def run_gimp(inp, outp):
    run = os.path.join(tempfile.gettempdir(), "nuke_run.scm")
    with open(run, "w") as f:
        f.write(f'(load "{config.SCM}")\n(nuke-filter "{inp}" "{outp}" "{LOGO}")\n')
    cmd = ["gimp", "-i", "-b", f'(load "{run}")', "-b", "(gimp-quit 0)"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stderr

def main():
    global LOGO
    ap = argparse.ArgumentParser(description="grayscale + colored-box logo filter (GIMP)")
    ap.add_argument("inputs", nargs="+", help="file(s) or folder(s)")
    ap.add_argument("--text", default=config.BRAND_TEXT, help="text rendered in the box")
    ap.add_argument("--color", default=config.BRAND_COLOR, help="box color R,G,B")
    ap.add_argument("--outdir", default=config.OUTPUT_DIR)
    ap.add_argument("--grain", action="store_true", help="add subtle 90s film grain")
    ap.add_argument("--logo", default=None, help="path to logo PNG (defaults to bundled asset)")
    args = ap.parse_args()

    try:
        rgb = config.parse_color(args.color)
    except ValueError:
        sys.exit("--color must be R,G,B")

    os.makedirs(args.outdir, exist_ok=True)
    if args.logo:
        LOGO = args.logo  # external brand asset: skip text/color regen
    else:
        # regen logo (cheap; picks up --text / --color changes)
        render_logo(args.text, rgb, LOGO)

    files = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            for f in sorted(os.listdir(inp)):
                if os.path.splitext(f)[1].lower() in IMG_EXT:
                    files.append(os.path.join(inp, f))
        elif os.path.splitext(inp)[1].lower() in IMG_EXT:
            files.append(inp)
        else:
            sys.exit(f"not an image or folder: {inp}")

    if not files:
        sys.exit("no images found")

    ok = fail = 0
    for f in files:
        outp = os.path.join(args.outdir, os.path.splitext(os.path.basename(f))[0] + ".jpg")
        code, err = run_gimp(f, outp)
        if code == 0 and os.path.exists(outp) and os.path.getsize(outp) > 0:
            ok += 1
            print(f"[OK]   {f}  ->  {outp}")
            if args.grain:
                grained = add_grain(outp); grained.save(outp)
        else:
            fail += 1
            print(f"[FAIL] {f}")
            errs = [l for l in (err or "").splitlines() if "Error" in l]
            print("   " + (errs[-1] if errs else f"gimp exited with code {code}"))

    print(f"\nDone: {ok} ok, {fail} failed. Output in {args.outdir}")

if __name__ == "__main__":
    main()
