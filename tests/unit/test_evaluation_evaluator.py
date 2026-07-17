"""
Tests for the evaluation module (evaluator).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.evaluation.evaluator import ResearchEvaluator, BatchEvaluator


class TestResearchEvaluator:
    @patch("src.crew.agents.create_critic_agent")
    def test_init(self, mock_create):
        mock_create.return_value = MagicMock()
        ev = ResearchEvaluator()
        assert ev.critic is not None
        mock_create.assert_called_once()

    @patch("src.crew.agents.create_critic_agent")
    def test_evaluate_report_not_found(self, mock_create):
        mock_create.return_value = MagicMock()
        ev = ResearchEvaluator()
        result = ev.evaluate_report(Path("/nonexistent/report.md"))
        assert result is None

    @patch("src.crew.agents.create_critic_agent")
    def test_evaluate_report_read_error(self, mock_create, tmp_path):
        mock_create.return_value = MagicMock()
        ev = ResearchEvaluator()
        path = tmp_path / "report.md"
        path.write_text("test", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=PermissionError):
            result = ev.evaluate_report(path)
            assert result is None

    @patch("src.crew.agents.create_critic_agent")
    def test_evaluate_from_state_no_get_all_findings(self, mock_create):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent
        mock_score = MagicMock()
        mock_agent.execute.return_value = mock_score

        ev = ResearchEvaluator()
        state = MagicMock(spec=[])
        state.question = "test question"
        state.iteration = 1
        state.synthesis = MagicMock()

        score = ev.evaluate_from_state(state)
        assert score == mock_score
        mock_agent.execute.assert_called_once()


class TestBatchEvaluator:
    def test_output_dir_default(self, tmp_path):
        with patch("src.evaluation.evaluator.get_settings") as mock_settings:
            mock_settings.return_value.storage.output_dir = tmp_path
            be = BatchEvaluator()
            assert be.output_dir == tmp_path / "evaluations"
            assert be.output_dir.exists()

    def test_output_dir_custom(self, tmp_path):
        with patch("src.evaluation.evaluator.get_settings"):
            custom = tmp_path / "custom_eval"
            be = BatchEvaluator(output_dir=custom)
            assert be.output_dir == custom
            assert custom.exists()

    def test_compute_summary_empty(self):
        with patch("src.evaluation.evaluator.get_settings"):
            be = BatchEvaluator(output_dir=Path("."))
            result = be._compute_summary([])
            assert result["avg_quality"] == 0

    def test_compute_summary_with_data(self):
        with patch("src.evaluation.evaluator.get_settings"):
            be = BatchEvaluator(output_dir=Path("."))
            results = [
                {"quality_score": {"overall": 8.0}, "iterations": 2, "total_findings": 5},
                {"quality_score": {"overall": 9.0}, "iterations": 3, "total_findings": 7},
            ]
            summary = be._compute_summary(results)
            assert summary["avg_quality"] == 8.5
            assert summary["min_quality"] == 8.0
            assert summary["max_quality"] == 9.0
            assert summary["avg_iterations"] == 2.5
            assert summary["avg_findings"] == 6.0

    def test_compute_summary_with_errors_skipped(self):
        with patch("src.evaluation.evaluator.get_settings"):
            be = BatchEvaluator(output_dir=Path("."))
            results = [
                {"quality_score": {"overall": 8.0}, "iterations": 2, "total_findings": 5},
                {"error": "failed", "question": "q2"},
            ]
            summary = be._compute_summary(results)
            assert summary["avg_quality"] == 8.0
            assert summary["avg_iterations"] == 2.0

    def test_compute_summary_single_item(self):
        with patch("src.evaluation.evaluator.get_settings"):
            be = BatchEvaluator(output_dir=Path("."))
            results = [
                {"quality_score": {"overall": 7.5}, "iterations": 1, "total_findings": 3},
            ]
            summary = be._compute_summary(results)
            assert summary["avg_quality"] == 7.5
            assert summary["min_quality"] == 7.5
            assert summary["max_quality"] == 7.5

    def test_run_evaluation_suite(self, tmp_path):
        with (
            patch("src.evaluation.evaluator.BatchEvaluator.evaluate_question") as mock_eq,
        ):
            mock_eq.return_value = {
                "question": "test",
                "run_id": "run_1",
                "iterations": 1,
                "quality_score": {"overall": 8.0},
                "total_findings": 3,
                "timestamp": "2025-01-01T00:00:00",
            }
            with patch("src.evaluation.evaluator.get_settings"):
                be = BatchEvaluator(output_dir=tmp_path)
                result_path = be.run_evaluation_suite(["q1", "q2"], label="test_suite")
                assert result_path.exists()
                import json
                report = json.loads(result_path.read_text())
                assert report["label"] == "test_suite"
                assert report["total"] == 2
                assert report["completed"] == 2

    def test_run_evaluation_suite_with_errors(self, tmp_path):
        with (
            patch("src.evaluation.evaluator.BatchEvaluator.evaluate_question") as mock_eq,
        ):
            mock_eq.side_effect = [
                {"question": "q1", "quality_score": {"overall": 8.0}, "iterations": 2, "total_findings": 3},
                Exception("flow failed"),
            ]
            with patch("src.evaluation.evaluator.get_settings"):
                be = BatchEvaluator(output_dir=tmp_path)
                result_path = be.run_evaluation_suite(["q1", "q2"])
                import json
                report = json.loads(result_path.read_text())
                assert report["total"] == 2
                assert report["completed"] == 1
                assert report["failed"] == 1


def test_get_evaluator():
    from src.evaluation.evaluator import get_evaluator
    with patch("src.evaluation.evaluator.ResearchEvaluator") as mock:
        mock.return_value = MagicMock()
        ev = get_evaluator()
        assert ev is not None


def test_get_batch_evaluator():
    from src.evaluation.evaluator import get_batch_evaluator
    with patch("src.evaluation.evaluator.BatchEvaluator") as mock:
        mock.return_value = MagicMock()
        be = get_batch_evaluator()
        assert be is not None