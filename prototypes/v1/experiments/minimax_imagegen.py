"""Measure MiniMax image-01: latency, size, and whether it survives a diagram prompt."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from minimax_probe import load_key, post  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots"

PROMPTS = [
    (
        "waveform",
        "Flat vector educational diagram of a speech waveform: a clean sound wave "
        "silhouette on a warm cream background, with a horizontal time axis, "
        "one marked vowel segment highlighted in burnt orange, minimal, "
        "no text, no letters, no numbers, textbook illustration style",
    ),
    (
        "spectrogram",
        "Flat vector educational diagram of a speech spectrogram: horizontal "
        "frequency bands in cool blue and teal on a pale background, vowel "
        "formant tracks visible as smooth curves, one region circled in orange, "
        "minimal, no text, no letters, no numbers, textbook illustration style",
    ),
]


def main() -> int:
    key = load_key()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, prompt in PROMPTS:
        t0 = time.time()
        out = post("/image_generation", {
            "model": "image-01",
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "n": 1,
            "response_format": "url",
        }, key, timeout=180.0)
        dt = time.time() - t0
        urls = (out.get("data") or {}).get("image_urls") or []
        print(f"[{name}] latency {dt:.1f}s  urls={len(urls)}")
        if not urls:
            print("   ", json.dumps(out, ensure_ascii=False)[:300])
            continue
        url = urls[0]
        with urllib.request.urlopen(url, timeout=60) as resp:
            blob = resp.read()
        path = OUT / f"gen-{name}.png"
        path.write_bytes(blob)
        print(f"   saved {path} ({len(blob)/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
