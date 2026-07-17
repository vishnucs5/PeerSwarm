"""
Tests for research domain models.
"""
from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from src.models.research import (
    SubQuestion, ResearchPlan, ResearchFinding, FindingCluster,
    Synthesis, FinalReport, ReportSection, SubQuestionPriority,
    ResearchStrategy, EvidenceType,
)


class TestSubQuestion:
    def test_create_minimal(self):
        sq = SubQuestion(question="Test?", rationale="Testing")
        assert sq.id.startswith("sq_")
        assert sq.priority == SubQuestionPriority.MEDIUM
        assert sq.strategy == ResearchStrategy.ACADEMIC_DEEP
        assert sq.assigned_researcher == "researcher_a"

    def test_create_full(self):
        sq = SubQuestion(
            question="What is RAG?",
            rationale="Understanding foundations",
            priority=SubQuestionPriority.HIGH,
            strategy=ResearchStrategy.INDUSTRY_SURVEY,
            assigned_researcher="researcher_b",
            search_terms=["RAG", "retrieval"],
            depends_on=[],
        )
        assert sq.priority == SubQuestionPriority.HIGH
        assert sq.strategy == ResearchStrategy.INDUSTRY_SURVEY

    def test_invalid_researcher(self):
        with pytest.raises(ValidationError):
            SubQuestion(question="Test?", rationale="Testing", assigned_researcher="researcher_d")

    def test_search_terms_default(self):
        sq = SubQuestion(question="Test?", rationale="Testing")
        assert sq.search_terms == []


class TestResearchPlan:
    def test_create_with_sub_questions(self, sample_sub_questions):
        plan = ResearchPlan(
            original_question="Test?",
            sub_questions=sample_sub_questions,
        )
        assert len(plan.sub_questions) == 3
        assert plan.id.startswith("plan_")

    def test_too_few_sub_questions(self):
        with pytest.raises(ValidationError):
            ResearchPlan(
                original_question="Test?",
                sub_questions=[SubQuestion(question="Q1?", rationale="R")],
            )

    def test_too_many_sub_questions(self):
        with pytest.raises(ValidationError):
            ResearchPlan(
                original_question="Test?",
                sub_questions=[
                    SubQuestion(question=f"Q{i}?", rationale="R")
                    for i in range(7)
                ],
            )

    def test_defaults(self):
        plan = ResearchPlan(
            original_question="Test?",
            sub_questions=[
                SubQuestion(question="Q1?", rationale="R"),
                SubQuestion(question="Q2?", rationale="R"),
            ],
        )
        assert plan.risk_assessment == {}
        assert plan.success_criteria == []
        assert plan.estimated_iterations == 1


class TestResearchFinding:
    def test_create_minimal(self):
        finding = ResearchFinding(
            sub_question_id="sq_001",
            researcher="researcher_a",
            claim="Test claim",
            evidence="Test evidence",
            evidence_type=EvidenceType.ACADEMIC_PAPER,
            source="Test source",
        )
        assert finding.id.startswith("find_")
        assert finding.confidence == 0.8
        assert finding.relevance == 0.8
        assert finding.tags == []

    def test_create_with_citation(self):
        finding = ResearchFinding(
            sub_question_id="sq_001",
            researcher="researcher_b",
            claim="Test",
            evidence="Test",
            evidence_type=EvidenceType.BLOG_POST,
            source="blog.example.com",
            citation="Author (2024). Blog post.",
        )
        assert finding.citation == "Author (2024). Blog post."

    def test_default_tags(self, sample_findings):
        assert sample_findings[0].tags == ["rag", "foundations"]


class TestSynthesis:
    def test_create_minimal(self):
        syn = Synthesis(question="Test?", plan_id="plan_001")
        assert syn.id.startswith("syn_")
        assert syn.executive_summary == ""
        assert syn.clusters == []
        assert syn.version == 1

    def test_with_clusters(self, sample_findings):
        cluster = FindingCluster(
            theme="RAG",
            findings=sample_findings,
            summary="Summary",
        )
        syn = Synthesis(
            question="Test?",
            plan_id="plan_001",
            clusters=[cluster],
            key_insights=["Insight 1"],
        )
        assert len(syn.clusters) == 1
        assert len(syn.key_insights) == 1
        assert len(syn.clusters[0].findings) == 3


class TestFinalReport:
    def test_create_minimal(self):
        report = FinalReport(
            synthesis_id="syn_001",
            title="Test Report",
            executive_summary="Summary",
        )
        assert report.id.startswith("rpt_")
        assert report.sections == []

    def test_with_sections(self):
        report = FinalReport(
            synthesis_id="syn_001",
            title="Test Report",
            executive_summary="Summary",
            sections=[
                ReportSection(title="Intro", content="Intro content", order=0),
                ReportSection(title="Body", content="Body content", order=1),
            ],
            references=["Ref 1", "Ref 2"],
        )
        assert len(report.sections) == 2
        assert len(report.references) == 2