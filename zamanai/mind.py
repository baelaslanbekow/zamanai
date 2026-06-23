from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from zamanai.config import Config
from zamanai.consciousness import GlobalWorkspace
from zamanai.groq_client import GroqClient
from zamanai.identity import assistant_identity, is_intro_query
from zamanai.modules.association import AssociationModule
from zamanai.modules.debate import DebateModule
from zamanai.modules.understanding import UnderstandingModule
from zamanai.modules.doubt import DoubtModule
from zamanai.modules.drives import DrivesSystem
from zamanai.modules.imagination import ImaginationModule
from zamanai.modules.memory import MemorySystem
from zamanai.modules.monologue import MonologueModule
from zamanai.modules.perception import PerceptionModule
from zamanai.modules.reasoning import ReasoningModule
from zamanai.modules.reflection import ReflectionModule
from zamanai.modules.self_review import SelfReviewModule
from zamanai.modules.web_search import WebSearchModule
from zamanai.modules.why_chain import WhyChainModule
from zamanai.response_guard import ensure_response
from zamanai.thinking_depth import (
    DEPTH_LABELS,
    ThinkingDepth,
    needs_debate,
    needs_why_chain,
    parse_depth,
    resolve_depth,
)
from zamanai.types import CognitiveStage, MindState

StageCallback = Callable[[str], None]

STAGE_ENUM = {
    "understanding": CognitiveStage.UNDERSTANDING,
    "web_search": CognitiveStage.WEB_SEARCH,
    "why_chain": CognitiveStage.WHY_CHAIN,
    "perception": CognitiveStage.PERCEPTION,
    "association": CognitiveStage.ASSOCIATION,
    "monologue": CognitiveStage.MONOLOGUE,
    "debate": CognitiveStage.DEBATE,
    "imagination": CognitiveStage.IMAGINATION,
    "reasoning": CognitiveStage.REASONING,
    "doubt": CognitiveStage.DOUBT,
    "reflection": CognitiveStage.REFLECTION,
    "self_review": CognitiveStage.SELF_REVIEW,
}

STAGE_NAMES = {
    "understanding": "🎯 Понимание вопроса",
    "web_search": "🌐 Поиск в интернете",
    "why_chain": "🔗 Цепочка «почему»",
    "perception": "👁  Восприятие",
    "association": "🔗 Ассоциации",
    "monologue": "💭 Монолог",
    "debate": "⚖️  Дебаты в голове",
    "imagination": "🌌 Воображение",
    "reasoning": "🧠 Рассуждение",
    "doubt": "❓ Сомнение",
    "reflection": "🪞 Рефлексия",
    "self_review": "🔄 Самопроверка",
    "memory": "💾 Память",
}


@dataclass
class ThinkResult:
    response: str
    state: MindState
    thoughts: str
    thoughts_list: list[dict]
    depth: ThinkingDepth

    @property
    def confidence(self) -> float:
        return self.state.confidence


class Jarvis:
    """Джарвис — AGI с дебатами, глубиной мышления и самопроверкой."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.from_env()
        self.llm = GroqClient(self.config)
        self.memory = MemorySystem(self.config, self.llm)
        self.drives = DrivesSystem(self.config)
        self.consciousness = GlobalWorkspace(self.drives)
        self.depth_override: ThinkingDepth | None = None

        self._modules = {
            "understanding": UnderstandingModule(self.llm, self.config),
            "web_search": WebSearchModule(self.llm, self.config),
            "why_chain": WhyChainModule(self.llm, self.config),
            "perception": PerceptionModule(self.llm, self.config),
            "association": AssociationModule(self.llm, self.config, self.memory),
            "monologue": MonologueModule(self.llm, self.config),
            "debate": DebateModule(self.llm, self.config),
            "imagination": ImaginationModule(self.llm, self.config),
            "reasoning": ReasoningModule(self.llm, self.config),
            "doubt": DoubtModule(self.llm, self.config),
            "reflection": ReflectionModule(self.llm, self.config),
            "self_review": SelfReviewModule(self.llm, self.config),
        }

    def set_depth(self, depth: ThinkingDepth) -> None:
        self.depth_override = depth

    def think(
        self,
        user_input: str,
        on_stage: StageCallback | None = None,
    ) -> ThinkResult:
        state = MindState(user_input=user_input.strip())

        recalled = self.memory.recall(user_input, limit=5)
        state.associations = [m.content for m in recalled]

        if is_intro_query(user_input):
            if on_stage:
                on_stage("⚡ быстрый ответ")
            return self._quick_intro(state)

        configured = parse_depth(self.config.thinking_depth)
        depth = resolve_depth(user_input, configured, self.depth_override)
        state.thinking_depth = depth.value

        if on_stage:
            on_stage(f"Режим: {DEPTH_LABELS.get(depth, depth.value)}")

        state = self._run("understanding", state, on_stage)
        state = self._run("web_search", state, on_stage)
        state = self._run("perception", state, on_stage)
        state = self._run("association", state, on_stage)
        state = self._run("monologue", state, on_stage)

        if needs_why_chain(depth, user_input):
            state = self._run("why_chain", state, on_stage)

        if needs_debate(depth):
            state = self._run("debate", state, on_stage)

        pipeline = self.consciousness.plan_pipeline(state)
        if "imagination" in pipeline:
            state = self._run("imagination", state, on_stage)

        state = self._run("reasoning", state, on_stage)
        state = self._run("doubt", state, on_stage)
        state = self._run("reflection", state, on_stage)
        state = self._run("self_review", state, on_stage)

        state.final_response = ensure_response(state)

        state.add_thought(
            CognitiveStage.DECISION,
            state.final_response,
            confidence=state.confidence,
        )

        if on_stage:
            on_stage(STAGE_NAMES["memory"])
        try:
            self.memory.consolidate(state)
        except Exception:
            state.add_thought(CognitiveStage.MEMORY, "Память: не удалось сохранить.", 0.3)

        return ThinkResult(
            response=state.final_response,
            state=state,
            thoughts=self.consciousness.format_thoughts(state),
            thoughts_list=self.consciousness.thoughts_as_list(state),
            depth=depth,
        )

    def _run(
        self,
        key: str,
        state: MindState,
        on_stage: StageCallback | None,
    ) -> MindState:
        if on_stage:
            on_stage(STAGE_NAMES.get(key, key))
        try:
            return self._modules[key].process(state)
        except Exception as exc:
            stage = STAGE_ENUM.get(key, CognitiveStage.PERCEPTION)
            state.add_thought(stage, f"Этап {key} пропущен: {exc}", confidence=0.3)
            return state

    def _quick_intro(self, state: MindState) -> ThinkResult:
        name = self.config.assistant_name
        memories = "\n".join(f"- {m}" for m in state.associations[:4]) or "Пока мало воспоминаний."

        response = self.llm.complete(
            f"""Ты — {name}, персональный AGI-ассистент.
{assistant_identity(self.config)}
Говори от первого лица. 2-4 предложения максимум.
{self._lang()}""",
            f"""Пользователь: "{state.user_input}"
Память: {memories}
Поприветствуй и представься как {name}.""",
            temperature=0.4,
        )

        state.final_response = response
        state.confidence = 0.9
        state.add_thought(CognitiveStage.DECISION, response, confidence=0.9, fast_path=True)
        try:
            self.memory.consolidate(state)
        except Exception:
            pass

        return ThinkResult(
            response=response,
            state=state,
            thoughts=self.consciousness.format_thoughts(state),
            thoughts_list=self.consciousness.thoughts_as_list(state),
            depth=ThinkingDepth.FAST,
        )

    def _lang(self) -> str:
        return "Отвечай на русском." if self.config.language == "ru" else "Respond in English."

    def get_memory_stats(self) -> dict:
        episodes = self.memory.get_recent_episodes(10)
        return {
            "episodes": len(episodes),
            "topics": [e["user_input"][:60] for e in episodes],
        }


ZamanMind = Jarvis