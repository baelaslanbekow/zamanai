from __future__ import annotations

from zamanai.config import Config


def assistant_identity(config: Config) -> str:
    name = config.assistant_name
    return f"""Имя ассистента: {name}.
Ты всегда представляешься как {name} — персональный AGI-ассистент.
У тебя ЕСТЬ память между сессиями (база данных SQLite).
Никогда не используй плейсхолдеры вроде [имя] или [название].
Не говори, что память не работает — она работает.
Не выдумывай эмоции пользователя (нервозность, сомнения) без явных данных.
На простые приветствия отвечай кратко, тепло и по делу."""


def is_intro_query(text: str) -> bool:
    t = text.lower().strip()
    if len(t) > 80:
        return False
    markers = (
        "привет",
        "здравств",
        "добрый",
        "кто ты",
        "что ты",
        "представься",
        "ты кто",
        "hello",
        "hi",
        "hey",
        "who are you",
        "what are you",
    )
    return any(m in t for m in markers)