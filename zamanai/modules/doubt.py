from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.types import CognitiveStage, MindState


class DoubtModule(CognitiveModule):
    name = "doubt"

    SYSTEM = """Ты — метакогниция Джарвис. Критикуй рассуждения, ищи bias.
{identity}
{lang}"""

    def process(self, state: MindState) -> MindState:
        data = self.llm.complete_json(
            self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
            f"""{self._understanding_block(state)}

Вопрос пользователя: "{state.user_input}"

Факты из интернета:
{state.web_context or "нет"}

Мои рассуждения:
{state.reasoning}

Внутренний монолог:
{state.monologue}

Критически оцени. JSON:
{{
  "doubt_analysis": "что вызывает сомнение",
  "confidence": 0.0-1.0,
  "knowledge_gaps": ["чего не знаю"],
  "biases_detected": ["возможные искажения"],
  "should_ask_clarification": true/false
}}""",
            temperature=self.config.temperature_analytical,
        )

        state.doubt = data.get("doubt_analysis", "")
        base_confidence = float(data.get("confidence", 0.5))
        if state.web_context and state.web_sources:
            base_confidence = min(base_confidence + 0.15, 0.95)
        state.confidence = base_confidence
        gaps = data.get("knowledge_gaps", [])
        biases = data.get("biases_detected", [])

        doubt_text = state.doubt
        if gaps:
            doubt_text += f"\nПробелы: {', '.join(gaps)}"
        if biases:
            doubt_text += f"\nBias: {', '.join(biases)}"

        state.add_thought(
            CognitiveStage.DOUBT,
            doubt_text,
            confidence=state.confidence,
            should_clarify=data.get("should_ask_clarification", False),
        )
        return state