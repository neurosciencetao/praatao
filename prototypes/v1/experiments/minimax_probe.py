"""Probe the MiniMax API that DSH itself uses: text, vision, image generation.

The key is read from DSH's own credential store.  It is never printed.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CREDS = Path.home() / ".dsh" / ".credentials.yaml"
BASE = "https://api.minimaxi.com/v1"
MODEL = "MiniMax-M3.1-Flash"


def load_key() -> str:
    """Read MINIMAX_CN_API_KEY out of DSH's credential file (never printed)."""
    text = CREDS.read_text(encoding="utf-8", errors="replace")
    in_refs = False
    for raw in text.splitlines():
        if raw.strip().startswith("refs:"):
            in_refs = True
            continue
        if in_refs:
            if not raw.startswith((" ", "\t")) or not raw.strip():
                break
            key, _, value = raw.partition(":")
            if key.strip() == "MINIMAX_CN_API_KEY":
                value = value.strip().strip("'\"")
                if value.startswith(("keychain:", "vault:", "cred:")):
                    raise SystemExit(f"credential is an indirect reference: {value[:20]}...")
                return value
    env = os.environ.get("MINIMAX_CN_API_KEY")
    if env:
        return env
    raise SystemExit("MINIMAX_CN_API_KEY not found")


def post(path: str, payload: dict, key: str, timeout: float = 90.0) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    key = load_key()
    print(f"key loaded, length={len(key)}, prefix={key[:6]}...")

    print("\n=== 1. text completion ===")
    t0 = time.time()
    try:
        out = post("/chat/completions", {
            "model": MODEL,
            "messages": [{"role": "user", "content": "用一句话解释什么是基频。"}],
            "max_tokens": 200,
        }, key)
        print(f"latency {time.time()-t0:.1f}s")
        print("reply:", out["choices"][0]["message"]["content"][:220])
        print("usage:", out.get("usage"))
    except urllib.error.HTTPError as exc:
        print("HTTPError", exc.code, exc.read().decode("utf-8", "replace")[:600])
    except Exception as exc:
        print("failed:", type(exc).__name__, exc)

    print("\n=== 2. vision (image_url with a base64 PNG) ===")
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        print("Pillow missing:", exc)
        return 1
    img = Image.new("RGB", (320, 120), (250, 246, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 140, 100], outline=(200, 80, 40), width=3)
    d.text((150, 55), "Praat spectrogram", fill=(60, 40, 20))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    t0 = time.time()
    try:
        out = post("/chat/completions", {
            "model": MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "这张图里有什么？一句话回答。"},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }],
            "max_tokens": 300,
        }, key)
        print(f"latency {time.time()-t0:.1f}s")
        print("reply:", out["choices"][0]["message"]["content"][:300])
        print("usage:", out.get("usage"))
    except urllib.error.HTTPError as exc:
        print("HTTPError", exc.code, exc.read().decode("utf-8", "replace")[:600])
    except Exception as exc:
        print("failed:", type(exc).__name__, exc)

    print("\n=== 3. image generation ===")
    for model in ("MiniMax-Image-01",):
        t0 = time.time()
        try:
            out = post("/image_generation", {
                "model": model,
                "prompt": "A clean minimal diagram of a Praat sound waveform "
                          "with a labelled time axis, soft warm palette, "
                          "flat vector illustration",
                "aspect_ratio": "16:9",
                "n": 1,
                "response_format": "url",
            }, key, timeout=180.0)
            print(f"model {model}: latency {time.time()-t0:.1f}s")
            print(json.dumps(out, ensure_ascii=False)[:700])
        except urllib.error.HTTPError as exc:
            print(f"model {model}: HTTPError", exc.code,
                  exc.read().decode("utf-8", "replace")[:500])
        except Exception as exc:
            print(f"model {model}: failed:", type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
