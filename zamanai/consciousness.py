from __future__ import annotations

from zamanai.modules.drives import DrivesSystem
from zamanai.types import CognitiveStage, MindState, ThoughtStep


class GlobalWorkspace:
    """
    Global Workspace Theory — сознание как арена конкурирующих мыслей.
    Решает, какие когнитивные этапы активировать.
    """

    STAGE_LABELS = {
        CognitiveStage.UNDERSTANDING: "🎯 Понимание вопроса",
        CognitiveStage.WEB_SEARCH: "🌐 Поиск в интернете",
        CognitiveStage.WHY_CHAIN: "🔗 Цепочка «почему»",
        CognitiveStage.PERCEPTION: "👁  Восприятие",
        CognitiveStage.ASSOCIATION: "🔗 Ассоциации",
        CognitiveStage.MONOLOGUE: "💭 Монолог",
        CognitiveStage.IMAGINATION: "🌌 Воображение",
        CognitiveStage.REASONING: "🧠 Логика",
        CognitiveStage.DOUBT: "❓ Сомнение",
        CognitiveStage.REFLECTION: "🪞 Рефлексия",
        CognitiveStage.DEBATE: "⚖️  Дебаты",
        CognitiveStage.SELF_REVIEW: "🔄 Самопроверка",
        CognitiveStage.DECISION: "✅ Решение",
        CognitiveStage.MEMORY: "💾 Память",
    }

    def __init__(self, drives: DrivesSystem) -> None:
        self.drives = drives

    def plan_pipeline(self, state: MindState) -> list[str]:
        """Какие модули запускать для данного ввода."""
        pipeline = [
            "understanding",
            "web_search",
            "perception",
            "association",
            "monologue",
        ]

        urgency = state.perception.urgency if state.perception else "medium"
        if self.drives.should_imagine(urgency, len(state.user_input)):
            pipeline.append("imagination")

        pipeline.extend(["reasoning", "doubt", "reflection", "memory"])
        return pipeline

    def broadcast(self, state: MindState, stage: CognitiveStage, content: str) -> None:
        """Публикует мысль в глобальное рабочее пространство."""
        salience = self._compute_salience(state, stage, content)
        state.add_thought(stage, content, confidence=salience, broadcast=True)

    def _compute_salience(self, state: MindState, stage: CognitiveStage, content: str) -> float:
        base = {
            CognitiveStage.UNDERSTANDING: 0.95,
            CognitiveStage.WEB_SEARCH: 0.88,
            CognitiveStage.WHY_CHAIN: 0.82,
            CognitiveStage.DEBATE: 0.84,
            CognitiveStage.SELF_REVIEW: 0.88,
            CognitiveStage.PERCEPTION: 0.9,
            CognitiveStage.ASSOCIATION: 0.6,
            CognitiveStage.MONOLOGUE: 0.7,
            CognitiveStage.IMAGINATION: 0.65,
            CognitiveStage.REASONING: 0.85,
            CognitiveStage.DOUBT: 0.8,
            CognitiveStage.REFLECTION: 0.9,
            CognitiveStage.DECISION: 1.0,
            CognitiveStage.MEMORY: 0.5,
        }.get(stage, 0.5)

        if state.perception and state.perception.urgency == "high":
            if stage in (CognitiveStage.REASONING, CognitiveStage.REFLECTION):
                base += 0.1

        return min(base, 1.0)

    def dominant_thought(self, state: MindState) -> ThoughtStep | None:
        if not state.thought_trace:
            return None
        return max(state.thought_trace, key=lambda t: t.confidence)

    def format_thoughts(self, state: MindState) -> str:
        lines = []
        for step in state.thought_trace:
            label = self.STAGE_LABELS.get(step.stage, step.stage.value)
            lines.append(f"{label} [{step.confidence:.0%}]\n{step.content}\n")
        return "\n".join(lines)

    def thoughts_as_list(self, state: MindState) -> list[dict]:
        return [
            {
                "stage": step.stage.value,
                "label": self.STAGE_LABELS.get(step.stage, step.stage.value),
                "content": step.content,
                "confidence": step.confidence,
            }
            for step in state.thought_trace
        ]