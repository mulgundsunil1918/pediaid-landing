#!/usr/bin/env python3
"""Render assets/og-card.html to assets/og-image.jpg at exactly 1200x630.

Why a real card and not the logo
--------------------------------
Every page pointed og:image at assets/pediaid-logo.png -- a 960x960 square.
Facebook, WhatsApp, LinkedIn and Slack all want 1200x630; given a square they
render a thumbnail chip instead of a card, so every share of all 284 pages
looked like a broken link with an icon next to it.

Run after editing assets/og-card.html:
    python3 scripts/render_og_image.py
"""
import base64
import pathlib
import shutil
import subprocess
import struct
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "assets" / "og-card.html"
LOGO = ROOT / "assets" / "pediaid-logo.png"
OUT = ROOT / "assets" / "og-image.jpg"

W, H = 1200, 630

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if c and pathlib.Path(c).exists():
            return c
    sys.exit("No Chrome/Chromium found -- install one or edit CHROME_CANDIDATES.")


def main():
    html = TEMPLATE.read_text(encoding="utf-8")
    logo_uri = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    html = html.replace("{{LOGO_DATA_URI}}", logo_uri)

    with tempfile.TemporaryDirectory() as td:
        page = pathlib.Path(td) / "card.html"
        page.write_text(html, encoding="utf-8")
        png = pathlib.Path(td) / "card.png"

        subprocess.run(
            [
                find_chrome(), "--headless", "--disable-gpu", "--hide-scrollbars",
                f"--screenshot={png}", f"--window-size={W},{H}",
                # The card loads Inter from Google Fonts; without a virtual-time
                # budget Chrome screenshots before the webfont arrives and the
                # whole card silently renders in Helvetica.
                "--virtual-time-budget=6000",
                page.as_uri(),
            ],
            check=True, capture_output=True,
        )

        w, h = struct.unpack(">II", png.read_bytes()[16:24])
        assert (w, h) == (W, H), f"rendered {w}x{h}, expected {W}x{H}"

        # A flat-gradient PNG out of Chrome is ~430 KB; the same card as a
        # quality-90 JPEG is ~150 KB and indistinguishable at card size.
        subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90",
             str(png), "--out", str(OUT)],
            check=True, capture_output=True,
        )

    print(f"{OUT.relative_to(ROOT)}  {W}x{H}  {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
