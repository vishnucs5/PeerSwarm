"""
Citation generation tool for formatting academic citations.
"""

from __future__ import annotations

import re
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


class CitationTool:
    """Tool for generating and formatting citations."""

    def __init__(self):
        self._crossref_client = None

    def format_apa(
        self,
        authors: list[str],
        year: int | None,
        title: str,
        journal: str | None = None,
        volume: str | None = None,
        issue: str | None = None,
        pages: str | None = None,
        doi: str | None = None,
        url: str | None = None,
        publisher: str | None = None,
    ) -> str:
        """Format citation in APA style."""
        author_str = self._format_authors_apa(authors)
        year_str = f"({year})" if year else "(n.d.)"
        title_str = title

        parts = [f"{author_str} {year_str}."]

        if journal:
            title_str = title_str.rstrip(".")
            parts.append(f"{title_str}.")
            journal_str = journal
            if volume:
                journal_str += f", {volume}"
                if issue:
                    journal_str += f"({issue})"
            if pages:
                journal_str += f", {pages}"
            parts.append(f"*{journal_str}*.")
        elif publisher:
            parts.append(f"{title_str}.")
            parts.append(f"{publisher}.")
        else:
            parts.append(f"{title_str}.")

        if doi:
            parts.append(f"https://doi.org/{doi}")
        elif url:
            parts.append(f"Retrieved from {url}")

        return " ".join(parts)

    def format_mla(
        self,
        authors: list[str],
        year: int | None,
        title: str,
        journal: str | None = None,
        publisher: str | None = None,
        doi: str | None = None,
        url: str | None = None,
    ) -> str:
        """Format citation in MLA style."""
        author_str = self._format_authors_mla(authors)
        title_str = title

        if journal:
            parts = [f'{author_str} "{title_str}." *{journal}*,']
            if year:
                parts[-1] += f" {year}."
            if doi:
                parts.append(f"doi:{doi}")
            elif url:
                parts.append(url)
            return " ".join(parts)
        parts = [f"{author_str} *{title_str}*."]
        if publisher:
            parts.append(f"{publisher},")
        if year:
            parts.append(f"{year}.")
        return " ".join(parts)

    def format_chicago(
        self,
        authors: list[str],
        year: int | None,
        title: str,
        journal: str | None = None,
        volume: str | None = None,
        issue: str | None = None,
        pages: str | None = None,
        doi: str | None = None,
        url: str | None = None,
        publisher: str | None = None,
    ) -> str:
        """Format citation in Chicago style."""
        author_str = self._format_authors_chicago(authors)
        year_str = str(year) if year else "n.d."

        if journal:
            parts = [f'{author_str} "{title}," *{journal}*']
            if volume:
                parts[-1] += f" {volume}"
                if issue:
                    parts[-1] += f", no. {issue}"
            if year:
                parts[-1] += f" ({year})"
            if pages:
                parts[-1] += f": {pages}."
            else:
                parts[-1] += "."
            if doi:
                parts.append(f"https://doi.org/{doi}")
        else:
            parts = [f"{author_str}. *{title}*."]
            if publisher:
                parts.append(f"{publisher},")
            parts.append(f"{year_str}.")
            if url:
                parts.append(url)

        return " ".join(parts)

    def generate_inline_citation(self, authors: list[str], year: int | None) -> str:
        """Generate inline citation text."""
        if not authors:
            return f"({year})" if year else "(n.d.)"

        if len(authors) == 1:
            return f"({authors[0]}, {year})" if year else f"({authors[0]})"
        if len(authors) == 2:
            return (
                f"({authors[0]} & {authors[1]}, {year})"
                if year
                else f"({authors[0]} & {authors[1]})"
            )
        return f"({authors[0]} et al., {year})" if year else f"({authors[0]} et al.)"

    def extract_doi(self, text: str) -> str | None:
        """Extract DOI from text."""
        doi_pattern = r"(10\.\d{4,}/[-._;()/:A-Za-z0-9]+)"
        match = re.search(doi_pattern, text)
        return match.group(1) if match else None

    def resolve_doi(self, doi: str) -> dict[str, Any] | None:
        """Resolve a DOI to get citation metadata via Crossref."""
        try:
            import requests

            url = f"https://api.crossref.org/works/{doi}"
            response = requests.get(
                url, headers={"User-Agent": "MultiAgentResearchLab/1.0"}, timeout=15
            )
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})

            authors = []
            for author in message.get("author", []):
                given = author.get("given", "")
                family = author.get("family", "")
                if family:
                    authors.append(f"{given} {family}".strip())

            return {
                "doi": doi,
                "title": message.get("title", [""])[0] if message.get("title") else "",
                "authors": authors,
                "year": message.get("published-print", {}).get("date-parts", [[None]])[0][0]
                or message.get("published-online", {}).get("date-parts", [[None]])[0][0],
                "journal": message.get("container-title", [""])[0]
                if message.get("container-title")
                else "",
                "publisher": message.get("publisher", ""),
                "volume": message.get("volume", ""),
                "issue": message.get("issue", ""),
                "pages": message.get("page", ""),
            }
        except Exception as e:
            logger.error(f"Error resolving DOI {doi}: {e}")
            return None

    def _format_authors_apa(self, authors: list[str]) -> str:
        """Format authors list in APA style."""
        if not authors:
            return "Unknown"

        formatted = []
        for author in authors:
            parts = author.strip().split()
            if len(parts) >= 2:
                last = parts[-1]
                initials = " ".join(f"{p[0]}." for p in parts[:-1] if p)
                formatted.append(f"{last}, {initials}")
            elif len(parts) == 1:
                formatted.append(f"{parts[-1]},")

        if len(formatted) == 1:
            return formatted[0]
        if len(formatted) == 2:
            return f"{formatted[0]} & {formatted[1]}"
        return f"{', '.join(formatted[:-1])}, & {formatted[-1]}"

    def _format_authors_mla(self, authors: list[str]) -> str:
        """Format authors list in MLA style."""
        if not authors:
            return "Unknown."

        if len(authors) == 1:
            parts = authors[0].strip().split()
            if len(parts) >= 2:
                return f"{parts[-1]}, {' '.join(parts[:-1])}"
            return f"{authors[0]}."

        if len(authors) == 2:
            return f"{authors[0]} and {authors[1]}"

        return f"{authors[0]} et al."

    def _format_authors_chicago(self, authors: list[str]) -> str:
        """Format authors list in Chicago style."""
        if not authors:
            return "Unknown."

        if len(authors) == 1:
            parts = authors[0].strip().split()
            if len(parts) >= 2:
                return f"{parts[-1]}, {' '.join(parts[:-1])}"
            return f"{authors[0]}."

        if len(authors) == 2:
            return f"{authors[0]} and {authors[1]}"

        if len(authors) <= 10:
            return f"{', '.join(authors[:-1])}, and {authors[-1]}"

        return f"{authors[0]} et al."


_citation_tool: CitationTool | None = None


def get_citation_tool() -> CitationTool:
    global _citation_tool
    if _citation_tool is None:
        _citation_tool = CitationTool()
    return _citation_tool
