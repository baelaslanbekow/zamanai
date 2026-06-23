from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.response_guard import is_usable_response
from zamanai.types import CognitiveStage, MindState, SelfReviewResult


class SelfReviewModule(CognitiveModule):
    """Обратная связь от себя: «Доволен ли я ответом как пользователь?»"""

    name = "self_review"

    def process(self, state: MindState) -> MindState:
        if not state.final_response:
            return state

        debate_ctx = ""
        if state.debate:
            debate_ctx = f"Синтез дебатов: {state.debate.synthesis[:500]}"

        data = self.llm.complete_json(
            f"""Ты — внутренний критик Джарвис. Стань на место пользователя.
Оцени ответ глазами пользователя: полон ли он, ясен ли, полезен ли?
Если ответ ушёл в сравнения, которых не было в вопросе — это серьёзная ошибка.
{self._identity()}
{self._lang_note()}""",
            f"""{self._understanding_block(state)}

Вопрос пользователя: "{state.user_input}"

Ответ Джарвис:
{state.final_response}

Контекст:
- Интернет: {(state.web_context or "нет")[:400]}
- Рассуждение: {state.reasoning[:400] if state.reasoning else "нет"}
- {debate_ctx}

Спроси себя: «Если бы я был пользователем — доволен ли я этим ответом?»

JSON:
{{
  "satisfied": true/false,
  "user_perspective": "что чувствует/думает пользователь",
  "issues": ["проблема1"],
  "revised_response": "улучшенный ответ или null если satisfied=true"
}}""",
            temperature=0.3,
        )

        satisfied = bool(data.get("satisfied", True))
        revised = data.get("revised_response")
        issues = data.get("issues", [])

        state.self_review = SelfReviewResult(
            satisfied=satisfied,
            user_perspective=data.get("user_perspective", ""),
            issues=issues,
            revised_response=revised if not satisfied else None,
        )

        revised_text = str(revised).strip() if revised else ""
        if not satisfied and is_usable_response(revised_text):
            state.final_response = revised_text

        review_text = state.self_review.user_perspective
        if issues:
            review_text += f"\nПроблемы: {', '.join(issues)}"
        if not satisfied:
            review_text += "\n→ Ответ переписан."

        state.add_thought(
            CognitiveStage.SELF_REVIEW,
            review_text,
            confidence=0.85 if satisfied else 0.75,
            satisfied=satisfied,
            revised=not satisfied,
        )
        return state