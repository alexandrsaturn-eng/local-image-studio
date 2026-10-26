const $ = (id) => document.getElementById(id);
const seconds = (value) => `${value.toLocaleString("ru-RU")} с`;

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Ошибка ${response.status}`);
  return data;
}

function setStatus(text, isError = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", isError);
}

// Shows elapsed seconds while a long request runs; returns a function that stops the timer.
function startTimer(label) {
  const started = Date.now();
  const tick = () => setStatus(`${label}… ${Math.round((Date.now() - started) / 1000)} с`);
  tick();
  const id = setInterval(tick, 1000);
  return () => clearInterval(id);
}

function describe(entry) {
  return `${entry.size}, seed ${entry.seed}, ${seconds(entry.seconds)}, ${entry.model}`;
}

async function writePrompt() {
  const idea = $("idea").value.trim();
  if (!idea) return setStatus("Сначала опишите идею", true);
  $("write-prompt").disabled = true;
  const stop = startTimer("Gemma пишет промпт");
  try {
    const data = await post("/api/prompt", { idea, style: $("style").value });
    $("prompt").value = data.prompt;
    setStatus(`Промпт готов за ${seconds(data.seconds)}. Его можно поправить.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    stop();
    $("write-prompt").disabled = false;
  }
}

async function generate() {
  const prompt = $("prompt").value.trim();
  if (!prompt) return setStatus("Сначала получите или напишите промпт", true);
  $("generate").disabled = true;
  const stop = startTimer("Draw Things рисует");
  try {
    const entry = await post("/api/generate", {
      prompt, idea: $("idea").value.trim(), model: $("model").value,
      aspect: $("aspect").value, quality: $("quality").value,
    });
    $("result-image").src = `/outputs/${encodeURIComponent(entry.file)}`;
    $("result-image").alt = entry.idea || entry.prompt;
    $("result-meta").textContent = describe(entry);
    $("result").hidden = false;
    setStatus(`Готово за ${seconds(entry.seconds)}. Файл: outputs/${entry.file}`);
    loadGallery();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    stop();
    $("generate").disabled = false;
  }
}

async function loadGallery() {
  const entries = await (await fetch("/api/gallery")).json();
  $("gallery-empty").hidden = entries.length > 0;
  $("gallery").replaceChildren(...entries.slice(0, 24).map((entry) => {
    const link = document.createElement("a");
    link.href = `/outputs/${encodeURIComponent(entry.file)}`;
    link.target = "_blank";
    link.title = entry.prompt;
    const img = document.createElement("img");
    img.src = link.href;
    img.alt = entry.idea || entry.prompt;
    img.loading = "lazy";
    const caption = document.createElement("span");
    caption.textContent = `${entry.idea || "без идеи"} · ${entry.size} · ${entry.model}`;
    link.append(img, caption);
    return link;
  }));
}

// Fills the model select from the server so the list lives in one place, drawthings.MODELS.
async function loadModels() {
  const data = await (await fetch("/api/models")).json();
  $("model").replaceChildren(...data.models.map((model) => {
    const steps = `${model.steps} ${model.steps < 5 ? "шага" : "шагов"}`;
    const option = new Option(`${model.title}, ${steps}`, model.id);
    option.selected = model.id === data.default;
    return option;
  }));
}

function showService(id, ok, text) {
  $(id).textContent = text;
  $(id).classList.toggle("ok", ok);
  $(id).classList.toggle("off", !ok);
}

// Checks Ollama and Draw Things so a stopped service shows up before the user presses a button.
async function checkServices() {
  let status;
  try {
    status = await (await fetch("/api/status")).json();
  } catch {
    showService("ollama-status", false, "Студия не отвечает");
    showService("drawthings-status", false, "Перезапустите python3 app.py");
    return;
  }
  const hints = [];
  if (status.ollama === "ok") {
    showService("ollama-status", true, "Ollama: Gemma готова");
  } else if (status.ollama === "no-model") {
    showService("ollama-status", false, "Ollama: модель не скачана");
    hints.push(`Скачайте модель: ollama pull ${status.ollama_model}`);
  } else {
    showService("ollama-status", false, "Ollama: не запущена");
    hints.push("Запустите приложение Ollama.");
  }
  if (status.drawthings_model) {
    showService("drawthings-status", true, "Draw Things: API включён");
  } else {
    showService("drawthings-status", false, "Draw Things: API выключен");
    hints.push("Откройте Draw Things и включите API-сервер: настройки → API Server, HTTP, порт 7860.");
  }
  $("services-hint").textContent = hints.join(" ");
  $("services-hint").hidden = hints.length === 0;
}

$("write-prompt").addEventListener("click", writePrompt);
$("generate").addEventListener("click", generate);
loadModels();
loadGallery();
checkServices();
setInterval(checkServices, 10000);
