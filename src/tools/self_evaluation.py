"""
Self-evaluation tool for claim verification and groundedness checking.
"""
from __future__ import annotations

import re
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


class SelfEvaluationTool:
    """Tool for evaluating factual accuracy and citation quality."""

    def evaluate_claim(self, claim: str, evidence: str) -> dict[str, Any]:
        """Evaluate a claim against provided evidence."""
        claim_lower = claim.lower()
        evidence_lower = evidence.lower()

        claim_sentences = [s.strip() for s in re.split(r'[.!?]+', claim) if s.strip()]
        evidence_sentences = [s.strip() for s in re.split(r'[.!?]+', evidence) if s.strip()]

        supported_count = 0
        unsupported_claims = []
        partial_support = []

        for i, sentence in enumerate(claim_sentences):
            support = self._check_support(sentence, evidence_lower, evidence_sentences)
            if support["status"] == "supported":
                supported_count += 1
            elif support["status"] == "partial":
                partial_support.append(sentence)
            else:
                unsupported_claims.append(sentence)

        total = len(claim_sentences)
        if total == 0:
            return {"groundedness": 1.0, "supported": True, "details": "No claims to evaluate"}

        groundedness = (supported_count / total) if total > 0 else 0

        return {
            "groundedness": round(groundedness, 2),
            "supported_count": supported_count,
            "total_claims": total,
            "partial_support_count": len(partial_support),
            "unsupported_count": len(unsupported_claims),
            "unsupported_claims": unsupported_claims[:3],
            "evidence_coverage": f"{supported_count}/{total} claims supported",
        }

    def _check_support(self, claim: str, evidence_text: str,
                       evidence_sentences: list[str]) -> dict[str, Any]:
        """Check if a claim is supported by evidence."""
        claim_lower = claim.lower()
        claim_words = set(re.findall(r'\b\w+\b', claim_lower))
        claim_words -= self._get_stopwords()

        if not claim_words:
            return {"status": "supported", "confidence": 1.0}

        if claim_lower in evidence_text:
            return {"status": "supported", "confidence": 1.0}

        matched_words = sum(1 for w in claim_words if w in evidence_text)
        coverage_ratio = matched_words / len(claim_words)

        best_sentence_match = 0
        for sentence in evidence_sentences:
            sentence_words = set(re.findall(r'\b\w+\b', sentence.lower()))
            sentence_words -= self._get_stopwords()
            if sentence_words:
                overlap = len(claim_words & sentence_words)
                ratio = overlap / max(len(claim_words), len(sentence_words))
                best_sentence_match = max(best_sentence_match, ratio)

        if coverage_ratio >= 0.7 and best_sentence_match >= 0.3:
            return {"status": "supported", "confidence": round(best_sentence_match, 2)}
        if coverage_ratio >= 0.3:
            return {"status": "partial", "confidence": round(best_sentence_match, 2)}
        return {"status": "unsupported", "confidence": round(best_sentence_match, 2)}

    def check_citation(self, claim: str, source: str) -> dict[str, Any]:
        """Verify if a claim properly cites its source."""
        citation_patterns = [
            r'\([\w\s,\.]+\d{4}\)',          # (Author, 2020)
            r'\[\d+\]',                        # [1]
            r'\[[\d,\s]+\]',                   # [1, 2, 3]
            r'[\w\s]+\(\d{4}\)',               # Author (2020)
            r'[\w\s]+et al\.?\(\d{4}\)',       # Author et al. (2020)
        ]

        has_citation = any(re.search(pattern, claim) for pattern in citation_patterns)

        if not source:
            return {
                "has_citation": False,
                "quality": "missing_source",
                "suggestion": "Add source metadata",
            }

        has_url = bool(re.search(r'https?://\S+', source))
        has_doi = bool(re.search(r'10\.\d{4,}', source))

        has_author = bool(re.search(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,?\s*(?:et\s+al\.?)?', source))

        quality_score = 0
        if has_doi:
            quality_score += 0.4
        if has_url:
            quality_score += 0.3
        if has_author:
            quality_score += 0.2
        if has_citation:
            quality_score += 0.1

        return {
            "has_citation": has_citation,
            "has_author": has_author,
            "has_doi": has_doi,
            "has_url": has_url,
            "quality": "high" if quality_score >= 0.7 else "medium" if quality_score >= 0.4 else "low",
            "quality_score": round(quality_score, 2),
            "suggestion": self._get_citation_suggestion(has_citation, has_author, has_doi),
        }

    def check_contradiction(self, claim1: str, claim2: str) -> dict[str, Any]:
        """Check if two claims contradict each other."""
        contradiction_indicators = [
            "however", "but", "although", "conversely", "in contrast",
            "on the other hand", "contrary to", "opposite",
        ]

        negation_words = ["not", "no", "never", "without", "cannot", "doesn't", "don't",
                          "didn't", "won't", "wouldn't", "couldn't", "isn't", "aren't",
                          "wasn't", "weren't", "hasn't", "haven't", "hadn't"]

        claim1_lower = claim1.lower()
        claim2_lower = claim2.lower()

        claim1_words = set(re.findall(r'\b\w+\b', claim1_lower))
        claim2_words = set(re.findall(r'\b\w+\b', claim2_lower))

        common_words = claim1_words & claim2_words
        common_words -= self._get_stopwords()

        if not common_words:
            return {"contradicts": False, "reason": "Claims on different topics", "is_contradiction": False}

        has_indicator = any(ind in claim2_lower for ind in contradiction_indicators)
        has_negation = any(n in claim2_words for n in negation_words)

        if has_indicator and has_negation:
            return {
                "contradicts": True,
                "strength": "high",
                "reason": "Evidence of contrast and negation found",
                "is_contradiction": True,
            }
        if has_negation:
            return {
                "contradicts": True,
                "strength": "medium",
                "reason": "Negation found in second claim on same topic",
                "is_contradiction": True,
            }
        if has_indicator:
            return {
                "contradicts": True,
                "strength": "low",
                "reason": "Contrast indicator found",
                "is_contradiction": True,
            }

        return {"contradicts": False, "reason": "No contradiction detected", "is_contradiction": False}

    def evaluate_output_quality(self, text: str) -> dict[str, Any]:
        """Evaluate general quality metrics of text output."""
        if not text:
            return {"score": 0, "has_content": False, "readability": 0}

        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        words = re.findall(r'\b\w+\b', text)
        total_words = len(words)

        if total_words == 0:
            return {"score": 0, "has_content": False, "readability": 0}

        avg_sentence_length = total_words / max(len(sentences), 1)

        unique_words = len(set(w.lower() for w in words))
        lexical_diversity = unique_words / max(total_words, 1)

        markdown_elements = len(re.findall(r'^#{1,6}\s', text, re.MULTILINE))
        has_lists = bool(re.search(r'^\s*[-*+]\s', text, re.MULTILINE))
        has_links = bool(re.search(r'\[.*?\]\(.*?\)', text))

        readability = max(0, min(100, 100 - (avg_sentence_length * 2)))
        content_score = min(1.0, (total_words / 500) * 0.5 + lexical_diversity * 0.3 +
                          (0.2 if markdown_elements > 0 else 0))

        return {
            "score": round(content_score, 2),
            "has_content": total_words > 50,
            "readability": round(readability, 2),
            "word_count": total_words,
            "sentence_count": len(sentences),
            "avg_sentence_length": round(avg_sentence_length, 1),
            "lexical_diversity": round(lexical_diversity, 2),
            "markdown_elements": markdown_elements,
            "has_lists": has_lists,
            "has_links": has_links,
        }

    def _get_stopwords(self) -> set:
        """Get common stopwords."""
        return {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
            "been", "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall", "this",
            "that", "these", "those", "it", "its", "they", "them", "their",
            "we", "us", "our", "you", "your", "he", "she", "his", "her", "him",
            "not", "no", "nor", "so", "if", "then", "than", "too", "very",
            "just", "about", "above", "after", "again", "all", "also", "any",
            "because", "before", "between", "both", "each", "few", "more",
            "most", "other", "some", "such", "only", "own", "same", "here", "there",
            "when", "where", "why", "how", "what", "which", "who", "whom",
        }

    def _get_citation_suggestion(self, has_citation: bool, has_author: bool, has_doi: bool) -> str:
        """Get suggestion for improving citation quality."""
        if has_citation and has_doi:
            return ""
        if not has_citation:
            return "Add inline citation with author name and year"
        if not has_doi:
            return "Add DOI for better traceability"
        return "Citation quality could be improved"


_eval_tool: SelfEvaluationTool | None = None


def get_evaluation_tool() -> SelfEvaluationTool:
    global _eval_tool
    if _eval_tool is None:
        _eval_tool = SelfEvaluationTool()
    return _eval_tool
