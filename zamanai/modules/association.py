from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.modules.memory import MemorySystem
from zamanai.types import CognitiveStage, MindState


class AssociationModule(CognitiveModule):
    name = "association"

    SYSTEM = """Ты — модуль АССОЦИАЦИЙ в AGI Джарвис.
Находи связи между вводом и воспоминаниями из базы данных.
Только ассоциации по теме вопроса. Не тяни из памяти нерелевантные людей и события.
{identity}
{lang}"""

    def __init__(self, llm, config, memory: MemorySystem) -> None:
        super().__init__(llm, config)
        self.memory = memory

    def process(self, state: MindState) -> MindState:
        recall_query = state.understanding.core_topic if state.understanding else state.user_input
        recalled = self.memory.recall(recall_query, limit=8)
        memory_text = "\n".join(
            f"[{m.memory_type.value}] {m.content}" for m in recalled
        ) or "Память пуста."

        data = self.llm.complete_json(
            self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
            f"""{self._understanding_block(state)}

Ввод: "{state.user_input}"

Данные из интернета:
{state.web_context or "нет"}

Воспоминания из памяти:
{memory_text}

Верни JSON:
{{
  "associations": ["ассоциация 1", "ассоциация 2"],
  "relevant_memories": ["какие воспоминания важны сейчас"],
  "emotional_resonance": "эмоциональный отклик"
}}""",
            temperature=self.config.temperature_creative,
        )

        state.associations = data.get("associations", []) + data.get("relevant_memories", [])
        resonance = data.get("emotional_resonance", "")
        if resonance:
            state.associations.append(resonance)

        state.add_thought(
            CognitiveStage.ASSOCIATION,
            "; ".join(state.associations) or "Новый контекст, без сильных ассоциаций.",
            confidence=0.6,
        )
        return state