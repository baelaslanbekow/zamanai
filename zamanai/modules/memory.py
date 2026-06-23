from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from zamanai.config import Config
from zamanai.groq_client import GroqClient
from zamanai.types import CognitiveStage, MemoryRecord, MemoryType, MindState


class MemorySystem:
    """Эпизодическая, семантическая и эмоциональная память."""

    def __init__(self, config: Config, llm: GroqClient) -> None:
        self.config = config
        self.llm = llm
        self.db_path = config.memory_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL DEFAULT 0.5,
                    associations TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_input TEXT NOT NULL,
                    response TEXT NOT NULL,
                    thought_summary TEXT,
                    created_at TEXT NOT NULL
                )
            """)

    def recall(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC, id DESC LIMIT 50"
            ).fetchall()

        if not rows:
            return []

        keywords = set(query.lower().split())
        scored: list[tuple[float, MemoryRecord]] = []

        for row in rows:
            content_lower = row["content"].lower()
            score = sum(1 for kw in keywords if kw in content_lower and len(kw) > 2)
            score += row["importance"]
            record = MemoryRecord(
                id=row["id"],
                memory_type=MemoryType(row["memory_type"]),
                content=row["content"],
                importance=row["importance"],
                associations=json.loads(row["associations"] or "[]"),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit] if _ > 0] or [r for _, r in scored[:limit]]

    def consolidate(self, state: MindState) -> None:
        """Запоминает эпизод и извлекает долгосрочные факты через LLM."""
        now = datetime.now(timezone.utc).isoformat()
        thought_summary = " | ".join(
            t.content[:120] for t in state.thought_trace[:6]
        )

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO episodes (user_input, response, thought_summary, created_at)
                   VALUES (?, ?, ?, ?)""",
                (state.user_input, state.final_response, thought_summary, now),
            )

        data = self.llm.complete_json(
            f"""Ты — память Джарвис ({self.config.assistant_name}).
Из диалога извлеки что стоит запомнить: факты о пользователе, важные выводы.
{"Отвечай на русском." if self.config.language == "ru" else "Respond in English."}""",
            f"""Пользователь: {state.user_input}
Ответ AGI: {state.final_response}
Контекст мыслей: {thought_summary}

JSON:
{{
  "episodic": "краткое описание эпизода",
  "semantic_facts": ["факт1", "факт2"],
  "emotional_notes": ["эмоциональная заметка"],
  "importance": 0.0-1.0
}}""",
            temperature=0.3,
        )

        importance = float(data.get("importance", 0.5))
        episodic = data.get("episodic", "")
        if episodic:
            self._store(MemoryType.EPISODIC, episodic, importance)

        for fact in data.get("semantic_facts", []):
            if fact:
                self._store(MemoryType.SEMANTIC, fact, min(importance + 0.1, 1.0))

        for note in data.get("emotional_notes", []):
            if note:
                self._store(MemoryType.EMOTIONAL, note, importance)

        state.add_thought(
            CognitiveStage.MEMORY,
            f"Запомнено: {episodic or 'эпизод сохранён'}",
            confidence=importance,
        )

    def _store(
        self,
        memory_type: MemoryType,
        content: str,
        importance: float,
        associations: list[str] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO memories (memory_type, content, importance, associations, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    memory_type.value,
                    content,
                    importance,
                    json.dumps(associations or [], ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_recent_episodes(self, limit: int = 5) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_input, response, created_at FROM episodes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]