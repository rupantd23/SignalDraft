from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

from tavily import TavilyClient

from src.config import Settings, settings
from src.models import ProspectInput, Source


class ResearchError(RuntimeError):
    """Raised when Tavily research cannot be completed."""


class ResearchService:
    def __init__(self, config: Settings = settings) -> None:
        if not config.tavily_api_key:
            raise ResearchError("TAVILY_API_KEY is not configured.")
        self.client = TavilyClient(api_key=config.tavily_api_key)
        self.search_depth = config.tavily_search_depth

    def _search(self, search_request: tuple[str, list[str] | None]) -> dict:
        query, include_domains = search_request
        search_options = {
            "query": query,
            "search_depth": getattr(self, "search_depth", "basic"),
            "max_results": 3,
            "include_answer": False,
            "include_raw_content": False,
        }
        if include_domains:
            search_options["include_domains"] = include_domains
        return self.client.search(**search_options)

    def research(self, prospect: ProspectInput) -> list[Source]:
        queries = [
            (
                f'"{prospect.full_name}" "{prospect.company_name}"',
                None,
            ),
            (
                f'site:linkedin.com/in "{prospect.full_name}" '
                f'"{prospect.company_name}"',
                ["linkedin.com"],
            ),
            (
                f'"{prospect.company_name}" business news strategy hiring expansion',
                None,
            ),
        ]
        results_by_url: dict[str, dict[str, str]] = {}
        try:
            with ThreadPoolExecutor(max_workers=len(queries)) as executor:
                responses = executor.map(self._search, queries)
                for response in responses:
                    for result in response.get("results", []):
                        url = result.get("url", "").strip()
                        if not url.startswith(("https://", "http://")):
                            continue
                        results_by_url.setdefault(
                            url,
                            {
                                "title": result.get("title", ""),
                                "content": result.get("raw_content")
                                or result.get("content", ""),
                                "published_date": result.get("published_date") or "",
                            },
                        )

            urls = list(results_by_url)[:5]
            if urls:
                extracted = self.client.extract(urls=urls)
                for item in extracted.get("results", []):
                    url = item.get("url", "")
                    if url in results_by_url and item.get("raw_content"):
                        results_by_url[url]["content"] = item["raw_content"]
        except Exception as exc:
            raise ResearchError(f"Tavily research failed: {exc}") from exc

        sources: list[Source] = []
        for url, item in results_by_url.items():
            content = " ".join(item["content"].split())
            if not content:
                continue
            source_id = sha256(url.encode("utf-8")).hexdigest()[:10]
            try:
                sources.append(
                    Source(
                        id=source_id,
                        title=item["title"] or url,
                        url=url,
                        content=content[:12000],
                        published_date=item["published_date"] or None,
                    )
                )
            except ValueError:
                continue
        return sources
