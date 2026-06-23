import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    api_key: str
    model: str
    show_thoughts: bool
    memory_path: Path
    language: str
    assistant_name: str = "Джарвис"
    max_working_memory: int = 7
    imagination_enabled: bool = True
    temperature_creative: float = 0.9
    temperature_analytical: float = 0.3
    temperature_balanced: float = 0.6
    web_search_enabled: bool = True
    web_search_max_sites: int = 25
    web_search_fetch_pages: int = 15
    thinking_depth: str = "auto"

    @classmethod
    def from_env(cls) -> "Config":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                f"GROQ_API_KEY не найден. Добавьте ключ в {PROJECT_ROOT / '.env'}"
            )

        raw_memory = os.getenv("ZAMAN_MEMORY_PATH", "data/memory.db")
        memory_path = Path(raw_memory)
        if not memory_path.is_absolute():
            memory_path = PROJECT_ROOT / memory_path
        memory_path.parent.mkdir(parents=True, exist_ok=True)

        return cls(
            api_key=api_key,
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            show_thoughts=os.getenv("ZAMAN_SHOW_THOUGHTS", "false").lower() == "true",
            memory_path=memory_path,
            language=os.getenv("ZAMAN_LANGUAGE", "ru"),
            assistant_name=os.getenv("ZAMAN_ASSISTANT_NAME", "Джарвис"),
            web_search_enabled=os.getenv("ZAMAN_WEB_SEARCH", "true").lower() == "true",
            web_search_max_sites=int(os.getenv("ZAMAN_WEB_MAX_SITES", "25")),
            web_search_fetch_pages=int(os.getenv("ZAMAN_WEB_FETCH_PAGES", "15")),
            thinking_depth=os.getenv("ZAMAN_THINKING_DEPTH", "auto"),
        )