"""
Scopus API client for automated literature search.
Settings from config.yaml (scopus section) and .env (SCOPUS_API_KEY).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config.settings import cfg, secrets

logger = logging.getLogger(__name__)

SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
SCOPUS_ABSTRACT_URL = "https://api.elsevier.com/content/abstract/scopus_id"


@dataclass
class ScopusArticle:
    scopus_id: str
    title: str
    authors: str
    journal: str
    year: int
    doi: str = ""
    abstract: str = ""
    citation_count: int = 0
    keywords: list[str] = field(default_factory=list)
    url: str = ""

    @property
    def apa_reference(self) -> str:
        return f"{self.authors} ({self.year}). {self.title}. {self.journal}. doi:{self.doi}"


class ScopusScraper:
    def __init__(self):
        self.api_key = secrets.scopus_api_key
        self.inst_token = secrets.scopus_inst_token
        self.headers = {"X-ELS-APIKey": self.api_key, "Accept": "application/json"}
        if self.inst_token:
            self.headers["X-ELS-Insttoken"] = self.inst_token

    @property
    def is_available(self) -> bool:
        return cfg.scopus_enabled and bool(self.api_key)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=15),
        before_sleep=lambda rs: logger.warning(
            f"Scopus search retry {rs.attempt_number}/3 after: {rs.outcome.exception()}"
        ),
    )
    async def search(self, query: str, max_results: int = 50, sort: str = "-citedby-count",
                     year_from: int | None = None, subject_area: str | None = None) -> list[ScopusArticle]:
        params: dict = {
            "query": query, "count": min(max_results, 25), "sort": sort,
            "field": "dc:title,dc:creator,prism:publicationName,prism:coverDate,"
                     "prism:doi,citedby-count,authkeywords,dc:identifier,link",
        }
        if year_from:
            params["date"] = f"{year_from}-"
        if subject_area:
            params["subj"] = subject_area

        articles: list[ScopusArticle] = []
        start = 0
        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(articles) < max_results:
                params["start"] = start
                resp = await client.get(SCOPUS_SEARCH_URL, headers=self.headers, params=params)
                if resp.status_code in (429, 500, 502, 503, 504):
                    logger.warning(f"Scopus search: transient HTTP {resp.status_code}")
                    raise httpx.NetworkError(f"HTTP {resp.status_code}")
                if resp.status_code != 200:
                    logger.warning(f"Scopus search: HTTP {resp.status_code} (not retryable)")
                    break
                data = resp.json()
                results = data.get("search-results", {}).get("entry", [])
                if not results or results[0].get("error"):
                    break
                for entry in results:
                    a = self._parse_entry(entry)
                    if a:
                        articles.append(a)
                total = int(data.get("search-results", {}).get("opensearch:totalResults", 0))
                start += len(results)
                if start >= total or start >= max_results:
                    break

        logger.info(f"Scopus: {len(articles)} articles for: {query[:80]}…")
        return articles[:max_results]

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=15),
        before_sleep=lambda rs: logger.warning(
            f"Scopus abstract retry {rs.attempt_number}/3 after: {rs.outcome.exception()}"
        ),
    )
    async def get_abstract(self, scopus_id: str) -> str:
        url = f"{SCOPUS_ABSTRACT_URL}/{scopus_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self.headers)
            if resp.status_code == 200:
                core = resp.json().get("abstracts-retrieval-response", {}).get("coredata", {})
                return core.get("dc:description", "")
            if resp.status_code in (429, 500, 502, 503, 504):
                logger.warning(f"Scopus abstract {scopus_id}: transient HTTP {resp.status_code}")
                raise httpx.NetworkError(f"HTTP {resp.status_code}")
            logger.warning(f"Scopus abstract {scopus_id}: HTTP {resp.status_code} (not retryable)")
            return ""

    async def search_for_proposal(self, topic: str, keywords: list[str],
                                   max_results: int | None = None,
                                   year_from: int | None = None) -> list[ScopusArticle]:
        """Multi-query search using settings from config.yaml."""
        mr = max_results or cfg.scopus_max_results
        yf = year_from or cfg.scopus_year_from

        all_articles: dict[str, ScopusArticle] = {}
        main_results = await self.search(f'TITLE-ABS-KEY("{topic}")', max_results=mr // 2, year_from=yf)
        for a in main_results:
            all_articles[a.scopus_id] = a

        for kw in keywords[:4]:
            kw_results = await self.search(
                f'TITLE-ABS-KEY("{kw}") AND TITLE-ABS-KEY("{topic.split()[0]}")',
                max_results=10, year_from=yf,
            )
            for a in kw_results:
                if a.scopus_id not in all_articles:
                    all_articles[a.scopus_id] = a

        sorted_articles = sorted(all_articles.values(), key=lambda a: a.citation_count, reverse=True)

        if cfg.scopus_enrich_abstracts:
            top = sorted_articles[:cfg.scopus_top_abstracts]
            abstracts = await asyncio.gather(*(self.get_abstract(a.scopus_id) for a in top), return_exceptions=True)
            for article, abstract in zip(top, abstracts):
                if isinstance(abstract, str):
                    article.abstract = abstract

        return sorted_articles

    def _parse_entry(self, entry: dict) -> ScopusArticle | None:
        try:
            return ScopusArticle(
                scopus_id=entry.get("dc:identifier", "").replace("SCOPUS_ID:", ""),
                title=entry.get("dc:title", ""), authors=entry.get("dc:creator", ""),
                journal=entry.get("prism:publicationName", ""),
                year=int(entry.get("prism:coverDate", "0000")[:4]),
                doi=entry.get("prism:doi", ""),
                citation_count=int(entry.get("citedby-count", 0)),
                keywords=[k.strip() for k in entry.get("authkeywords", "").split("|") if k.strip()],
                url=next((l["@href"] for l in entry.get("link", []) if l.get("@ref") == "scopus"), ""),
            )
        except Exception as e:
            logger.warning(f"Scopus parse error: {e}")
            return None

    def format_references_apa(self, articles: list[ScopusArticle], max_refs: int = 30) -> str:
        return "\n".join(f"[{i}] {a.apa_reference}" for i, a in enumerate(articles[:max_refs], 1))
