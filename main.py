#!/usr/bin/env python3
"""Джарвис — консольный терминал."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

from zamanai.config import Config
from zamanai.input_handler import (
    drain_pasted_lines,
    is_likely_fragment,
    join_message,
    read_multiline_until_end,
)
from zamanai.mind import Jarvis
from zamanai.thinking_depth import DEPTH_LABELS, ThinkingDepth, parse_depth

console = Console()


def print_banner(name: str, model: str, web: bool, depth: str) -> None:
    web_status = "включён" if web else "выключен"
    console.print(Panel.fit(
        f"[bold cyan]{name}[/bold cyan]\n"
        f"[dim]AGI · {model} · интернет: {web_status} · мышление: {depth}[/dim]\n\n"
        "Команды:\n"
        "[yellow]/thoughts[/yellow] мысли | [yellow]/memory[/yellow] память\n"
        "[yellow]/fast[/yellow] быстрый | [yellow]/deep[/yellow] глубокий | [yellow]/expert[/yellow] экспертный\n"
        "[yellow]/paste[/yellow] длинный текст | [yellow]/auto[/yellow] авто | [yellow]/exit[/yellow] выход\n"
        "[dim]Наберите сообщение и нажмите Enter. Длинный текст: /paste[/dim]",
        border_style="cyan",
    ))


def main() -> None:
    try:
        config = Config.from_env()
    except ValueError as e:
        console.print(f"[red]Ошибка конфигурации:[/red] {e}")
        sys.exit(1)

    print_banner(
        config.assistant_name,
        config.model,
        config.web_search_enabled,
        config.thinking_depth,
    )
    show_thoughts = config.show_thoughts

    try:
        jarvis = Jarvis(config)
    except Exception as e:
        console.print(f"[red]Ошибка запуска:[/red] {e}")
        sys.exit(1)

    current_depth = parse_depth(config.thinking_depth)
    console.print("[green]✓[/green] Джарвис готов — дебаты, глубина, самопроверка\n")

    while True:
        try:
            first_line = Prompt.ask("[bold green]Вы[/bold green]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]До встречи![/cyan]")
            break

        from_paste = first_line.strip().lower() == "/paste"
        if from_paste:
            console.print(
                "[dim]Вставьте или наберите текст. Завершение: /end  |  Отмена: /cancel[/dim]"
            )
            text = read_multiline_until_end()
            if not text:
                continue
        else:
            extra = drain_pasted_lines()
            text = join_message(first_line, extra)

        text = text.strip()
        if not text:
            continue

        if not from_paste and is_likely_fragment(text):
            console.print(
                "[yellow]⚠️  Похоже на обрывок текста — сообщение не отправлено.[/yellow]\n"
                "[dim]Вставьте полный текст целиком и нажмите Enter один раз "
                "(или используйте /paste).[/dim]"
            )
            continue

        if text.lower() in ("/exit", "exit", "quit", "выход"):
            console.print("[cyan]До встречи![/cyan]")
            break

        if text.lower() == "/thoughts":
            show_thoughts = not show_thoughts
            console.print(f"[yellow]Мысли {'включены' if show_thoughts else 'скрыты'}[/yellow]")
            continue

        if text.lower() == "/memory":
            stats = jarvis.get_memory_stats()
            console.print(Panel(
                f"Эпизодов: {stats['episodes']}\n"
                f"Темы: {', '.join(stats['topics']) or 'пусто'}",
                title="💾 Память",
                border_style="blue",
            ))
            continue

        depth_commands = {
            "/fast": ThinkingDepth.FAST,
            "/deep": ThinkingDepth.DEEP,
            "/expert": ThinkingDepth.EXPERT,
            "/auto": ThinkingDepth.AUTO,
        }
        if text.lower() in depth_commands:
            current_depth = depth_commands[text.lower()]
            jarvis.set_depth(current_depth)
            label = DEPTH_LABELS.get(current_depth, current_depth.value)
            if current_depth == ThinkingDepth.AUTO:
                label = "🤖 Авто"
            console.print(f"[yellow]Режим мышления: {label}[/yellow]")
            continue

        jarvis.set_depth(current_depth if current_depth != ThinkingDepth.AUTO else None)

        # Один ввод → один полный цикл мышления. Пока думает — новый ввод не читаем.
        with console.status(
            f"[bold cyan]{config.assistant_name} думает...[/bold cyan]",
            spinner="dots",
        ) as status:

            def update_stage(stage: str) -> None:
                status.update(f"[bold cyan]{config.assistant_name}:[/bold cyan] {stage}")

            try:
                result = jarvis.think(text, on_stage=update_stage)
            except Exception as e:
                console.print(f"[red]Ошибка:[/red] {e}")
                continue

        depth_label = DEPTH_LABELS.get(result.depth, result.depth.value)
        if show_thoughts and result.thoughts:
            web_info = f" | 🌐 {len(result.state.web_sources)} сайтов" if result.state.web_sources else ""
            console.print(Panel(
                result.thoughts,
                title="🧠 Внутренний мир",
                border_style="dim cyan",
                subtitle=f"{depth_label} | Уверенность: {result.confidence:.0%}{web_info}",
            ))

        response_text = (result.response or "").strip()
        if not response_text:
            response_text = (
                "[red]Пустой ответ — повторите запрос или попробуйте /deep вместо экспертного режима.[/red]"
            )
            panel_content: str | Markdown = response_text
        else:
            try:
                panel_content = Markdown(response_text)
            except Exception:
                panel_content = response_text

        console.print(Panel(
            panel_content,
            title=f"[bold cyan]{config.assistant_name}[/bold cyan] [dim]({depth_label})[/dim]",
            border_style="green",
        ))
        console.print()


if __name__ == "__main__":
    main()