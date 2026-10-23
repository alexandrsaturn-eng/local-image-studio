"""Turns an idea written in Russian into a detailed English prompt with a local model in Ollama."""

import json
import urllib.request

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "hf.co/unsloth/gemma-4-12b-it-GGUF:Q4_K_M"

STYLES = {
    "photo": "a photorealistic photograph; name the lens, lighting and camera angle",
    "illustration": "a detailed digital illustration; name the art style, palette and mood",
    "cover": "a clean cover image for a blog post with empty space for a title; bold composition, few details",
}

SYSTEM = (
    "You write prompts for a local text-to-image model. The user gives a short idea, usually in Russian. "
    "Reply with ONE English prompt of 50-90 words describing subject, setting, lighting, composition and style. "
    "Keep every concrete detail the user asked for (objects, colours, text on signs in quotes, camera view). "
    "Do not add text or lettering unless the user asked for it. Reply with the prompt only, no comments."
)


class PromptWriterError(Exception):
    pass


def write_prompt(idea, style):
    body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.7},
        "system": SYSTEM,
        "prompt": f"Idea: {idea}\nThe image should be {STYLES[style]}.",
    }
    request = urllib.request.Request(
        OLLAMA_URL + "/api/generate", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            answer = json.load(response)
    except OSError as error:
        raise PromptWriterError("Ollama не отвечает. Запустите приложение Ollama или команду ollama serve.") from error
    prompt = (answer.get("response") or "").strip().strip('"')
    if not prompt:
        raise PromptWriterError("Модель вернула пустой промпт. Попробуйте ещё раз или опишите идею подробнее.")
    return prompt


def status():
    """'ok', 'no-model' (Ollama runs but the model is not downloaded) or 'off'."""
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=2) as response:
            models = {m["name"] for m in json.load(response).get("models", [])}
    except OSError:
        return "off"
    return "ok" if OLLAMA_MODEL in models else "no-model"
