from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from zamanai.modules.base import CognitiveModule
from zamanai.types import CognitiveStage, DebateResult, MindState


class DebateModule(CognitiveModule):
    """Внутренние дебаты: Оптимист, Скептик, Прагматик → Синтезатор."""

    name = "debate"

    def process(self, state: MindState) -> MindState:
        context = self._build_context(state)

        with ThreadPoolExecutor(max_workers=3) as pool:
            opt_f = pool.submit(self._optimist, state.user_input, context)
            ske_f = pool.submit(self._skeptic, state.user_input, context)
            pra_f = pool.submit(self._pragmatist, state.user_input, context)
            optimist = opt_f.result()
            skeptic = ske_f.result()
            pragmatist = pra_f.result()

        synthesis = self._synthesizer(state.user_input, optimist, skeptic, pragmatist, context)

        state.debate = DebateResult(
            optimist=optimist,
            skeptic=skeptic,
            pragmatist=pragmatist,
            synthesis=synthesis,
        )

        debate_text = (
            f"🟢 ОПТИМИСТ:\n{optimist}\n\n"
            f"🔴 СКЕПТИК:\n{skeptic}\n\n"
            f"🔵 ПРАГМАТИК:\n{pragmatist}\n\n"
            f"⚖️ СИНТЕЗАТОР:\n{synthesis}"
        )
        state.add_thought(CognitiveStage.DEBATE, debate_text, confidence=0.82)
        return state

    def _build_context(self, state: MindState) -> str:
        parts = [self._understanding_block(state)]
        if state.web_context:
            parts.append(f"Интернет: {state.web_context[:800]}")
        if state.why_chain:
            parts.append("Почему-цепочка: " + " | ".join(s.answer[:100] for s in state.why_chain))
        if state.monologue:
            parts.append(f"Монолог: {state.monologue[:400]}")
        if state.perception:
            parts.append(f"Восприятие: {state.perception.raw_analysis[:300]}")
        return "\n".join(parts) or "Контекст минимальный."

    def _optimist(self, question: str, context: str) -> str:
        return self.llm.complete(
            f"""Ты — ОПТИМИСТ в голове Джарвис. Видишь возможности, потенциал, лучший сценарий.
Отвечай строго в рамках того, что спросил пользователь. Не сравнивай с другими, если не просили.
{self._lang_note()}""",
            f"Вопрос: {question}\nКонтекст:\n{context}\n\nЧто хорошего и какие возможности? 3-5 предложений.",
            temperature=0.7,
        )

    def _skeptic(self, question: str, context: str) -> str:
        return self.llm.complete(
            f"""Ты — СКЕПТИК в голове Джарвис. Ищешь дыры, риски, слабые места, ошибки.
Не критикуй сравнения с другими марками, если пользователь их не просил.
{self._lang_note()}""",
            f"Вопрос: {question}\nКонтекст:\n{context}\n\nЧто может пойти не так? Где слабые аргументы? 3-5 предложений.",
            temperature=0.4,
        )

    def _pragmatist(self, question: str, context: str) -> str:
        return self.llm.complete(
            f"""Ты — ПРАГМАТИК в голове Джарвис. Что реально сделать прямо сейчас? Конкретные шаги.
{self._lang_note()}""",
            f"Вопрос: {question}\nКонтекст:\n{context}\n\nПрактичный план действий. 3-5 предложений.",
            temperature=0.5,
        )

    def _synthesizer(
        self, question: str, optimist: str, skeptic: str, pragmatist: str, context: str,
    ) -> str:
        return self.llm.complete(
            f"""Ты — СИНТЕЗАТОР в голове Джарвис. Слушаешь Оптимиста, Скептика и Прагматика.
Собери сбалансированный вывод — лучшее из всех позиций.
Ответ должен отвечать ТОЛЬКО на вопрос пользователя, без лишних сравнений.
{self._identity()}
{self._lang_note()}""",
            f"""Вопрос: {question}

🟢 Оптимист: {optimist}
🔴 Скептик: {skeptic}
🔵 Прагматик: {pragmatist}

Контекст: {context[:600]}

Синтез: сбалансированный вывод для ответа пользователю. 4-6 предложений.""",
            temperature=0.5,
        )