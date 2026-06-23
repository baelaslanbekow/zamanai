from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.thinking_depth import WHY_COUNTS, ThinkingDepth
from zamanai.types import CognitiveStage, MindState, WhyStep


class WhyChainModule(CognitiveModule):
    """Цепочка «5 почему» — докапывается до корневой причины."""

    name = "why_chain"

    def process(self, state: MindState) -> MindState:
        depth = ThinkingDepth(state.thinking_depth)
        count = WHY_COUNTS.get(depth, 0)
        if count == 0:
            return state

        context = state.web_context or "нет данных из интернета"
        chain: list[WhyStep] = []
        current_q = state.user_input

        for i in range(count):
            answer = self.llm.complete(
                f"""Ты анализируешь причинно-следственные связи (метод «5 почему»).
Шаг {i + 1} из {count}. Отвечай кратко и по существу.
{self._identity()}
{self._lang_note()}""",
                f"""{self._understanding_block(state)}

Вопрос: {current_q}

Контекст из интернета: {context[:1500]}
Монолог: {state.monologue[:500] if state.monologue else "ещё нет"}

Дай глубокий ответ на текущий «почему/как». 2-4 предложения.""",
                temperature=0.3,
            )
            chain.append(WhyStep(question=current_q, answer=answer))
            current_q = f"Почему: {answer}"

        state.why_chain = chain
        summary = "\n".join(
            f"Почему «{s.question[:80]}» → {s.answer}" for s in chain
        )
        state.add_thought(
            CognitiveStage.WHY_CHAIN,
            f"Цепочка из {count} «почему»:\n\n{summary}",
            confidence=0.8,
            steps=count,
        )
        return state