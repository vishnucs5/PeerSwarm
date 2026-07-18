"""
Shared test fixtures and configuration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.quality import (
    HardGateFailure,
    QualityDimension,
    QualityGateResult,
    QualityScore,
)
from src.models.research import (
    EvidenceType,
    FindingCluster,
    ResearchFinding,
    ResearchPlan,
    ResearchStrategy,
    SubQuestion,
    SubQuestionPriority,
    Synthesis,
)

# ── Fixture directories ────────────────────────────────────────────


@pytest.fixture
def test_output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Research Plan Fixtures ──────────────────────────────────────────


@pytest.fixture
def sample_sub_questions() -> list[SubQuestion]:
    return [
        SubQuestion(
            question="What are the main approaches to RAG?",
            rationale="Foundation for understanding the field",
            priority=SubQuestionPriority.HIGH,
            strategy=ResearchStrategy.ACADEMIC_DEEP,
            assigned_researcher="researcher_a",
            search_terms=["RAG approaches", "retrieval augmented generation"],
        ),
        SubQuestion(
            question="What are current limitations of RAG systems?",
            rationale="Identify gaps and challenges",
            priority=SubQuestionPriority.HIGH,
            strategy=ResearchStrategy.GAP_ANALYSIS,
            assigned_researcher="researcher_b",
            search_terms=["RAG limitations", "RAG challenges"],
        ),
        SubQuestion(
            question="How does RAG compare to fine-tuning?",
            rationale="Comparative analysis",
            priority=SubQuestionPriority.MEDIUM,
            strategy=ResearchStrategy.COMPARATIVE,
            assigned_researcher="researcher_c",
            search_terms=["RAG vs fine-tuning"],
        ),
    ]


@pytest.fixture
def sample_plan(sample_sub_questions) -> ResearchPlan:
    return ResearchPlan(
        original_question="What are advances in RAG?",
        sub_questions=sample_sub_questions,
        overall_strategy="Comprehensive literature survey",
        risk_assessment={"recent_advances": "Rapidly evolving field"},
        success_criteria=["Cover at least 10 key papers"],
    )


# ── Finding Fixtures ───────────────────────────────────────────────


@pytest.fixture
def sample_findings() -> list[ResearchFinding]:
    return [
        ResearchFinding(
            sub_question_id="sq_001",
            researcher="researcher_a",
            claim="RAG combines retrieval with generation to ground LLM outputs",
            evidence="Key papers show RAG improves factual accuracy by 30%",
            evidence_type=EvidenceType.ACADEMIC_PAPER,
            source="Lewis et al. 2020",
            citation="Lewis et al. (2020). Retrieval-Augmented Generation...",
            confidence=0.9,
            relevance=0.95,
            tags=["rag", "foundations"],
        ),
        ResearchFinding(
            sub_question_id="sq_002",
            researcher="researcher_b",
            claim="RAG systems struggle with multi-hop reasoning",
            evidence="Benchmark evaluations show 40% accuracy drop on multi-hop queries",
            evidence_type=EvidenceType.ACADEMIC_PAPER,
            source="Zhang et al. 2023",
            citation="Zhang et al. (2023). Challenges in RAG...",
            confidence=0.8,
            relevance=0.85,
            tags=["rag", "limitations"],
        ),
        ResearchFinding(
            sub_question_id="sq_003",
            researcher="researcher_c",
            claim="RAG outperforms fine-tuning for knowledge-intensive tasks",
            evidence="Comparative study across 5 benchmarks shows RAG advantage",
            evidence_type=EvidenceType.ACADEMIC_PAPER,
            source="Wang et al. 2024",
            citation="Wang et al. (2024). RAG vs Fine-tuning...",
            confidence=0.85,
            relevance=0.9,
            tags=["rag", "comparison"],
        ),
    ]


# ── Synthesis Fixtures ─────────────────────────────────────────────


@pytest.fixture
def sample_synthesis(sample_findings) -> Synthesis:
    return Synthesis(
        question="What are advances in RAG?",
        plan_id="plan_001",
        executive_summary="RAG is a promising approach that combines retrieval and generation.",
        clusters=[
            FindingCluster(
                theme="RAG Architecture",
                findings=sample_findings[:1],
                summary="RAG architectures combine retrieval and generation",
            ),
        ],
        key_insights=["RAG improves factual grounding"],
        citations={"lewis2020": "Lewis et al. (2020)"},
    )


# ── Quality Fixtures ───────────────────────────────────────────────


@pytest.fixture
def passing_quality_score() -> QualityScore:
    return QualityScore(
        factual_accuracy=8,
        source_quality=8,
        logical_coherence=8,
        completeness=8,
        clarity=8,
        overall=8.0,
        iteration=1,
    )


@pytest.fixture
def failing_quality_score() -> QualityScore:
    return QualityScore(
        factual_accuracy=5,
        source_quality=6,
        logical_coherence=7,
        completeness=6,
        clarity=7,
        overall=6.2,
        iteration=1,
        hard_gate_failures=[
            HardGateFailure(
                dimension=QualityDimension.FACTUAL_ACCURACY,
                score=5,
                threshold=6,
                reason="Factual accuracy below threshold",
            ),
        ],
    )


@pytest.fixture
def passing_gate_result(passing_quality_score) -> QualityGateResult:
    return QualityGateResult(
        passed=True,
        score=passing_quality_score,
        action="write",
        reason="All quality dimensions meet threshold",
        iteration=1,
        max_iterations=3,
    )


@pytest.fixture
def failing_gate_result(failing_quality_score) -> QualityGateResult:
    return QualityGateResult(
        passed=False,
        score=failing_quality_score,
        action="revise_analysis",
        reason="Below threshold (5.0 < 6.0 hard gate for factual_accuracy)",
        iteration=1,
        max_iterations=3,
        failing_dimensions=[QualityDimension.FACTUAL_ACCURACY],
    )


# ── Config Fixtures ───────────────────────────────────────────────


@pytest.fixture
def mock_settings(tmp_path):
    """Settings object override for tests (env-var nesting does not bind).

    Per-test usage:
        with patch("src.<module>.get_settings") as g:
            g.return_value = mock_settings
    """
    from src.config import Settings

    s = Settings(_env_file=None)
    s.storage.output_dir = tmp_path / "test_output"
    s.quality.threshold = 8.0
    s.quality.hard_gate_threshold = 6.0
    s.quality.max_iterations = 3
    return s


# ── Helpers ────────────────────────────────────────────────────────


def make_quality_score(**overrides) -> QualityScore:
    """Create a QualityScore with defaults."""
    defaults = {
        "factual_accuracy": 8,
        "source_quality": 8,
        "logical_coherence": 8,
        "completeness": 8,
        "clarity": 8,
        "overall": 8.0,
        "iteration": 1,
    }
    defaults.update(overrides)
    return QualityScore(**defaults)


def make_finding(**overrides) -> ResearchFinding:
    """Create a ResearchFinding with defaults."""
    defaults = {
        "sub_question_id": "sq_test",
        "researcher": "researcher_a",
        "claim": "Test claim",
        "evidence": "Test evidence",
        "evidence_type": EvidenceType.ACADEMIC_PAPER,
        "source": "Test source",
        "confidence": 0.8,
        "relevance": 0.8,
    }
    defaults.update(overrides)
    return ResearchFinding(**defaults)
