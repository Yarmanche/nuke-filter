#!/usr/bin/env python3
"""
Shared configuration for the boxed-filter toolkit.

Everything is relative to this file's directory — clone the folder anywhere and
it works. All values can be overridden via environment variables or a ``.env``
file placed next to this script (see .env.example).

Nothing here is machine- or user-specific.
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# Optional .env next to the scripts (never overrides real environment vars).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE, ".env"))
except ImportError:
    pass  # python-dotenv is optional; plain env vars always work


def _env(key, default=None):
    return os.environ.get(key, default)


# ---- brand / appearance -----------------------------------------------------
APP_NAME    = _env("FILTER_APP_NAME", "Boxed Filter")   # display name (bot /start)
BRAND_TEXT  = _env("FILTER_TEXT", "YOUR BRAND")          # text rendered inside the box
BRAND_COLOR = _env("FILTER_COLOR", "196,30,30")          # box color, "R,G,B"
LOGO_WIDTH  = float(_env("FILTER_LOGO_WIDTH", "0.55"))   # logo width as fraction of image

# ---- paths (all relative to BASE by default) --------------------------------
LOGO       = _env("FILTER_LOGO", os.path.join(BASE, "assets", "nuke_logo.png"))
OUTPUT_DIR = _env("FILTER_OUT_DIR", os.path.join(BASE, "out"))
SCM        = os.path.join(BASE, "scripts", "nuke-filter.scm")  # GIMP Script-Fu filter

# ---- server / bot -----------------------------------------------------------
PORT  = int(_env("FILTER_PORT", "8788"))
# Bot token: FILTER_BOT_TOKEN is the canonical name; NUKE_BOT_TOKEN kept as a
# legacy alias so existing setups keep working.
TOKEN = _env("FILTER_BOT_TOKEN") or _env("NUKE_BOT_TOKEN")

# ---- font -------------------------------------------------------------------
# Optional explicit font (TTF). If unset, a heavy/bold system font is picked.
FILTER_FONT = _env("FILTER_FONT", "")

_FONT_CANDIDATES = [
    # Linux
    "/usr/share/fonts/TTF/FiraSansCompressed-Heavy.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    # Windows
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\impact.ttf",
]


def find_font():
    """Return a usable bold/heavy TTF path, or None if nothing suitable."""
    if FILTER_FONT and os.path.exists(FILTER_FONT):
        return FILTER_FONT
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def parse_color(spec=None):
    """Parse an 'R,G,B' string into a tuple. Raises ValueError on bad input."""
    rgb = tuple(int(x) for x in (spec or BRAND_COLOR).split(","))
    if len(rgb) != 3:
        raise ValueError("color must be R,G,B")
    return rgb
