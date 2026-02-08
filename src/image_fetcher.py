"""Fetch illustrative images for vocabulary words.

Supports two strategies:
1. Google Custom Search API (requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX)
2. Fallback: generate a colored placeholder image with the word text
"""

import os
import time
import requests

import src.config as config

_IMG_CACHE_DIR = None


def _get_cache_dir():
    global _IMG_CACHE_DIR
    _IMG_CACHE_DIR = os.path.join(config.OUTPUT_DIR, "images")
    os.makedirs(_IMG_CACHE_DIR, exist_ok=True)
    return _IMG_CACHE_DIR


def _search_google_image(query: str) -> str | None:
    """Use Google Custom Search JSON API to find an image URL."""
    api_key = config.GOOGLE_CSE_API_KEY or config.GEMINI_API_KEY
    cx = config.GOOGLE_CSE_CX
    if not api_key or not cx:
        return None

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "num": 1,
        "safe": "active",
        "imgSize": "medium",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if resp.status_code != 200:
            err = data.get("error", {}).get("message", resp.text[:200])
            print(f"    [CSE error] {resp.status_code}: {err}")
            return None
        items = data.get("items", [])
        if items:
            return items[0]["link"]
        else:
            print(f"    [CSE] No image results for '{query}'")
    except Exception as e:
        print(f"    [CSE exception] {e}")
    return None


def _download_image(url: str, path: str) -> bool:
    """Download an image from a URL and save to path."""
    try:
        resp = requests.get(url, timeout=15, stream=True, headers={
            "User-Agent": "Mozilla/5.0 (educational flashcard generator)"
        })
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and not url.lower().endswith(
                (".jpg", ".jpeg", ".png", ".gif", ".webp")):
            return False
        with open(path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return True
    except Exception:
        return False


def _create_placeholder(word: str, path: str):
    """Create a simple placeholder PNG image with the word."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (300, 200), color=(230, 240, 255))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except (OSError, IOError):
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), word, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (300 - tw) // 2
        y = (200 - th) // 2
        draw.text((x, y), word, fill=(60, 80, 120), font=font)
        draw.rectangle([(2, 2), (297, 197)], outline=(100, 140, 200), width=2)
        img.save(path, "PNG")
    except ImportError:
        import struct
        import zlib

        def _minimal_png(w, h, r, g, b):
            raw = b""
            for _ in range(h):
                raw += b"\x00" + bytes([r, g, b]) * w
            compressed = zlib.compress(raw)

            def chunk(ctype, data):
                c = ctype + data
                return (struct.pack(">I", len(data)) + c +
                        struct.pack(">I", zlib.crc32(c) & 0xffffffff))

            ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
            return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
                    chunk(b"IDAT", compressed) + chunk(b"IEND", b""))

        with open(path, "wb") as f:
            f.write(_minimal_png(300, 200, 230, 240, 255))


def fetch_image(word: str, index: int) -> str:
    """Fetch an image for a vocabulary word. Returns path to local image file."""
    cache_dir = _get_cache_dir()
    safe_name = "".join(c if c.isalnum() else "_" for c in word)
    path = os.path.join(cache_dir, f"{index:02d}_{safe_name}.png")

    if os.path.exists(path):
        return path

    query = f"{word} illustration educational"
    image_url = _search_google_image(query)
    if image_url and _download_image(image_url, path):
        return path

    _create_placeholder(word, path)
    return path


def fetch_all_images(words: list[dict], on_progress=None) -> dict[str, str]:
    """Fetch images for all vocabulary words. Returns {word: image_path}."""
    result = {}
    for i, w in enumerate(words):
        word = w["word"]
        if on_progress:
            on_progress(f"Fetching image {i + 1}/{len(words)}: {word}")
        path = fetch_image(word, i)
        result[word] = path
        if config.GOOGLE_CSE_CX:
            time.sleep(0.3)
    return result
