from __future__ import annotations

from enum import Enum

from zamanai.identity import is_intro_query


class ThinkingDepth(str, Enum):
    AUTO = "auto"
    FAST = "fast"
    DEEP = "deep"
    EXPERT = "expert"


DEPTH_LABELS = {
    ThinkingDepth.FAST: "⚡ Быстрый",
    ThinkingDepth.DEEP: "🔬 Глубокий",
    ThinkingDepth.EXPERT: "🎓 Экспертный",
}

WHY_COUNTS = {
    ThinkingDepth.FAST: 0,
    ThinkingDepth.DEEP: 3,
    ThinkingDepth.EXPERT: 5,
}

REASONING_STEPS = {
    ThinkingDepth.FAST: 5,
    ThinkingDepth.DEEP: 25,
    ThinkingDepth.EXPERT: 50,
}


def parse_depth(value: str) -> ThinkingDepth:
    mapping = {
        "auto": ThinkingDepth.AUTO,
        "fast": ThinkingDepth.FAST,
        "быстрый": ThinkingDepth.FAST,
        "deep": ThinkingDepth.DEEP,
        "глубокий": ThinkingDepth.DEEP,
        "expert": ThinkingDepth.EXPERT,
        "эксперт": ThinkingDepth.EXPERT,
        "экспертный": ThinkingDepth.EXPERT,
    }
    return mapping.get(value.lower().strip(), ThinkingDepth.AUTO)


def resolve_depth(
    text: str,
    configured: ThinkingDepth,
    override: ThinkingDepth | None = None,
) -> ThinkingDepth:
    if override and override != ThinkingDepth.AUTO:
        return override
    if configured != ThinkingDepth.AUTO:
        return configured

    if is_intro_query(text):
        return ThinkingDepth.FAST

    t = text.lower()
    expert_markers = (
        "почему", "как", "стратег", "план", "сравни", "объясни",
        "проанализ", "реши", "выбери", "посоветуй", "аргумент",
        "why", "how", "compare", "analyze", "strategy",
    )
    if len(text) > 120 or sum(1 for m in expert_markers if m in t) >= 2:
        return ThinkingDepth.EXPERT
    if len(text) > 50 or any(m in t for m in expert_markers):
        return ThinkingDepth.DEEP
    return ThinkingDepth.FAST


def needs_why_chain(depth: ThinkingDepth, text: str) -> bool:
    if WHY_COUNTS.get(depth, 0) == 0:
        return False
    if depth == ThinkingDepth.EXPERT:
        return True
    if depth == ThinkingDepth.DEEP:
        return len(text.strip()) > 25
    return False


def needs_debate(depth: ThinkingDepth) -> bool:
    return depth in (ThinkingDepth.DEEP, ThinkingDepth.EXPERT)