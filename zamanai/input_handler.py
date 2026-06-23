from __future__ import annotations

import select
import sys


def _stdin_has_data(timeout: float = 0.05) -> bool:
    """Есть ли уже готовые строки в буфере stdin (остаток после вставки)."""
    try:
        return bool(select.select([sys.stdin], [], [], timeout)[0])
    except Exception:
        return False


def drain_pasted_lines() -> list[str]:
    """Считывает строки, оставшиеся в буфере после вставки многострочного текста."""
    lines: list[str] = []
    while _stdin_has_data(0.03):
        line = sys.stdin.readline()
        if not line:
            break
        lines.append(line.rstrip("\n\r"))
    return lines


def is_likely_fragment(text: str) -> bool:
    """Обрывок вставки из терминала — не обычное сообщение пользователя."""
    t = text.strip()
    if not t:
        return True

    if t.startswith("/"):
        return False

    # Артефакты копирования из консоли (промпт «Вы:» попал в текст)
    if "Вы:Вы:" in t or t.startswith("Вы:"):
        return True

    return False


def join_message(first_line: str, extra_lines: list[str]) -> str:
    parts = [first_line.strip()]
    parts.extend(line for line in extra_lines if line is not None)
    return "\n".join(parts).strip()


def read_multiline_until_end() -> str:
    """Режим /paste — пользователь сам завершает ввод командой /end."""
    lines: list[str] = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip().lower() in ("/end", "/send", "/done"):
            break
        if line.strip().lower() == "/cancel":
            return ""
        lines.append(line)
    return "\n".join(lines).strip()