const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const GROQ_MODEL = "llama-3.1-8b-instant";

function getGroqKey() {
  return localStorage.getItem("zaman_groq_key") || "";
}

function setGroqKey(key) {
  localStorage.setItem("zaman_groq_key", key.trim());
}

async function groqChat(apiKey, messages, temperature = 0.6) {
  const res = await fetch(GROQ_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: GROQ_MODEL,
      messages,
      temperature,
      max_tokens: 4096,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.error?.message || `Groq API: ${res.status}`);
  }
  const data = await res.json();
  return (data.choices?.[0]?.message?.content || "").trim();
}

async function groqLLM(apiKey, message, history = []) {
  const messages = [
    {
      role: "system",
      content: "Ты — ZamanAI, умный ассистент. Отвечай на русском: вежливо, ясно, по делу.",
    },
  ];
  for (const item of history) {
    if (!item.content) continue;
    messages.push({
      role: item.role === "assistant" ? "assistant" : "user",
      content: item.content,
    });
  }
  messages.push({ role: "user", content: message });
  return groqChat(apiKey, messages, 0.6);
}

async function groqAGI(apiKey, message, onStage) {
  const stages = [
    ["🎯 Понимание вопроса", "Кратко разбери вопрос пользователя. Выдели суть и ключевые темы.", message],
    ["🧠 Рассуждение", "На основе анализа построй логичное рассуждение. Используй факты, без выдумок.", null],
    ["❓ Сомнение", "Проверь рассуждение: найди слабые места и исправь их.", null],
    ["🪞 Рефлексия", "Сформируй финальный ответ: чётко, подробно, по делу, вежливо. Структурируй текст.", null],
  ];

  let context = "";
  for (const [label, task, input] of stages) {
    if (onStage) onStage(label);
    const userText = input || `Задача: ${task}\n\nКонтекст:\n${context}\n\nИсходный вопрос: ${message}`;
    const system = `Ты модуль AGI ZamanAI. ${task} Отвечай на русском.`;
    context = await groqChat(apiKey, [
      { role: "system", content: system },
      { role: "user", content: userText },
    ], 0.4);
  }

  if (onStage) onStage("✅ Готово");
  return {
    model: "agi",
    response: context,
    confidence: 0.82,
    thoughts: null,
  };
}