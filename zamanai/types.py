from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CognitiveStage(str, Enum):
    UNDERSTANDING = "understanding"
    WEB_SEARCH = "web_search"
    WHY_CHAIN = "why_chain"
    PERCEPTION = "perception"
    ASSOCIATION = "association"
    MONOLOGUE = "monologue"
    IMAGINATION = "imagination"
    REASONING = "reasoning"
    DOUBT = "doubt"
    REFLECTION = "reflection"
    DEBATE = "debate"
    SELF_REVIEW = "self_review"
    DECISION = "decision"
    MEMORY = "memory"


class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    EMOTIONAL = "emotional"


@dataclass
class ThoughtStep:
    stage: CognitiveStage
    content: str
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MemoryRecord:
    id: int | None
    memory_type: MemoryType
    content: str
    importance: float
    associations: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class WebSource:
    title: str
    url: str
    snippet: str
    fetched: bool = False


@dataclass
class QuestionUnderstanding:
    exact_meaning: str
    core_topic: str
    question_type: str
    user_wants: list[str]
    user_did_not_ask: list[str]
    avoid_assumptions: list[str]
    search_queries: list[str]
    answer_focus: str
    is_comparison_question: bool = False


@dataclass
class PerceptionResult:
    intent: str
    topics: list[str]
    emotional_tone: str
    urgency: str
    raw_analysis: str


@dataclass
class ImaginationScenario:
    name: str
    description: str
    pros: list[str]
    cons: list[str]
    likelihood: float


@dataclass
class WhyStep:
    question: str
    answer: str


@dataclass
class DebateResult:
    optimist: str
    skeptic: str
    pragmatist: str
    synthesis: str


@dataclass
class SelfReviewResult:
    satisfied: bool
    user_perspective: str
    issues: list[str]
    revised_response: str | None


@dataclass
class ReflectionResult:
    quality_score: float
    should_revise: bool
    issues: list[str]
    improved_response: str | None
    reasoning: str


@dataclass
class MindState:
    user_input: str
    thinking_depth: str = "fast"
    understanding: QuestionUnderstanding | None = None
    web_context: str = ""
    web_sources: list[WebSource] = field(default_factory=list)
    why_chain: list[WhyStep] = field(default_factory=list)
    debate: DebateResult | None = None
    self_review: SelfReviewResult | None = None
    perception: PerceptionResult | None = None
    associations: list[str] = field(default_factory=list)
    monologue: str = ""
    scenarios: list[ImaginationScenario] = field(default_factory=list)
    reasoning: str = ""
    doubt: str = ""
    reflection: ReflectionResult | None = None
    final_response: str = ""
    thought_trace: list[ThoughtStep] = field(default_factory=list)
    confidence: float = 0.5

    def add_thought(
        self,
        stage: CognitiveStage,
        content: str,
        confidence: float = 0.5,
        **metadata: Any,
    ) -> None:
        self.thought_trace.append(
            ThoughtStep(
                stage=stage,
                content=content,
                confidence=confidence,
                metadata=metadata,
            )
        )