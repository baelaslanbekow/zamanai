from __future__ import annotations

from zamanai.modules.base import CognitiveModule
from zamanai.types import CognitiveStage, MindState, QuestionUnderstanding


class UnderstandingModule(CognitiveModule):
    """ПЕРВЫЙ этап — точно понять вопрос пользователя, прежде чем что-либо делать."""

    name = "understanding"

    SYSTEM = """Ты — модуль ПОНИМАНИЯ вопроса в AGI Джарвис.
Твоя единственная задача: ТОЧНО понять, что спрашивает пользователь.

КРИТИЧЕСКИ ВАЖНО:
- Читай вопрос БУКВАЛЬНО. Не добавляй то, чего нет.
- Если пользователь спрашивает «почему BMW лучше» — он НЕ спрашивает про Mercedes, Audi и сравнения.
- Если нет слова «сравни» / «или» / «лучше чем» — это НЕ вопрос сравнения.
- Если пользователь прислал описание продукта/идеи без явного вопроса — он хочет анализ, оценку или резюме, а НЕ «что обсудить?».
- Определи, что пользователь ХОЧЕТ и что он НЕ спрашивал.
{identity}
{lang}"""

    PROMPT = """Сообщение пользователя (читай ДОСЛОВНО):
"{user_input}"

Контекст из памяти:
{memories}

Проанализируй. JSON:
{{
  "exact_meaning": "что именно спрашивает пользователь своими словами",
  "core_topic": "главная тема одной фразой",
  "question_type": "explain_why|how|what|compare|opinion|analyze_pitch|other",
  "user_wants": ["что хочет получить 1", "что хочет 2"],
  "user_did_not_ask": ["чего НЕ спрашивал — например сравнение с Mercedes"],
  "avoid_assumptions": ["чего НЕЛЬЗЯ добавлять в ответ"],
  "search_queries": ["точный поисковый запрос 1", "запрос 2", "запрос 3"],
  "answer_focus": "на чём должен быть сфокусирован ответ",
  "is_comparison_question": false
}}

Пример: описание стартапа с Value Proposition / Monetization без вопроса →
- user_wants: ["оценить идею", "дать анализ продукта", "резюмировать сильные стороны"]
- question_type: analyze_pitch
- answer_focus: анализ идеи, монетизации и целевой аудитории

Пример: «почему машины BMW лучше» →
- user_wants: ["узнать преимущества BMW", "аргументы почему BMW хороши"]
- user_did_not_ask: ["сравнение с Mercedes", "сравнение с другими марками"]
- is_comparison_question: false
- search_queries: ["преимущества BMW", "почему BMW хороший автомобиль", "плюсы BMW"]"""

    def process(self, state: MindState) -> MindState:
        memories = "\n".join(f"- {m}" for m in state.associations[:4]) or "нет"

        try:
            data = self._analyze(state, memories)
        except Exception:
            data = self._fallback_analysis(state)

        return self._finalize(state, data)

    def _analyze(self, state: MindState, memories: str) -> dict:
        return self.llm.complete_json(
            self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
            self.PROMPT.format(user_input=state.user_input, memories=memories),
            temperature=0.1,
        )

    def _fallback_analysis(self, state: MindState) -> dict:
        text = state.user_input.strip()
        lower = text.lower()
        is_compare = any(w in lower for w in ("сравни", " или ", " vs ", " versus ", "лучше чем"))
        is_pitch = any(
            m in lower
            for m in (
                "value proposition", "monetization", "target audience",
                "бизнес", "продукт", "стартап", "tam", "монетизац",
            )
        )
        q_type = "compare" if is_compare else "explain_why" if "почему" in lower else "analyze_pitch" if is_pitch else "other"
        wants = (
            ["оценить идею", "проанализировать продукт", "дать резюме"]
            if is_pitch
            else [f"ответ на: {text}"]
        )
        return {
            "exact_meaning": text,
            "core_topic": text[:120],
            "question_type": q_type,
            "user_wants": wants,
            "user_did_not_ask": [] if is_compare else ["сравнение с другими марками и брендами"],
            "avoid_assumptions": [] if is_compare else ["сравнения с Mercedes, Audi и другими без запроса"],
            "search_queries": [text],
            "answer_focus": text,
            "is_comparison_question": is_compare,
        }

    def _finalize(self, state: MindState, data: dict) -> MindState:
        state.understanding = QuestionUnderstanding(
            exact_meaning=data.get("exact_meaning", state.user_input),
            core_topic=data.get("core_topic", state.user_input),
            question_type=data.get("question_type", "other"),
            user_wants=data.get("user_wants", []),
            user_did_not_ask=data.get("user_did_not_ask", []),
            avoid_assumptions=data.get("avoid_assumptions", []),
            search_queries=data.get("search_queries", [state.user_input]),
            answer_focus=data.get("answer_focus", ""),
            is_comparison_question=bool(data.get("is_comparison_question", False)),
        )

        thought = (
            f"📌 Точный смысл: {state.understanding.exact_meaning}\n"
            f"🎯 Тема: {state.understanding.core_topic}\n"
            f"✅ Хочет: {', '.join(state.understanding.user_wants)}\n"
            f"🚫 НЕ спрашивал: {', '.join(state.understanding.user_did_not_ask) or '—'}\n"
            f"💡 Фокус ответа: {state.understanding.answer_focus}"
        )
        state.add_thought(CognitiveStage.UNDERSTANDING, thought, confidence=0.95)
        return state