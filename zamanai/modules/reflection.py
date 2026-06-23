from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.response_guard import is_usable_response
from zamanai.types import CognitiveStage, MindState, ReflectionResult


class ReflectionModule(CognitiveModule):
    name = "reflection"

    SYSTEM = """Ты — рефлексия Джарвис. Оцени и улучши ответ.
Ответ должен отвечать ТОЛЬКО на то, что спросил пользователь.
Если в ответе есть сравнения, которых не было в вопросе — это ошибка, убери их.
НЕ задавай встречных вопросов «что обсудить?» — дай конкретный полезный ответ по присланному тексту.
{identity}
Убери плейсхолдеры [имя], упоминания внутренних модулей AGI.
{lang}"""

    def process(self, state: MindState) -> MindState:
        draft = self._draft_response(state)

        if not is_usable_response(draft):
            draft = self._fallback_draft(state)

        try:
            data = self.llm.complete_json(
                self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
                f"""{self._understanding_block(state)}

Вопрос: "{state.user_input[:2000]}"

Черновик ответа:
{draft[:3000]}

Синтез дебатов: {(state.debate.synthesis if state.debate else "нет")[:400]}
Рассуждение: {state.reasoning[:600]}
Сомнения: {state.doubt[:400]}
Уверенность: {state.confidence:.0%}

Оцени и при необходимости улучши. JSON:
{{
  "quality_score": 0.0-1.0,
  "should_revise": true/false,
  "issues": ["проблема1"],
  "improved_response": "улучшенный ответ или null",
  "reasoning": "почему так оценил"
}}""",
                temperature=self.config.temperature_analytical,
            )
        except Exception:
            data = {
                "quality_score": 0.6,
                "should_revise": False,
                "issues": ["рефлексия пропущена"],
                "improved_response": None,
                "reasoning": "Использован черновик без доработки.",
            }

        improved = data.get("improved_response")
        improved_text = str(improved).strip() if improved else ""

        state.reflection = ReflectionResult(
            quality_score=float(data.get("quality_score", 0.7)),
            should_revise=bool(data.get("should_revise", False)),
            issues=data.get("issues", []),
            improved_response=improved_text or None,
            reasoning=data.get("reasoning", ""),
        )

        if state.reflection.should_revise and is_usable_response(improved_text):
            state.final_response = improved_text
        else:
            state.final_response = draft

        state.add_thought(
            CognitiveStage.REFLECTION,
            state.reflection.reasoning,
            confidence=state.reflection.quality_score,
            revised=state.reflection.should_revise,
        )
        return state

    def _context_block(self, state: MindState) -> str:
        u = state.understanding
        pitch_note = ""
        if u and u.question_type == "analyze_pitch":
            pitch_note = """
ФОРМАТ ОТВЕТА (бизнес-идея):
1. Суть идеи в 2-3 предложениях
2. Сильные стороны и уникальность
3. Риски и слабые места
4. Как начать: конкретные шаги на 30/60/90 дней
5. Метрики успеха и MVP
Будь детальным и практичным."""

        return f"""{self._understanding_block(state)}
{pitch_note}

Вопрос: "{state.user_input[:2500]}"

Факты из интернета: {(state.web_context or "нет")[:1200]}
Синтез дебатов: {(state.debate.synthesis if state.debate else "нет")[:600]}
Цепочка почему: {(" | ".join(s.answer[:80] for s in state.why_chain) if state.why_chain else "нет")}
Мои мысли: {(state.monologue or "нет")[:800]}
Логика: {(state.reasoning or "нет")[:1200]}
Сомнения: {(state.doubt or "нет")[:400]}
Уверенность: {state.confidence:.0%}"""

    def _draft_response(self, state: MindState) -> str:
        scenarios = ""
        if state.scenarios:
            scenarios = "\n".join(f"- {s.name}: {s.description}" for s in state.scenarios)

        name = self.config.assistant_name
        depth = state.thinking_depth
        max_tokens = 6000 if depth in ("deep", "expert") else 4096

        for attempt in range(2):
            try:
                text = self.llm.complete(
                    f"""Ты — {name}, персональный AGI-ассистент.
Формируешь ответ пользователю. Будь полезен, ясен, человечен.
Если прислали описание идеи/продукта — дай детальный разбор и план действий, не переспрашивай.
{self._identity()}
Никогда не упоминай модули AGI, ZamanMind, плейсхолдеры.
{self._lang_note()}""",
                    f"""{self._context_block(state)}

Сценарии: {scenarios or "нет"}

Напиши лучший полный ответ пользователю.""",
                    temperature=self.config.temperature_balanced,
                    max_tokens=max_tokens,
                )
                if is_usable_response(text):
                    return text.strip()
            except Exception:
                pass

        return ""

    def _fallback_draft(self, state: MindState) -> str:
        name = self.config.assistant_name
        summary = (state.debate.synthesis if state.debate else "") or (state.reasoning or "")[:2000]
        if not summary.strip():
            summary = state.monologue or state.web_context or "Нет данных для ответа."

        try:
            text = self.llm.complete(
                f"""Ты — {name}. Сформируй ответ пользователю кратко, но по делу. {self._lang_note()}""",
                f"""{self._understanding_block(state)}

Вопрос: "{state.user_input[:1500]}"

Ключевые выводы:
{summary[:2500]}

Дай связный ответ пользователю.""",
                temperature=0.5,
                max_tokens=3000,
            )
            if is_usable_response(text):
                return text.strip()
        except Exception:
            pass

        return summary.strip()[:3500] or "Не удалось сформировать ответ."