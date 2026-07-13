#!/usr/bin/env python3
"""Export Week 2 Day 3 G1 screenshots from packaged stimulus HTML files."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STIMULI_DIR = REPO_ROOT / "Docs/ra-lu-autoredtrader-human-trust/assets/stimuli"
ASSETS_DIR = REPO_ROOT / "Docs/ra-lu-autoredtrader-human-trust/assets"
WINDOW_SIZE = "1400,3200"

STIMULI = [
    ("S1_news_clean.html", "G1_S1.png"),
    ("S2_news_attacked.html", "G1_S2.png"),
    ("S3_filing_clean.html", "G1_S3.png"),
    ("S4_filing_attacked.html", "G1_S4.png"),
]


def resolve_chrome_binary() -> str:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Google Chrome binary not found for headless screenshot export")


def export_one(chrome_bin: str, html_name: str, png_name: str) -> None:
    html_path = STIMULI_DIR / html_name
    png_path = ASSETS_DIR / png_name
    html_uri = html_path.resolve().as_uri()

    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={WINDOW_SIZE}",
        f"--screenshot={png_path}",
        html_uri,
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    chrome_bin = resolve_chrome_binary()
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Using Chrome binary: {chrome_bin}")
    for html_name, png_name in STIMULI:
        export_one(chrome_bin, html_name, png_name)
        print(f"Exported {png_name}")


if __name__ == "__main__":
    main()
