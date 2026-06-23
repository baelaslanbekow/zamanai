from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.thinking_depth import REASONING_STEPS, ThinkingDepth
from zamanai.types import CognitiveStage, MindState


class ReasoningModule(CognitiveModule):
    name = "reasoning"

    SYSTEM = """Ты — модуль рассуждения Джарвис. Логика и структура.
{identity}
{lang}"""

    def process(self, state: MindState) -> MindState:
        depth = ThinkingDepth(state.thinking_depth)
        steps_target = REASONING_STEPS.get(depth, 5)

        scenarios = ""
        if state.scenarios:
            scenarios = "\n".join(
                f"- {s.name}: {s.description} (вероятность {s.likelihood:.0%})"
                for s in state.scenarios
            )

        why_text = ""
        if state.why_chain:
            why_text = "\n".join(f"• {s.question} → {s.answer}" for s in state.why_chain)

        debate_text = ""
        if state.debate:
            debate_text = state.debate.synthesis

        if depth == ThinkingDepth.EXPERT:
            state.reasoning = self._expert_reasoning(
                state, scenarios, why_text, debate_text, steps_target,
            )
        elif depth == ThinkingDepth.DEEP:
            state.reasoning = self._deep_reasoning(
                state, scenarios, why_text, debate_text, steps_target,
            )
        else:
            state.reasoning = self._fast_reasoning(
                state, scenarios, why_text, debate_text,
            )

        state.add_thought(
            CognitiveStage.REASONING,
            f"[{DEPTH_LABEL(depth)} · {steps_target} шагов]\n{state.reasoning}",
            confidence=0.8 if depth != ThinkingDepth.FAST else 0.75,
        )
        return state

    def _fast_reasoning(self, state, scenarios, why_text, debate_text) -> str:
        return self.llm.complete(
            self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
            self._prompt(state, scenarios, why_text, debate_text, steps=5),
            temperature=self.config.temperature_analytical,
        )

    def _deep_reasoning(self, state, scenarios, why_text, debate_text, steps) -> str:
        return self.llm.complete(
            self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
            self._prompt(state, scenarios, why_text, debate_text, steps)
            + f"\n\nПроведи РОВНО {steps} пронумерованных шагов рассуждения (1. ... {steps}. ...).",
            temperature=self.config.temperature_analytical,
            max_tokens=3000,
        )

    def _expert_reasoning(self, state, scenarios, why_text, debate_text, steps) -> str:
        parts = []
        chunk = 17
        remaining = steps
        step_num = 1
        prior = ""

        while remaining > 0:
            batch = min(chunk, remaining)
            end_step = step_num + batch - 1
            prior_block = f"Предыдущие шаги:\n{prior}" if prior else ""
            expert_note = (
                f"\n\nЭКСПЕРТНЫЙ РЕЖИМ: шаги {step_num}-{end_step} из {steps}.\n"
                f"{prior_block}\n\n"
                f"Напиши шаги {step_num}-{end_step} пронумерованными. "
                "Каждый шаг — одно логическое действие."
            )
            batch_result = self.llm.complete(
                self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
                self._prompt(state, scenarios, why_text, debate_text, steps) + expert_note,
                temperature=self.config.temperature_analytical,
                max_tokens=2500,
            )
            parts.append(batch_result)
            prior = batch_result[-1500:]
            step_num += batch
            remaining -= batch

        return "\n\n".join(parts)

    def _prompt(self, state, scenarios, why_text, debate_text, steps: int) -> str:
        return f"""{self._understanding_block(state)}

Вопрос: "{state.user_input}"

Данные из интернета:
{state.web_context or "нет"}

Цепочка «почему»:
{why_text or "нет"}

Синтез дебатов:
{debate_text or "нет"}

Внутренний монолог:
{state.monologue}

Сценарии воображения:
{scenarios or "не генерировались"}

Цель: {steps} логических шагов к обоснованному выводу.
1. Что знаем точно?
2. Что предполагаем?
3. Какие варианты?
4. Лучший вывод?"""


def DEPTH_LABEL(depth: ThinkingDepth) -> str:
    return {
        ThinkingDepth.FAST: "⚡ Быстрый",
        ThinkingDepth.DEEP: "🔬 Глубокий",
        ThinkingDepth.EXPERT: "🎓 Экспертный",
    }.get(depth, "⚡")