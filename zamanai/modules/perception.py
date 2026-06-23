from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.types import CognitiveStage, MindState, PerceptionResult


class PerceptionModule(CognitiveModule):
    name = "perception"

    SYSTEM = """Ты — модуль ВОСПРИЯТИЯ в AGI-системе Джарвис.
Твоя задача: понять сообщение пользователя.
Сначала опирайся на блок «ТОЧНОЕ ПОНИМАНИЕ ВОПРОСА» — он важнее всего.
Не добавляй темы, которых пользователь не спрашивал (например сравнения с другими марками).
{identity}
На простые приветствия не приписывай нервозность или сомнения.
{lang}"""

    def process(self, state: MindState) -> MindState:
        memories = "\n".join(f"- {m}" for m in state.associations[:5]) or "Нет связанных воспоминаний."
        web = state.web_context or "Интернет не искали или ничего не найдено."

        data = self.llm.complete_json(
            self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
            f"""{self._understanding_block(state)}

Сообщение пользователя:
"{state.user_input}"

Данные из интернета (уже проверены):
{web}

Связанные воспоминания:
{memories}

Верни JSON:
{{
  "intent": "главное намерение пользователя",
  "topics": ["тема1", "тема2"],
  "emotional_tone": "эмоциональный тон",
  "urgency": "low|medium|high",
  "raw_analysis": "развёрнутый анализ 2-4 предложения"
}}""",
            temperature=self.config.temperature_analytical,
        )

        state.perception = PerceptionResult(
            intent=data.get("intent", ""),
            topics=data.get("topics", []),
            emotional_tone=data.get("emotional_tone", "neutral"),
            urgency=data.get("urgency", "medium"),
            raw_analysis=data.get("raw_analysis", ""),
        )
        state.add_thought(
            CognitiveStage.PERCEPTION,
            state.perception.raw_analysis,
            confidence=0.8,
            intent=state.perception.intent,
        )
        return state