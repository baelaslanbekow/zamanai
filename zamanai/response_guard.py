from __future__ import annotations

from zamanai.types import MindState


def _pick_text(value: str | None, limit: int = 4000) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "нет"):
        return ""
    return text[:limit]


def ensure_response(state: MindState) -> str:
    """Гарантирует непустой ответ — fallback по цепочке источников."""
    primary = _pick_text(state.final_response, 8000)
    if primary:
        return primary

    candidates: list[str | None] = []
    if state.self_review and state.self_review.revised_response:
        candidates.append(state.self_review.revised_response)
    if state.reflection and state.reflection.improved_response:
        candidates.append(state.reflection.improved_response)
    if state.debate:
        candidates.append(state.debate.synthesis)
    candidates.extend([
        state.reasoning,
        state.monologue,
        state.web_context,
    ])

    for candidate in candidates:
        text = _pick_text(candidate)
        if text:
            return text

    return (
        "Не удалось сформировать ответ — слишком много запросов или сбой API. "
        "Попробуйте ещё раз или переключите режим: /fast или /deep."
    )


def is_usable_response(text: str | None, min_len: int = 30) -> bool:
    cleaned = _pick_text(text, 10000)
    return len(cleaned) >= min_len