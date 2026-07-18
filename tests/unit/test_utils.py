"""
Tests for utils: logger, tracing, exporters.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.utils.logger import configure_logging, get_logger


class TestLogger:
    def test_get_logger(self):
        logger = get_logger("test")
        assert logger is not None

    def test_configure_logging(self):
        configure_logging(level="DEBUG")
        logger = get_logger("test_debug")
        assert logger is not None

    def test_info_log(self):
        logger = get_logger("test_info")
        logger.info("Test message")

    def test_error_log(self):
        logger = get_logger("test_error")
        logger.error("Test error")

    def test_json_log_output(self):
        import io
        import json

        buf = io.StringIO()
        configure_logging(level="DEBUG", format="json", stream=buf)
        logger = get_logger("json_test")
        logger.info("JSON test message", extra_field="hello")
        output = buf.getvalue()
        parsed = json.loads(output.strip().split("\n")[0])
        assert parsed["event"] == "JSON test message"
        assert parsed["logger"] == "json_test"
        assert parsed["service"] == "multi-agent-research-lab"
        assert "timestamp" in parsed
        assert parsed["extra_field"] == "hello"

    def test_json_log_context_binding(self):
        import io
        import json

        buf = io.StringIO()
        configure_logging(level="DEBUG", format="json", stream=buf)
        from src.utils.logger import LogContext

        with LogContext(request_id="abc-123"):
            logger = get_logger("ctx_test")
            logger.info("context test")
        output = buf.getvalue()
        parsed = json.loads(output.strip().split("\n")[0])
        assert parsed["event"] == "context test"


class TestTracing:
    def test_tracing(self):
        from src.utils.tracing import Tracing

        tm = Tracing()
        assert tm is not None
        assert tm.enabled is False

    def test_get_tracing(self):
        from src.utils.tracing import get_tracing

        tm = get_tracing()
        assert tm is not None
        assert tm.enabled is False

    def test_null_trace(self):
        from src.utils.tracing import NullTrace

        t = NullTrace()
        assert t.id == "disabled"
        with t as nt:
            assert nt.id == "disabled"
        gen = t.generation()
        assert gen is not None
        span = t.span()
        assert span is not None

    def test_null_generation(self):
        from src.utils.tracing import NullGeneration

        g = NullGeneration()
        with g as ng:
            ng.end()

    def test_null_span(self):
        from src.utils.tracing import NullSpan

        s = NullSpan()
        with s as ns:
            ns.end()

    def test_trace_disabled_returns_null(self):
        from src.utils.tracing import NullTrace, Tracing

        tm = Tracing()
        assert isinstance(tm.trace("test"), NullTrace)

    def test_generation_disabled_returns_null(self):
        from src.utils.tracing import NullGeneration, Tracing

        tm = Tracing()
        g = tm.generation(trace_id="t1", name="test", model="gpt-4", input="hello")
        assert isinstance(g, NullGeneration)

    def test_span_disabled_returns_null(self):
        from src.utils.tracing import NullSpan, Tracing

        tm = Tracing()
        s = tm.span(trace_id="t1", name="test")
        assert isinstance(s, NullSpan)

    def test_trace_agent_decorator(self):
        from src.utils.tracing import trace_agent

        @trace_agent("test_agent")
        def my_func(a, b):
            return a + b

        result = my_func(1, 2)
        assert result == 3

    def test_trace_tool_decorator(self):
        from src.utils.tracing import trace_tool

        @trace_tool("test_tool")
        def my_tool(x):
            return x * 2

        assert my_tool(5) == 10

    def test_trace_operation_decorator(self):
        from src.utils.tracing import trace_operation

        @trace_operation("test_op")
        def my_op(x):
            return x + 1

        assert my_op(3) == 4

    def test_trace_quality_loop(self):
        from src.utils.tracing import NullSpan, trace_quality_loop

        with trace_quality_loop(iteration=1) as span:
            assert isinstance(span, NullSpan)

    def test_record_quality_score_disabled(self):
        from src.utils.tracing import record_quality_score

        score = MagicMock()
        score.overall = 8.0
        score.hard_gate_failures = []
        record_quality_score("trace_1", score, iteration=1)

    def test_record_token_usage_disabled(self):
        from src.utils.tracing import record_token_usage

        record_token_usage("trace_1", {"prompt_tokens": 100, "completion_tokens": 50}, "gpt-4o")

    def test_flush(self):
        from src.utils.tracing import Tracing

        tm = Tracing()
        tm.flush()


class TestExporters:
    def test_export_markdown(self, tmp_path):
        from src.models.research import FinalReport, ReportSection
        from src.utils.exporters import export_markdown

        report = FinalReport(
            synthesis_id="syn_001",
            title="Test Report",
            executive_summary="Summary content",
            sections=[
                ReportSection(title="Intro", content="Intro content", order=0),
                ReportSection(title="Method", content="Method content", order=1),
            ],
            references=["Ref 1", "Ref 2"],
        )
        output = tmp_path / "test.md"
        result = export_markdown(report, output_path=output)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "Test Report" in content

    def test_export_json(self, tmp_path):
        from src.models.research import FinalReport
        from src.utils.exporters import export_json

        report = FinalReport(
            synthesis_id="syn_001",
            title="JSON Test",
            executive_summary="Summary",
        )
        output = tmp_path / "test.json"
        result = export_json(report, output_path=output)
        assert result.exists()
        import json

        data = json.loads(result.read_text())
        assert data["title"] == "JSON Test"

    def test_export_markdown_no_sections(self, tmp_path):
        from src.models.research import FinalReport
        from src.utils.exporters import export_markdown

        report = FinalReport(
            synthesis_id="syn_002",
            title="Minimal Report",
            executive_summary="Just a summary",
        )
        output = tmp_path / "minimal.md"
        result = export_markdown(report, output_path=output)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "Minimal Report" in content

    def test_export_markdown_default_path(self):
        from src.models.research import FinalReport
        from src.utils.exporters import export_markdown

        report = FinalReport(
            synthesis_id="syn_004",
            title="Default Path",
            executive_summary="Summary",
        )
        result = export_markdown(report)
        assert result is not None
        assert result.suffix == ".md"
        # Default filename starts with rpt_ followed by run_id hash
        assert result.stem.startswith("rpt_")
        result.unlink() if result.exists() else None

    def test_export_json_default_path(self):
        from src.models.research import FinalReport
        from src.utils.exporters import export_json

        report = FinalReport(
            synthesis_id="syn_005",
            title="JSON Default",
            executive_summary="Summary",
        )
        result = export_json(report)
        assert result is not None
        assert result.suffix == ".json"
        assert result.stem.startswith("rpt_")
        result.unlink() if result.exists() else None

    def test_generate_html(self):
        from src.models.research import FinalReport, ReportSection
        from src.utils.exporters import generate_html

        report = FinalReport(
            synthesis_id="syn_006",
            title="HTML Test",
            executive_summary="Executive summary",
            sections=[
                ReportSection(title="Intro", content="Intro content", order=0),
                ReportSection(title="Method", content="Method content", order=1),
            ],
            key_takeaways=["Takeaway 1"],
            limitations=["Limitation 1"],
            future_work=["Future item"],
            references=["Ref A"],
        )
        html = generate_html(report)
        assert "<h1>HTML Test</h1>" in html
        assert "Executive summary" in html
        assert "<h2>Intro</h2>" in html
        assert "Intro content" in html
        assert "<h2>Method</h2>" in html
        assert "Method content" in html
        assert "Takeaway 1" in html
        assert "Limitation 1" in html
        assert "Future item" in html
        assert "Ref A" in html

    def test_generate_html_minimal(self):
        from src.models.research import FinalReport
        from src.utils.exporters import generate_html

        report = FinalReport(
            synthesis_id="syn_007",
            title="Minimal",
            executive_summary="Minimal summary",
        )
        html = generate_html(report)
        assert "<h1>Minimal</h1>" in html
        assert "Minimal summary" in html

    def test_export_pdf_missing_weasyprint(self):
        from src.models.research import FinalReport
        from src.utils.exporters import HAS_WEASYPRINT, export_pdf

        report = FinalReport(
            synthesis_id="syn_008",
            title="PDF Test",
            executive_summary="Summary",
        )
        if not HAS_WEASYPRINT:
            import pytest

            with pytest.raises(ImportError, match="WeasyPrint is not installed"):
                export_pdf(report)
        # If weasyprint is installed, just verify it creates a file
        else:
            import tempfile

            output = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            result = export_pdf(report, output_path=output.name)
            assert result.exists()
            output.close()
