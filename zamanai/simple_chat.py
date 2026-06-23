from __future__ import annotations

from zamanai.config import Config
from zamanai.groq_client import GroqClient
from zamanai.identity import assistant_identity


class SimpleChat:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.llm = GroqClient(config)

    def chat(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        lang = "Отвечай на русском." if self.config.language == "ru" else "Respond in English."
        system = (
            f"Ты — {self.config.assistant_name}, быстрый и точный AI-ассистент.\n"
            f"{assistant_identity(self.config)}\n{lang}\n"
            "Стиль: вежливо, ясно, по делу. Без лишней воды."
        )
        lines: list[str] = []
        for item in history or []:
            role, content = item.get("role", ""), (item.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                lines.append(f"Пользователь: {content}")
            elif role == "assistant":
                lines.append(f"Ассистент: {content}")
        lines.append(f"Пользователь: {message.strip()}")
        lines.append("Ассистент:")
        return self.llm.complete(system, "\n\n".join(lines), temperature=self.config.temperature_balanced)