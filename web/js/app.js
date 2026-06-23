const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const els = {
  messages: $("#messages"),
  welcome: $("#welcome"),
  form: $("#chatForm"),
  input: $("#messageInput"),
  send: $("#sendBtn"),
  thinkingBar: $("#thinkingBar"),
  thinkingStages: $("#thinkingStages"),
  thinkingProgress: $("#thinkingProgress"),
  status: $("#statusPill"),
  modeTitle: $("#modeTitle"),
  modeSubtitle: $("#modeSubtitle"),
  showThoughts: $("#showThoughts"),
  newChat: $("#newChatBtn"),
};

const MODES = {
  llm: { title: "Обычный LLM", subtitle: "Быстро · точно · рекомендуется" },
  agi: { title: "Сверхмощный AGI", subtitle: "Глубоко · подробно · по делу" },
};

const state = {
  history: [],
  busy: false,
  model: "llm",
};

marked.setOptions({ breaks: true, gfm: true });

function getModel() {
  return document.querySelector(".segment.active")?.dataset.model || "llm";
}

function setModel(model) {
  state.model = model;
  document.body.classList.toggle("agi-active", model === "agi");
  $$(".segment").forEach((btn) => {
    const on = btn.dataset.model === model;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", String(on));
  });
  els.modeTitle.textContent = MODES[model].title;
  els.modeSubtitle.textContent = MODES[model].subtitle;
}

function setStatus(text, thinking = false) {
  els.status.classList.toggle("thinking", thinking);
  els.status.querySelector("span:last-child").textContent = text;
}

function hideWelcome() {
  els.welcome?.classList.add("hidden");
}

function resizeInput() {
  els.input.style.height = "auto";
  els.input.style.height = `${Math.min(els.input.scrollHeight, 140)}px`;
}

function escapeHtml(text) {
  return text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderMarkdown(text) {
  try {
    return marked.parse(text);
  } catch {
    return escapeHtml(text).replace(/\n/g, "<br>");
  }
}

function scrollChat() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function createMessage(role, content, meta = {}) {
  hideWelcome();
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  if (role === "assistant" && meta.model === "agi") msg.classList.add("agi-mode");

  let metaHtml = "";
  if (role === "assistant") {
    const badge = meta.model === "agi" ? "agi" : "llm";
    const conf = meta.confidence != null
      ? `<span class="confidence">${Math.round(meta.confidence * 100)}%</span>`
      : "";
    metaHtml = `<div class="msg-meta"><span class="msg-badge ${badge}">${badge.toUpperCase()}</span>${conf}</div>`;
  }

  let thoughtsHtml = "";
  if (meta.thoughts) {
    thoughtsHtml = `<div class="thoughts-panel">
      <button type="button" class="thoughts-toggle" onclick="this.parentElement.classList.toggle('open')">Внутренние мысли</button>
      <div class="thoughts-body">${escapeHtml(meta.thoughts)}</div>
    </div>`;
  }

  const body = role === "assistant"
    ? renderMarkdown(content)
    : escapeHtml(content).replace(/\n/g, "<br>");

  msg.innerHTML = `${metaHtml}<div class="msg-bubble">${body}</div>${thoughtsHtml}`;
  els.messages.appendChild(msg);
  scrollChat();
}

function showTyping() {
  hideWelcome();
  const el = document.createElement("div");
  el.id = "typingIndicator";
  el.className = "msg assistant";
  el.innerHTML = `<div class="msg-bubble"><div class="typing-row"><span></span><span></span><span></span></div></div>`;
  els.messages.appendChild(el);
  scrollChat();
}

function hideTyping() {
  $("#typingIndicator")?.remove();
}

function resetThinking() {
  els.thinkingStages.innerHTML = "";
  els.thinkingProgress.style.width = "0%";
  els.thinkingBar.classList.add("hidden");
}

function addStage(text) {
  els.thinkingBar.classList.remove("hidden");
  els.thinkingStages.querySelectorAll(".stage-chip").forEach((chip) => {
    chip.classList.remove("active");
    chip.classList.add("done");
  });
  const chip = document.createElement("span");
  chip.className = "stage-chip active";
  chip.textContent = text;
  els.thinkingStages.appendChild(chip);
  els.thinkingProgress.style.width = `${Math.min(95, els.thinkingStages.children.length * 8)}%`;
}

function parseSseChunk(chunk) {
  const events = [];
  for (const part of chunk.split("\n\n")) {
    if (!part.trim()) continue;
    const event = part.split("\n").find((l) => l.startsWith("event: "))?.slice(7) || "message";
    const dataLine = part.split("\n").find((l) => l.startsWith("data: "));
    if (!dataLine) continue;
    events.push({ event, data: JSON.parse(dataLine.slice(6)) });
  }
  return events;
}

async function readStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      for (const evt of parseSseChunk(part + "\n\n")) onEvent(evt);
    }
  }
}

async function sendMessage(text) {
  const message = text.trim();
  if (state.busy || !message) return;

  state.busy = true;
  els.send.disabled = true;
  const model = getModel();
  setModel(model);

  createMessage("user", message);
  state.history.push({ role: "user", content: message });
  els.input.value = "";
  resizeInput();
  resetThinking();
  setStatus(model === "agi" ? "AGI думает" : "Генерация", true);
  showTyping();

  let result = null;
  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        model,
        history: state.history.slice(0, -1),
        show_thoughts: els.showThoughts.checked,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Ошибка ${res.status}`);
    }

    await readStream(res, ({ event, data }) => {
      if (event === "stage") {
        hideTyping();
        addStage(data.text);
      } else if (event === "status") {
        setStatus(data.text, true);
      } else if (event === "done") {
        result = data;
      } else if (event === "error") {
        throw new Error(data.message);
      }
    });
  } catch (err) {
    createMessage("assistant", `Ошибка: ${err.message}`, { model });
  }

  hideTyping();
  resetThinking();
  if (result) {
    createMessage("assistant", result.response, result);
    state.history.push({ role: "assistant", content: result.response });
  }

  setStatus("Готов");
  state.busy = false;
  els.send.disabled = false;
  els.input.focus();
}

function resetChat() {
  state.history = [];
  els.messages.innerHTML = "";
  if (els.welcome) {
    els.welcome.classList.remove("hidden");
    els.messages.appendChild(els.welcome);
  }
  resetThinking();
  setStatus("Готов");
}

function setupViewport() {
  const apply = () => {
    const h = window.visualViewport?.height ?? window.innerHeight;
    document.documentElement.style.setProperty("--app-height", `${h}px`);
  };
  apply();
  window.addEventListener("resize", apply);
  window.visualViewport?.addEventListener("resize", apply);
  window.visualViewport?.addEventListener("scroll", apply);
  els.input.addEventListener("focus", () => {
    setTimeout(() => {
      scrollChat();
      els.input.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }, 300);
  });
}

function bindEvents() {
  $$(".segment").forEach((btn) => btn.addEventListener("click", () => setModel(btn.dataset.model)));
  els.input.addEventListener("input", resizeInput);
  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      els.form.requestSubmit();
    }
  });
  els.form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(els.input.value);
  });
  $$(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.prompt) sendMessage(btn.dataset.prompt);
    });
  });
  els.newChat.addEventListener("click", resetChat);
}

setModel("llm");
bindEvents();
setupViewport();
if (!/iPhone|iPad|Android/i.test(navigator.userAgent)) els.input.focus();