"""Local Image Studio: an idea in Russian -> an English prompt (Gemma in Ollama) -> an image (Draw Things).

Run: python3 app.py, then open http://127.0.0.1:8000
Needs only the Python standard library.
"""

import json
import random
import re
import threading
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import drawthings
import prompt_writer

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "outputs"
GALLERY_PATH = OUTPUT_DIR / "gallery.json"
HOST, PORT = "127.0.0.1", 8000

# Draw Things renders one image at a time; a second request waits for nothing and is refused.
generation_lock = threading.Lock()


def load_gallery():
    if GALLERY_PATH.exists():
        return json.loads(GALLERY_PATH.read_text(encoding="utf-8"))
    return []


def save_to_gallery(entry):
    gallery = load_gallery()
    gallery.insert(0, entry)
    GALLERY_PATH.write_text(json.dumps(gallery, ensure_ascii=False, indent=1), encoding="utf-8")


def file_name(prompt):
    # The first words of the English prompt keep names readable; the timestamp keeps them unique.
    words = re.findall(r"[a-z0-9]+", prompt.lower())
    slug = "-".join(w for w in words if w not in {"a", "an", "the", "of", "photorealistic"})[:40].strip("-")
    return datetime.now().strftime("%Y-%m-%d-%H%M%S") + (f"-{slug}" if slug else "") + ".png"


class StudioHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/gallery":
            return self.send_json(200, load_gallery())
        if self.path == "/api/status":
            return self.send_json(200, {
                "ollama": prompt_writer.status(), "ollama_model": prompt_writer.OLLAMA_MODEL,
                "drawthings_model": drawthings.status(),
            })
        if self.path.startswith("/outputs/"):
            path = OUTPUT_DIR / Path(unquote(self.path[len("/outputs/"):])).name
            if path.suffix == ".png" and path.exists():
                return self.send_file(path, "image/png")
            return self.send_json(404, {"error": "Картинка не найдена"})
        return super().do_GET()

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self.send_json(400, {"error": "Некорректный запрос"})
        if self.path == "/api/prompt":
            return self.handle_prompt(body)
        if self.path == "/api/generate":
            return self.handle_generate(body)
        return self.send_json(404, {"error": "Нет такого адреса"})

    def handle_prompt(self, body):
        idea, style = (body.get("idea") or "").strip(), body.get("style", "photo")
        if not idea or style not in prompt_writer.STYLES:
            return self.send_json(400, {"error": "Опишите идею и выберите стиль"})
        try:
            started = time.time()
            prompt = prompt_writer.write_prompt(idea, style)
        except prompt_writer.PromptWriterError as error:
            return self.send_json(502, {"error": str(error)})
        self.send_json(200, {"prompt": prompt, "seconds": round(time.time() - started, 1)})

    def handle_generate(self, body):
        prompt, idea = (body.get("prompt") or "").strip(), (body.get("idea") or "").strip()
        aspect, quality = body.get("aspect", "1:1"), body.get("quality", "standard")
        if not prompt or aspect not in drawthings.ASPECTS or quality not in ("draft", "standard", "fullhd"):
            return self.send_json(400, {"error": "Нужны промпт, формат и качество"})
        if not generation_lock.acquire(blocking=False):
            return self.send_json(409, {"error": "Уже рисуется другая картинка, дождитесь её"})
        try:
            OUTPUT_DIR.mkdir(exist_ok=True)
            name = file_name(prompt)
            seed = body.get("seed") or random.randint(1, 2**31 - 1)
            started = time.time()
            used = drawthings.generate(prompt, aspect, quality, OUTPUT_DIR / name, seed=seed)
            entry = {
                "file": name, "idea": idea, "prompt": prompt, "aspect": aspect, "quality": quality,
                "size": f"{used['width']}x{used['height']}", "seed": seed, "model": drawthings.current_model(),
                "seconds": round(time.time() - started, 1), "created": datetime.now().isoformat(timespec="seconds"),
            }
            save_to_gallery(entry)
            self.send_json(200, entry)
        except drawthings.DrawThingsError as error:
            self.send_json(502, {"error": str(error)})
        finally:
            generation_lock.release()

    def end_headers(self):
        # Without this the browser keeps an old app.js / style.css after the studio is updated.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_json(self, status, data):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_file(self, path, content_type):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"Local Image Studio: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), StudioHandler).serve_forever()
