from __future__ import annotations

import json
import queue
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from zamanai.config import Config
from zamanai.mind import Jarvis
from zamanai.simple_chat import SimpleChat
from zamanai.thinking_depth import DEPTH_LABELS, ThinkingDepth

WEB_ROOT = Path(__file__).resolve().parent / "web"
SITE_VERSION = "zamanai-ios27-v3"

AGI_POLISH_SYSTEM = """Ты редактор ответов AGI-ассистента.
Перепиши текст для пользователя на {lang}:
- чётко и строго по делу
- подробно, но без воды и повторов
- вежливо, с уважением
- структурированно: абзацы, списки, заголовки где уместно
Сохрани все факты, цифры и смысл. Не добавляй выдуманных данных."""

config: Config | None = None
jarvis: Jarvis | None = None
simple_chat: SimpleChat | None = None


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    model: Literal["llm", "agi"] = "llm"
    history: list[HistoryItem] = Field(default_factory=list)
    show_thoughts: bool = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    global config, jarvis, simple_chat
    config = Config.from_env()
    jarvis = Jarvis(config)
    simple_chat = SimpleChat(config)
    yield


app = FastAPI(title="ZamanAI", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(NoCacheMiddleware)


def _require_ready() -> tuple[Jarvis, SimpleChat, Config]:
    if not jarvis or not simple_chat or not config:
        raise HTTPException(503, "Сервер ещё запускается")
    return jarvis, simple_chat, config


def _agi_polish(text: str) -> str:
    if not jarvis or not text.strip():
        return text
    lang = "русском" if config and config.language == "ru" else "том же языке, что вопрос"
    polished = jarvis.llm.complete(
        AGI_POLISH_SYSTEM.format(lang=lang),
        text.strip(),
        temperature=0.35,
        max_tokens=6000,
    )
    return polished.strip() or text


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _agi_result(message: str, on_stage=None) -> dict:
    jarvis.set_depth(ThinkingDepth.EXPERT)
    result = jarvis.think(message, on_stage=on_stage)
    return {
        "model": "agi",
        "response": _agi_polish(result.response),
        "confidence": round(result.confidence, 2),
        "depth": DEPTH_LABELS.get(result.depth, result.depth.value),
        "thoughts": result.thoughts,
        "stages": [t.get("stage", "") for t in result.thoughts_list],
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html", headers={"X-ZamanAI-Version": SITE_VERSION})


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "site": SITE_VERSION,
        "assistant": config.assistant_name if config else "ZamanAI",
        "model": config.model if config else "",
    }


@app.get("/api/memory")
async def memory_stats() -> dict:
    _require_ready()
    return jarvis.get_memory_stats()


@app.post("/api/chat")
async def chat(body: ChatRequest) -> dict:
    _, chat_llm, _ = _require_ready()
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "Пустое сообщение")
    history = [item.model_dump() for item in body.history]
    if body.model == "llm":
        return {
            "model": "llm",
            "response": chat_llm.chat(message, history),
            "confidence": None,
            "depth": None,
            "thoughts": None,
            "stages": [],
        }
    data = _agi_result(message)
    if not body.show_thoughts:
        data["thoughts"] = None
    return data


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    _, chat_llm, _ = _require_ready()
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "Пустое сообщение")
    history = [item.model_dump() for item in body.history]

    def stream():
        if body.model == "llm":
            yield _sse("status", {"text": "Генерация ответа..."})
            try:
                yield _sse("done", {
                    "model": "llm",
                    "response": chat_llm.chat(message, history),
                    "confidence": None,
                    "depth": "⚡ Обычный LLM",
                    "thoughts": None,
                })
            except Exception as exc:
                yield _sse("error", {"message": str(exc)})
            return

        q: queue.Queue = queue.Queue()

        def on_stage(stage: str) -> None:
            q.put(("stage", stage))

        def worker() -> None:
            try:
                data = _agi_result(message, on_stage=on_stage)
                if not body.show_thoughts:
                    data["thoughts"] = None
                q.put(("done", data))
            except Exception as exc:
                q.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        while True:
            kind, payload = q.get()
            if kind == "stage":
                yield _sse("stage", {"text": payload})
            elif kind == "error":
                yield _sse("error", {"message": payload})
                break
            elif kind == "done":
                yield _sse("done", payload)
                break

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if WEB_ROOT.exists():
    app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")
    app.mount("/css", StaticFiles(directory=WEB_ROOT / "css"), name="css")
    app.mount("/js", StaticFiles(directory=WEB_ROOT / "js"), name="js")
    app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")