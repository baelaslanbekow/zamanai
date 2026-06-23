from __future__ import annotations

from abc import ABC, abstractmethod

from zamanai.config import Config
from zamanai.groq_client import GroqClient
from zamanai.types import MindState


class CognitiveModule(ABC):
    name: str = "base"

    def __init__(self, llm: GroqClient, config: Config) -> None:
        self.llm = llm
        self.config = config

    @abstractmethod
    def process(self, state: MindState) -> MindState:
        ...

    def _lang_note(self) -> str:
        if self.config.language == "ru":
            return "Отвечай на русском языке."
        return "Respond in English."

    def _identity(self) -> str:
        from zamanai.identity import assistant_identity

        return assistant_identity(self.config)

    def _understanding_block(self, state: MindState) -> str:
        u = state.understanding
        if not u:
            return "Понимание: ещё не сформировано."
        not_asked = ", ".join(u.user_did_not_ask) or "—"
        avoid = ", ".join(u.avoid_assumptions) or "—"
        wants = ", ".join(u.user_wants) or "—"
        return f"""ТОЧНОЕ ПОНИМАНИЕ ВОПРОСА (приоритет над всем остальным):
Смысл: {u.exact_meaning}
Тема: {u.core_topic}
Пользователь хочет: {wants}
НЕ спрашивал: {not_asked}
ЗАПРЕЩЕНО добавлять: {avoid}
Фокус ответа: {u.answer_focus}
Это сравнение: {"да" if u.is_comparison_question else "НЕТ — не сравнивай с другими"}"""