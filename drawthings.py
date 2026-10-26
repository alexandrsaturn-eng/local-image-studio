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

# Models the studio offers. Both are distilled: few steps and CFG 1; other settings would spoil the image.
MODELS = {
    "z-image": {"title": "Z-Image Turbo", "file": "z_image_turbo_1.0_i8x.ckpt", "steps": 8, "guidance": 1.0},
    "klein": {"title": "FLUX.2 klein 4B", "file": "flux_2_klein_4b_q8p.ckpt", "steps": 4, "guidance": 1.0},
}
DEFAULT_MODEL = "z-image"


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
            "Draw Things не отвечает. Откройте приложение и включите API-сервер: "
            "настройки → API Server, протокол HTTP, порт 7860."
        ) from error


def status():
    """Selected model name, or None when Draw Things or its API server is off."""
    try:
        return _request("/", timeout=2).get("model")
    except DrawThingsError:
        return None


def generate(prompt, aspect, quality, out_path, model=DEFAULT_MODEL, seed=None):
    """Generates an image into out_path (PNG). Returns the settings actually used."""
    width, height = target_size(aspect, quality)
    settings = MODELS[model]
    body = {
        "prompt": prompt, "negative_prompt": "", "width": _round_up(width), "height": _round_up(height),
        "model": settings["file"], "steps": settings["steps"], "guidance_scale": settings["guidance"],
    }
    if seed is not None:
        body["seed"] = seed
    result = _request("/sdapi/v1/txt2img", body)
    images = result.get("images") or []
    if not images:
        raise DrawThingsError(f"Draw Things не вернул картинку. Проверьте, что в приложении скачана модель {settings['title']}.")
    out_path.write_bytes(base64.b64decode(images[0]))
    if (body["width"], body["height"]) != (width, height):
        # sips ships with macOS (Draw Things is macOS-only anyway): crop to the exact size around the centre.
        subprocess.run(["sips", "-c", str(height), str(width), str(out_path)], check=True, capture_output=True)
    return {"width": width, "height": height, "seed": seed, "model": settings["title"], "steps": settings["steps"]}
