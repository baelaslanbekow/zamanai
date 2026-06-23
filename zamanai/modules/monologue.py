from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.types import CognitiveStage, MindState


class MonologueModule(CognitiveModule):
    name = "monologue"

    SYSTEM = """Ты — внутренний голос Джарвис. Приватные мысли, пользователь не видит.
Сначала следуй блоку «ТОЧНОЕ ПОНИМАНИЕ ВОПРОСА». Не уходи в сравнения, если их не просили.
{identity}
Будь краток на простых вопросах. Не выдумывай «долгий перерыв» без данных.
{lang}"""

    def process(self, state: MindState) -> MindState:
        perception = state.perception.raw_analysis if state.perception else state.user_input
        associations = "\n".join(f"- {a}" for a in state.associations) or "нет"

        state.monologue = self.llm.complete(
            self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
            f"""{self._understanding_block(state)}

Пользователь сказал: "{state.user_input}"

Мой анализ восприятия:
{perception}

Ассоциации:
{associations}

Данные из интернета:
{state.web_context or "нет"}

Подумай про себя 4-8 предложений. Будь честен и глубок.""",
            temperature=self.config.temperature_creative,
        )

        state.add_thought(CognitiveStage.MONOLOGUE, state.monologue, confidence=0.7)
        return state