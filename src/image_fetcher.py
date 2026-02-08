"""Fetch illustrative images for vocabulary words.

Image sources (tried in order):
1. Google Custom Search API (optional, requires CSE_API_KEY + CSE_CX)
2. Pixabay API (free key at https://pixabay.com/api/docs/)
3. Placeholder image (fallback)
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


# ---------------------------------------------------------------------------
# Source 1: Google Custom Search (optional)
# ---------------------------------------------------------------------------

def _search_google_image(query: str) -> str | None:
    api_key = config.GOOGLE_CSE_API_KEY or config.GEMINI_API_KEY
    cx = config.GOOGLE_CSE_CX
    if not api_key or not cx:
        return None

    params = {
        "key": api_key, "cx": cx, "q": query,
        "searchType": "image", "num": 1,
        "safe": "active", "imgSize": "medium",
    }
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params, timeout=15)
        data = resp.json()
        if resp.status_code != 200:
            err = data.get("error", {}).get("message", resp.text[:200])
            print(f"    [CSE error] {resp.status_code}: {err}")
            return None
        items = data.get("items", [])
        if items:
            return items[0]["link"]
    except Exception as e:
        print(f"    [CSE exception] {e}")
    return None


# ---------------------------------------------------------------------------
# Source 2: Pixabay API (free key at https://pixabay.com/api/docs/)
# ---------------------------------------------------------------------------

def _search_pixabay_image(query: str) -> str | None:
    """Search Pixabay for an image. Requires a free API key."""
    api_key = config.PIXABAY_API_KEY
    if not api_key:
        return None

    try:
        resp = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": api_key,
                "q": query,
                "image_type": "photo",
                "per_page": 3,
                "safesearch": "true",
                "lang": "en",
            },
            timeout=15,
        )
        if resp.status_code == 401:
            print("    [Pixabay error] Invalid API key")
            return None
        if resp.status_code != 200:
            print(f"    [Pixabay error] {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        hits = data.get("hits", [])
        if hits:
            # webformatURL is 640px wide — good quality for flashcards
            return hits[0].get("webformatURL")
    except Exception as e:
        print(f"    [Pixabay exception] {e}")
    return None


# ---------------------------------------------------------------------------
# Download + Placeholder
# ---------------------------------------------------------------------------

def _download_image(url: str, path: str) -> bool:
    try:
        resp = requests.get(url, timeout=15, stream=True, headers={
            "User-Agent": "Mozilla/5.0 (educational flashcard generator)"
        })
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and not url.lower().endswith(
                (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")):
            return False
        with open(path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        # Verify file isn't tiny/broken
        if os.path.getsize(path) < 500:
            os.remove(path)
            return False
        return True
    except Exception:
        return False


def _create_placeholder(word: str, path: str):
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_image(word: str, index: int) -> str:
    """Fetch an image for a vocabulary word. Returns path to local image file."""
    cache_dir = _get_cache_dir()
    safe_name = "".join(c if c.isalnum() else "_" for c in word)
    path = os.path.join(cache_dir, f"{index:02d}_{safe_name}.png")

    if os.path.exists(path):
        return path

    query = f"{word} vocabulary"

    # Try Google CSE first (if configured)
    if config.GOOGLE_CSE_CX:
        url = _search_google_image(query)
        if url and _download_image(url, path):
            return path

    # Try Pixabay (if API key configured)
    url = _search_pixabay_image(word)
    if url and _download_image(url, path):
        return path

    # Fallback: placeholder
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
        time.sleep(0.3)  # rate limit
    return result
