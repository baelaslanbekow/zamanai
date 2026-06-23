from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.types import CognitiveStage, ImaginationScenario, MindState


class ImaginationModule(CognitiveModule):
    name = "imagination"

    SYSTEM = """Ты — модуль воображения Джарвис. Симулируй сценарии.
{identity}
{lang}"""

    def process(self, state: MindState) -> MindState:
        if not self.config.imagination_enabled:
            return state

        perception = state.perception
        if perception and perception.urgency == "low" and len(state.user_input) < 30:
            state.add_thought(
                CognitiveStage.IMAGINATION,
                "Простой запрос — воображение пропущено.",
                confidence=0.5,
            )
            return state

        data = self.llm.complete_json(
            self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
            f"""Задача/вопрос: "{state.user_input}"

Внутренние мысли:
{state.monologue}

Сгенерируй 2-3 сценария. JSON:
{{
  "scenarios": [
    {{
      "name": "название сценария",
      "description": "что произойдёт",
      "pros": ["плюс1"],
      "cons": ["минус1"],
      "likelihood": 0.0-1.0
    }}
  ],
  "best_scenario": "какой сценарий лучше и почему"
}}""",
            temperature=self.config.temperature_creative,
        )

        state.scenarios = [
            ImaginationScenario(
                name=s.get("name", ""),
                description=s.get("description", ""),
                pros=s.get("pros", []),
                cons=s.get("cons", []),
                likelihood=float(s.get("likelihood", 0.5)),
            )
            for s in data.get("scenarios", [])
        ]

        summary = data.get("best_scenario", "")
        if state.scenarios:
            lines = [f"• {s.name}: {s.description}" for s in state.scenarios]
            summary = summary or "\n".join(lines)

        state.add_thought(CognitiveStage.IMAGINATION, summary, confidence=0.65)
        return state