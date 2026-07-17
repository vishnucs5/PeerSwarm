"""
Tests for citation generation tool.
"""
from __future__ import annotations

from src.tools.citation_tool import CitationTool


class TestCitationTool:
    def setup_method(self):
        self.cit = CitationTool()

    def test_format_apa_journal(self):
        result = self.cit.format_apa(
            authors=["John Smith", "Jane Doe"],
            year=2023,
            title="A study on RAG systems",
            journal="Journal of AI Research",
            volume="10",
            issue="2",
            pages="100-120",
            doi="10.1234/example",
        )
        assert "Smith" in result
        assert "Doe" in result
        assert "(2023)" in result
        assert "doi.org" in result
        assert "Journal of AI Research" in result

    def test_format_apa_book(self):
        result = self.cit.format_apa(
            authors=["John Smith"],
            year=2020,
            title="Deep Learning Basics",
            publisher="MIT Press",
        )
        assert "Smith" in result
        assert "MIT Press" in result

    def test_format_apa_no_year(self):
        result = self.cit.format_apa(
            authors=["Alice Author"],
            year=None,
            title="Untitled work",
            url="https://example.com",
        )
        assert "(n.d.)" in result

    def test_format_apa_no_journal_no_publisher(self):
        result = self.cit.format_apa(
            authors=["Alice Author"],
            year=2023,
            title="Simple title",
        )
        assert "Author" in result

    def test_format_mla_journal(self):
        result = self.cit.format_mla(
            authors=["John Smith"],
            year=2023,
            title="RAG Study",
            journal="Journal of AI",
            doi="10.1234/test",
        )
        assert "Smith" in result
        assert "RAG Study" in result
        assert "Journal of AI" in result

    def test_format_mla_book(self):
        result = self.cit.format_mla(
            authors=["John Smith"],
            year=2021,
            title="Book Title",
            publisher="Oxford Press",
        )
        assert "Oxford Press" in result

    def test_format_chicago_journal(self):
        result = self.cit.format_chicago(
            authors=["John Smith"],
            year=2023,
            title="Chicago Style Paper",
            journal="History Journal",
            volume="5",
            pages="50-60",
        )
        assert "Smith" in result
        assert "History Journal" in result

    def test_format_chicago_book(self):
        result = self.cit.format_chicago(
            authors=["John Smith"],
            year=2020,
            title="Chicago Book",
            publisher="Chicago Press",
        )
        assert "Chicago Press" in result

    def test_generate_inline_single_author(self):
        result = self.cit.generate_inline_citation(["Smith"], 2023)
        assert "(Smith, 2023)" == result

    def test_generate_inline_two_authors(self):
        result = self.cit.generate_inline_citation(["Smith", "Doe"], 2023)
        assert "(Smith & Doe, 2023)" == result

    def test_generate_inline_three_authors(self):
        result = self.cit.generate_inline_citation(["Smith", "Doe", "Lee"], 2023)
        assert "et al." in result

    def test_generate_inline_no_authors(self):
        result = self.cit.generate_inline_citation([], 2023)
        assert "(2023)" == result

    def test_generate_inline_no_year(self):
        result = self.cit.generate_inline_citation(["Smith"], None)
        assert "(n.d.)" in result or "(Smith)" in result

    def test_extract_doi(self):
        result = self.cit.extract_doi("https://doi.org/10.1234/example.2023.001")
        assert result == "10.1234/example.2023.001"

    def test_extract_doi_no_match(self):
        result = self.cit.extract_doi("Just some text without doi")
        assert result is None

    def test_format_authors_apa_single(self):
        result = self.cit._format_authors_apa(["John Smith"])
        assert "Smith" in result

    def test_format_authors_apa_two(self):
        result = self.cit._format_authors_apa(["John Smith", "Jane Doe"])
        assert "&" in result

    def test_format_authors_apa_many(self):
        result = self.cit._format_authors_apa(["John Smith", "Jane Doe", "Bob Lee"])
        assert "&" in result

    def test_format_authors_apa_empty(self):
        result = self.cit._format_authors_apa([])
        assert result == "Unknown"

    def test_format_authors_mla_single(self):
        result = self.cit._format_authors_mla(["John Smith"])
        assert "Smith," in result

    def test_format_authors_mla_two(self):
        result = self.cit._format_authors_mla(["John Smith", "Jane Doe"])
        assert "and" in result

    def test_format_authors_mla_many(self):
        result = self.cit._format_authors_mla(["John Smith", "Jane Doe", "Bob Lee"])
        assert "et al." in result

    def test_format_authors_chicago_single(self):
        result = self.cit._format_authors_chicago(["John Smith"])
        assert "Smith," in result

    def test_format_authors_chicago_two(self):
        result = self.cit._format_authors_chicago(["John Smith", "Jane Doe"])
        assert "and" in result

    def test_format_authors_chicago_under_ten(self):
        result = self.cit._format_authors_chicago(["A Author", "B Author", "C Author"])
        assert ", and" in result

    def test_format_authors_chicago_over_ten(self):
        authors = [f"Author{i} Last{i}" for i in range(1, 12)]
        result = self.cit._format_authors_chicago(authors)
        assert "et al." in result


def test_get_citation_tool():
    from src.tools.citation_tool import get_citation_tool
    tool = get_citation_tool()
    assert tool is not None
    assert isinstance(tool, CitationTool)
