"""
ArXiv search tool for academic paper retrieval.
"""

from __future__ import annotations

from typing import Any

import arxiv

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ArxivSearchResult:
    """Single ArXiv search result."""

    def __init__(self, entry: arxiv.Result):
        self.id = entry.entry_id
        self.title = entry.title
        self.authors = [a.name for a in entry.authors]
        self.summary = entry.summary
        self.published = entry.published
        self.updated = entry.updated
        self.pdf_url = entry.pdf_url
        self.links = [l.href for l in entry.links]
        self.categories = entry.categories
        self.doi = entry.doi
        self.comment = entry.comment
        self.journal_ref = entry.journal_ref

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "summary": self.summary[:500],
            "published": self.published.isoformat() if self.published else None,
            "pdf_url": self.pdf_url,
            "categories": self.categories,
            "doi": self.doi,
            "journal_ref": self.journal_ref,
        }


class ArxivTool:
    """Tool for searching ArXiv academic papers."""

    def __init__(self, max_results: int = 10, sort_by: str = "relevance"):
        self.client = arxiv.Client()
        self.max_results = max_results
        self.sort_by = getattr(arxiv.SortCriterion, sort_by.upper(), arxiv.SortCriterion.Relevance)

    def search(self, query: str, max_results: int | None = None) -> list[ArxivSearchResult]:
        """Search ArXiv for papers."""
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results or self.max_results,
                sort_by=self.sort_by,
            )

            results = []
            for result in self.client.results(search):
                results.append(ArxivSearchResult(result))

            logger.info(f"ArXiv search '{query[:50]}' returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"ArXiv search error: {e}")
            return []

    def search_by_id(self, paper_id: str) -> ArxivSearchResult | None:
        """Search for a specific paper by ID."""
        try:
            search = arxiv.Search(id_list=[paper_id])
            results = list(self.client.results(search))
            if results:
                return ArxivSearchResult(results[0])
        except Exception as e:
            logger.error(f"ArXiv ID search error: {e}")
        return None

    def search_by_author(self, author: str, max_results: int = 10) -> list[ArxivSearchResult]:
        """Search for papers by author."""
        return self.search(f"au:{author}", max_results=max_results)

    def search_by_category(
        self, category: str, query: str = "", max_results: int = 10
    ) -> list[ArxivSearchResult]:
        """Search within a specific category."""
        full_query = f"cat:{category}"
        if query:
            full_query = f"({query}) AND {full_query}"
        return self.search(full_query, max_results=max_results)

    def get_recent_papers(
        self, category: str = "cs.AI", max_results: int = 5
    ) -> list[ArxivSearchResult]:
        """Get most recent papers in a category."""
        return self.search_by_category(
            category=category,
            max_results=max_results,
        )


_arxiv_tool: ArxivTool | None = None


def get_arxiv_tool() -> ArxivTool:
    global _arxiv_tool
    if _arxiv_tool is None:
        _arxiv_tool = ArxivTool()
    return _arxiv_tool
