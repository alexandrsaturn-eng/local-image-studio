"""Draw Things HTTP API client: picks a valid size, generates, crops to the exact size."""

import base64
import json
import math
import subprocess
import urllib.request

DRAW_THINGS_URL = "http://127.0.0.1:7860"

# Draw Things only accepts sides that are multiples of 64.
SIZE_STEP = 64

ASPECTS = {"1:1": (1, 1), "16:9": (16, 9), "9:16": (9, 16), "4:3": (4, 3), "3:4": (3, 4)}
# Megapixels for each quality level; "fullhd" is set by the short side instead.
QUALITY_MEGAPIXELS = {"draft": 0.5, "standard": 1.0}


class DrawThingsError(Exception):
    pass


def _round_up(value):
    return -(-value // SIZE_STEP) * SIZE_STEP


def target_size(aspect, quality):
    """Exact output size in pixels for an aspect ratio and quality level."""
    w, h = ASPECTS[aspect]
    if quality == "fullhd":
        # Full HD = the short side is 1080: 1920x1080, 1080x1920, 1080x1080.
        short_side = 1080
        return (round(short_side * w / h), short_side) if w >= h else (short_side, round(short_side * h / w))
    megapixels = QUALITY_MEGAPIXELS[quality]
    width = round(math.sqrt(megapixels * 1_000_000 * w / h) / SIZE_STEP) * SIZE_STEP
    return width, round(width * h / w)


def _request(path, body=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        DRAW_THINGS_URL + path, data=data, headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except OSError as error:
        raise DrawThingsError(
            f"Draw Things is not responding at {DRAW_THINGS_URL}: is the app running with the API server on?"
        ) from error


def current_model():
    return _request("/", timeout=5).get("model")


def generate(prompt, aspect, quality, out_path, seed=None):
    """Generates an image into out_path (PNG). Returns the settings actually used."""
    width, height = target_size(aspect, quality)
    body = {"prompt": prompt, "negative_prompt": "", "width": _round_up(width), "height": _round_up(height)}
    if seed is not None:
        body["seed"] = seed
    result = _request("/sdapi/v1/txt2img", body)
    images = result.get("images") or []
    if not images:
        raise DrawThingsError("Draw Things returned no image")
    out_path.write_bytes(base64.b64decode(images[0]))
    if (body["width"], body["height"]) != (width, height):
        # sips ships with macOS (Draw Things is macOS-only anyway): crop to the exact size around the centre.
        subprocess.run(["sips", "-c", str(height), str(width), str(out_path)], check=True, capture_output=True)
    return {"width": width, "height": height, "seed": seed}
