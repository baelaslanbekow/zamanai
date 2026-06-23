from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from zamanai.config import Config


class GroqClient:
    """Обёртка над Groq API (OpenAI-совместимый endpoint)."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = OpenAI(
            api_key=config.api_key,
            base_url="https://api.groq.com/openai/v1",
            max_retries=2,
        )

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        temp = temperature if temperature is not None else self.config.temperature_balanced

        for attempt in range(3):
            try:
                response = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                return content.strip() if content else ""
            except RateLimitError:
                if attempt < 2:
                    time.sleep(3 * (2 ** attempt))
                    continue
                raise
            except (APIConnectionError, APIStatusError):
                if attempt < 2:
                    time.sleep(1)
                    continue
                raise

        return ""

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        raw = self.complete(
            system + "\n\nОтвечай ТОЛЬКО валидным JSON без markdown-обёртки.",
            user,
            temperature=temperature,
        )
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Groq вернул невалидный JSON: {text[:200]}...")