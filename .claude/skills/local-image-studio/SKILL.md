---
name: local-image-studio
description: Work with the Local Image Studio repository — a local web app that turns an idea in Russian into an English prompt (Gemma in Ollama) and an image (Draw Things API). Use when asked to run the studio, generate an image through it, debug it, change its features or UI, update its README or screenshots, or prepare it for publishing.
---

# Local Image Studio

A local web app for macOS: idea in Russian → English prompt from Gemma (Ollama) → image from Draw Things → file in `outputs/` and an entry in the gallery. Python standard library only, no pip dependencies.

## Structure

| File | What it does |
|---|---|
| `app.py` | HTTP server on 127.0.0.1:8000. Routes: `GET /` (static UI), `POST /api/prompt` `{idea, style}` → `{prompt, seconds}`, `POST /api/generate` `{prompt, idea, aspect, quality, seed?}` → gallery entry, `GET /api/gallery`, `GET /api/status` → `{ollama: ok/no-model/off, ollama_model, drawthings_model or null}`, `GET /outputs/<file>.png`. One generation at a time (`generation_lock`, 409 when busy). Every response carries `Cache-Control: no-cache` so the browser picks up UI changes. |
| `prompt_writer.py` | Calls Ollama `POST /api/generate` with `OLLAMA_MODEL`. `STYLES` holds the three styles (photo, illustration, cover); `SYSTEM` is the instruction for the model. |
| `drawthings.py` | `target_size(aspect, quality)` → exact size; `generate()` rounds sides up to multiples of 64, calls `POST /sdapi/v1/txt2img`, crops with `sips` to the exact size. `ASPECTS` and `QUALITY_MEGAPIXELS` define the options; Full HD = short side 1080. |
| `static/` | `index.html`, `style.css` (light and dark theme via CSS variables), `app.js` (two steps, timer, gallery). UI text is in Russian. |
| `outputs/` | Generated PNGs and `gallery.json`. Ignored by git. |
| `images/` | Screenshots used in README. |

## Run

1. Check the dependencies answer:
   ```bash
   curl -s http://127.0.0.1:11434/api/version          # Ollama
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7860/   # Draw Things, expect 200
   ```
   Draw Things must be open with Settings → API Server → HTTP, port 7860; after the app restarts the API server may be off again, and the studio's status bar turns red. If Ollama does not answer, start the Ollama app or `ollama serve`. `curl -s http://127.0.0.1:8000/api/status` shows both at once.
2. Start the server in the background: `python3 app.py`, then open http://127.0.0.1:8000.
3. Stop it by its PID (`lsof -t -iTCP:8000 -sTCP:LISTEN | xargs kill`): on macOS the process shows as `Python`, so `pkill -f "python3 app.py"` can miss it. "Address already in use" means an old server is still running.

## Check after a change

1. `python3 -m py_compile app.py drawthings.py prompt_writer.py` and remove `__pycache__/`.
2. Restart the server (old code stays loaded until then).
3. Smoke test the API:
   ```bash
   curl -s -X POST http://127.0.0.1:8000/api/prompt -d '{"idea":"","style":"photo"}'   # expect a 400 error message
   curl -s -X POST http://127.0.0.1:8000/api/prompt -d '{"idea":"кот на подоконнике","style":"photo"}'
   ```
   A real generation takes about 40 s at 1 MP and 90 s at Full HD on an M3 Pro; use quality `draft` for quick checks.
4. For UI changes, open the page in a browser and go through both steps; check the light and dark theme. A page opened before the no-cache header existed may need one hard reload (Cmd+Shift+R).
5. To see the red status and error messages without stopping anything, run a second copy on another port with unreachable addresses:
   ```bash
   python3 -c 'import app, drawthings, prompt_writer; from http.server import ThreadingHTTPServer; drawthings.DRAW_THINGS_URL="http://127.0.0.1:7999"; prompt_writer.OLLAMA_URL="http://127.0.0.1:7998"; ThreadingHTTPServer(("127.0.0.1", 8001), app.StudioHandler).serve_forever()'
   ```
   Never test the error path with a real `POST /api/generate` against the main server: if Draw Things is up, it draws a real image into the gallery.

## Making changes

- Keep the standard-library-only rule: no Flask, no requests, no Pillow. Cropping uses `sips`, which ships with macOS.
- Keep Python 3.9 compatible syntax (the macOS system Python): no `match`, no `X | Y` type unions.
- A new format: add it to `ASPECTS` in `drawthings.py` and to the `aspect` select in `static/index.html`.
- A new style: add it to `STYLES` in `prompt_writer.py` and to the `style` select.
- Another Ollama model or address: `OLLAMA_MODEL` / `OLLAMA_URL` in `prompt_writer.py`; Draw Things address: `DRAW_THINGS_URL` in `drawthings.py`.
- User-facing messages are in Russian; code, comments and identifiers are in English.

## README and screenshots

- README is in Russian and follows the course structure: Проблема, Пользователь, Основная функция, Формат результата, Минимальный функционал, Технологии, then install, usage, structure, skill.
- After a visible UI change, retake the screenshots: run a real generation, capture the idea+prompt step, the result and the gallery, save them as `images/01-idea-and-prompt.jpg`, `images/02-result.jpg`, `images/03-gallery.jpg`.
- Update the timing numbers in README only from a real run.

## Before publishing

- `git status` shows no `outputs/`, `__pycache__/` or `.DS_Store`.
- No personal data in the diff: gallery entries, local paths, emails.
- README renders: images resolve from `images/`, install steps match the code.
- Publish with GitHub CLI: `gh repo create <name> --public --source . --push`, or `git push` for an existing repo.
