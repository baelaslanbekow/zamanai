from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urlparse

import httpx

from zamanai.modules.base import CognitiveModule
from zamanai.scraper import extract_urls_from_text, fetch_page_text, is_fetchable_url
from zamanai.types import CognitiveStage, MindState, WebSource

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _get_ddgs_class():
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        from duckduckgo_search import DDGS
        return DDGS


class WebSearchModule(CognitiveModule):
    """Первый этап — поиск в интернете и реальное чтение сайтов."""

    name = "web_search"

    SYSTEM = """Ты — модуль ПОИСКА В ИНТЕРНЕТЕ Джарвис.
{identity}
Сожми факты из реально прочитанных сайтов в чёткую сводку.
{lang}"""

    def process(self, state: MindState) -> MindState:
        if not self.config.web_search_enabled:
            state.add_thought(CognitiveStage.WEB_SEARCH, "Поиск отключён.", 0.5)
            return state

        try:
            sources: list[WebSource] = []

            # Если пользователь дал прямую ссылку — заходим на неё
            sources.extend(self._fetch_direct_urls(state.user_input))

            queries = self._build_queries(state)
            sources.extend(self._search_all(queries, state.user_input))

            sources = self._dedupe_sources(sources)
            sources = sources[: self.config.web_search_max_sites]

            if not sources:
                state.add_thought(
                    CognitiveStage.WEB_SEARCH,
                    "Сайты не найдены. Продолжаю на знаниях модели.",
                    0.3,
                )
                return state

            # Реально заходим на сайты и читаем содержимое
            self._visit_all_sites(sources)

            state.web_sources = sources
            summary = self._synthesize(state, sources)
            state.web_context = summary

            visited = sum(1 for s in sources if s.fetched)
            state.add_thought(
                CognitiveStage.WEB_SEARCH,
                f"Проверено {len(sources)} сайтов, зашёл и прочитал {visited}.\n\n{summary}",
                0.9 if visited >= 8 else 0.75,
                sites=len(sources),
                pages_read=visited,
            )
        except Exception as exc:
            state.add_thought(
                CognitiveStage.WEB_SEARCH,
                f"Ошибка поиска: {exc}. Продолжаю без интернета.",
                0.3,
            )
        return state

    def _fetch_direct_urls(self, text: str) -> list[WebSource]:
        sources: list[WebSource] = []
        for url in extract_urls_from_text(text)[:3]:
            content = fetch_page_text(url, timeout=10.0)
            if content:
                sources.append(WebSource(
                    title=f"Прямая ссылка: {urlparse(url).netloc}",
                    url=url,
                    snippet=content[:2000],
                    fetched=True,
                ))
        return sources

    def _dedupe_sources(self, sources: list[WebSource]) -> list[WebSource]:
        seen: set[str] = set()
        result: list[WebSource] = []
        for src in sources:
            key = src.url.rstrip("/").lower()
            if key not in seen:
                seen.add(key)
                result.append(src)
        return result

    def _build_queries(self, state: MindState) -> list[str]:
        clean = re.sub(r"https?://\S+", "", state.user_input).strip()
        base: list[str] = []

        u = state.understanding
        if u and u.search_queries:
            base.extend(q.strip() for q in u.search_queries if q and str(q).strip())

        if not base:
            base = [clean]

        if f"{clean} wikipedia" not in base:
            base.append(f"{clean} wikipedia")

        if not u or not u.search_queries:
            try:
                focus = u.answer_focus if u else clean
                data = self.llm.complete_json(
                    f"2 коротких поисковых запроса по ТОЧНОМУ смыслу вопроса. "
                    f"Не добавляй сравнения, если их нет в вопросе. {self._lang_note()}",
                    f'Вопрос: "{clean}"\nФокус: "{focus}"\n'
                    f'JSON: {{"queries":["q1","q2"]}}',
                    temperature=0.1,
                )
                for q in data.get("queries", []):
                    q = str(q).strip()
                    if q and q not in base:
                        base.append(q)
            except Exception:
                pass

        if u and not u.is_comparison_question:
            compare_markers = (" vs ", " versus ", " или ", "сравн", "лучше чем", " mercedes", " audi")
            base = [
                q for q in base
                if not any(m in q.lower() for m in compare_markers)
            ]

        return [q for q in base if q][:4]

    def _search_all(self, queries: list[str], original: str) -> list[WebSource]:
        sources: list[WebSource] = []
        limit = self.config.web_search_max_sites

        for query in queries:
            if len(sources) >= limit:
                break
            sources.extend(self._search_wikipedia(query, limit - len(sources)))

        for query in queries:
            if len(sources) >= limit:
                break
            sources.extend(self._search_ddg(query, limit - len(sources)))

        if len(sources) < 5:
            clean = re.sub(r"https?://\S+", "", original).strip()
            sources.extend(self._search_wikipedia(clean, limit))

        return sources

    def _search_ddg(self, query: str, limit: int) -> list[WebSource]:
        DDGS = _get_ddgs_class()
        sources: list[WebSource] = []
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=max(10, limit))
                if not isinstance(results, list):
                    results = list(results)
                for item in results:
                    url = (item.get("href") or item.get("link") or "").strip()
                    if not url or not is_fetchable_url(url):
                        continue
                    sources.append(WebSource(
                        title=(item.get("title") or url)[:200],
                        url=url,
                        snippet=(item.get("body") or item.get("snippet") or "")[:400],
                    ))
                    if len(sources) >= limit:
                        break
        except Exception:
            pass
        return sources

    def _search_wikipedia(self, query: str, limit: int) -> list[WebSource]:
        sources: list[WebSource] = []
        for lang, prefix in (("ru", "Википедия"), ("en", "Wikipedia")):
            if len(sources) >= limit:
                break
            try:
                api = f"https://{lang}.wikipedia.org/w/api.php"
                with httpx.Client(timeout=8.0, headers={"User-Agent": USER_AGENT}) as client:
                    search = client.get(api, params={
                        "action": "query", "list": "search",
                        "srsearch": query, "format": "json",
                        "srlimit": min(5, limit), "origin": "*",
                    })
                    search.raise_for_status()
                    for page in search.json().get("query", {}).get("search", []):
                        title = page.get("title", "")
                        page_id = page.get("pageid")
                        if not title:
                            continue
                        url = f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
                        snippet = re.sub(r"<[^>]+>", "", page.get("snippet", ""))

                        if page_id:
                            detail = client.get(api, params={
                                "action": "query", "pageids": page_id,
                                "prop": "extracts", "explaintext": True,
                                "exintro": False, "exchars": 2000,
                                "format": "json", "origin": "*",
                            })
                            if detail.status_code == 200:
                                extract = (
                                    detail.json()
                                    .get("query", {})
                                    .get("pages", {})
                                    .get(str(page_id), {})
                                    .get("extract", "")
                                )
                                if extract:
                                    snippet = extract

                        # Дополнительно заходим на страницу, если API дал мало текста
                        if len(snippet) < 400:
                            page_text = fetch_page_text(url, timeout=8.0)
                            if len(page_text) > len(snippet) and "data-mw" not in page_text[:300]:
                                snippet = page_text

                        sources.append(WebSource(
                            title=f"{prefix}: {title}",
                            url=url,
                            snippet=snippet[:2000],
                            fetched=bool(snippet),
                        ))
                        if len(sources) >= limit:
                            break
            except Exception:
                continue
        return sources

    def _visit_all_sites(self, sources: list[WebSource]) -> None:
        """Реально заходит на каждый сайт из списка (в пределах лимита)."""
        max_visits = min(self.config.web_search_fetch_pages, len(sources))

        # Сначала сайты, куда ещё не заходили или мало текста
        priority = sorted(
            sources,
            key=lambda s: (0 if not s.fetched else 1, 0 if len(s.snippet) < 300 else 1),
        )
        targets = priority[:max_visits]

        workers = min(8, len(targets))
        if not targets:
            return

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch_page_text, s.url, 10.0): s for s in targets}
            try:
                for future in as_completed(futures, timeout=45):
                    source = futures[future]
                    try:
                        text = future.result(timeout=12.0)
                        if len(text) > 100:
                            source.snippet = text[:2000]
                            source.fetched = True
                    except Exception:
                        if len(source.snippet) > 80:
                            source.fetched = True
            except Exception:
                pass

    def _fallback_summary(self, question: str, sources: list[WebSource]) -> str:
        lines = [f"По вопросу «{question}» — {len(sources)} источников:"]
        for i, s in enumerate(sources[:10], 1):
            tag = "✓ прочитан" if s.fetched else "сниппет"
            lines.append(f"{i}. [{tag}] {s.title}: {s.snippet[:250]}")
        return "\n".join(lines)

    def _synthesize(self, state: MindState, sources: list[WebSource]) -> str:
        question = state.user_input
        blocks = []
        for i, src in enumerate(sources[:20], 1):
            tag = "ЗАШЁЛ И ПРОЧИТАЛ" if src.fetched else "только сниппет"
            blocks.append(
                f"[{i}] {src.title}\n"
                f"URL: {src.url}\n"
                f"Статус: {tag}\n"
                f"Текст: {src.snippet[:700]}"
            )

        research = "\n\n".join(blocks)
        try:
            focus_note = ""
            if state.understanding:
                focus_note = (
                    f"\n\n{self._understanding_block(state)}\n"
                    "Отвечай ТОЛЬКО на то, что спросил пользователь. "
                    "Игнорируй факты про темы, которые он НЕ спрашивал."
                )

            summary = self.llm.complete(
                self.SYSTEM.format(identity=self._identity(), lang=self._lang_note()),
                f"""Вопрос: "{question}"
{focus_note}

Джарвис реально зашёл на сайты и прочитал их. Данные:
{research[:10000]}

Сводка фактов для ответа (5-10 предложений). Только по сути вопроса.""",
                temperature=0.2,
                max_tokens=900,
            )
            if summary and len(summary) > 20:
                return summary
        except Exception:
            pass
        return self._fallback_summary(question, sources)