"""
Report export utilities (Markdown, PDF).
"""

from __future__ import annotations

from pathlib import Path

try:
    from weasyprint import CSS, HTML
    from weasyprint.text.fonts import FontConfiguration

    HAS_WEASYPRINT = True
except (ImportError, OSError):
    HAS_WEASYPRINT = False
    HTML, CSS, FontConfiguration = None, None, None

from src.models.research import FinalReport
from src.utils.logger import get_logger

logger = get_logger(__name__)


def export_markdown(report: FinalReport, output_path: Path | None = None) -> Path:
    """Export report to Markdown file."""
    lines = [
        f"# {report.title}",
        "",
        f"**Question:** {getattr(report, 'question', 'N/A')}",
        f"**Generated:** {report.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Report ID:** {report.id}",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
    ]

    if report.key_takeaways:
        lines.extend(
            [
                "## Key Takeaways",
                "",
            ]
        )
        for i, takeaway in enumerate(report.key_takeaways, 1):
            lines.append(f"{i}. {takeaway}")
        lines.append("")

    for section in report.sections:
        lines.extend(
            [
                f"## {section.title}",
                "",
                section.content,
                "",
            ]
        )

    if report.limitations:
        lines.extend(
            [
                "## Limitations",
                "",
            ]
        )
        for limitation in report.limitations:
            lines.append(f"- {limitation}")
        lines.append("")

    if report.future_work:
        lines.extend(
            [
                "## Future Work",
                "",
            ]
        )
        for item in report.future_work:
            lines.append(f"- {item}")
        lines.append("")

    if report.references:
        lines.extend(
            [
                "## References",
                "",
            ]
        )
        for i, ref in enumerate(report.references, 1):
            lines.append(f"{i}. {ref}")
        lines.append("")

    markdown = "\n".join(lines)

    if output_path is None:
        output_path = Path(f"data/outputs/{report.id}.md")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    logger.info(f"Exported markdown report to {output_path}")
    return output_path


def export_pdf(report: FinalReport, output_path: Path | None = None) -> Path:
    """Export report to PDF using WeasyPrint."""
    if not HAS_WEASYPRINT:
        raise ImportError(
            "WeasyPrint is not installed or missing system dependencies (GTK/gobject). PDF export is unavailable."
        )

    # Generate HTML first
    html = generate_html(report)

    if output_path is None:
        output_path = Path(f"data/outputs/{report.id}.pdf")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # CSS for styling
    css = CSS(
        string="""
        @page {
            margin: 2cm;
            @bottom-center {
                content: counter(page);
            }
        }
        body {
            font-family: 'DejaVu Sans', 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
        }
        h1 { color: #1a1a2e; border-bottom: 2px solid #16213e; padding-bottom: 0.5rem; }
        h2 { color: #16213e; border-bottom: 1px solid #0f3460; padding-bottom: 0.3rem; margin-top: 2rem; }
        h3 { color: #0f3460; }
        .meta { color: #666; font-size: 0.9rem; margin-bottom: 2rem; }
        .section { margin-bottom: 2rem; }
        ul { padding-left: 1.5rem; }
        li { margin-bottom: 0.5rem; }
        .references { font-size: 0.85rem; }
        .references li { margin-bottom: 0.3rem; }
        pre { background: #f5f5f5; padding: 1rem; overflow-x: auto; }
        code { background: #f0f0f0; padding: 0.2rem 0.4rem; border-radius: 3px; }
    """
    )

    # Font configuration
    font_config = FontConfiguration()

    # Generate PDF
    HTML(string=html).write_pdf(
        output_path,
        stylesheets=[css],
        font_config=font_config,
    )

    logger.info(f"Exported PDF report to {output_path}")
    return output_path


def generate_html(report: FinalReport) -> str:
    """Generate HTML from report."""
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<meta charset='utf-8'>",
        f"<title>{report.title}</title>",
        "</head>",
        "<body>",
        f"<h1>{report.title}</h1>",
        "<div class='meta'>",
        f"<p><strong>Question:</strong> {getattr(report, 'question', 'N/A')}</p>",
        f"<p><strong>Generated:</strong> {report.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>",
        f"<p><strong>Report ID:</strong> {report.id}</p>",
        "</div>",
    ]

    html_parts.extend(
        [
            "<h2>Executive Summary</h2>",
            f"<p>{report.executive_summary}</p>",
        ]
    )

    if report.key_takeaways:
        html_parts.append("<h2>Key Takeaways</h2>")
        html_parts.append("<ul>")
        for takeaway in report.key_takeaways:
            html_parts.append(f"<li>{takeaway}</li>")
        html_parts.append("</ul>")

    for section in report.sections:
        html_parts.extend(
            [
                "<div class='section'>",
                f"<h2>{section.title}</h2>",
                f"<div>{section.content}</div>",
                "</div>",
            ]
        )

    if report.limitations:
        html_parts.append("<h2>Limitations</h2>")
        html_parts.append("<ul>")
        for limitation in report.limitations:
            html_parts.append(f"<li>{limitation}</li>")
        html_parts.append("</ul>")

    if report.future_work:
        html_parts.append("<h2>Future Work</h2>")
        html_parts.append("<ul>")
        for item in report.future_work:
            html_parts.append(f"<li>{item}</li>")
        html_parts.append("</ul>")

    if report.references:
        html_parts.append("<h2>References</h2>")
        html_parts.append("<ol class='references'>")
        for ref in report.references:
            html_parts.append(f"<li>{ref}</li>")
        html_parts.append("</ol>")

    html_parts.extend(["</body>", "</html>"])

    return "\n".join(html_parts)


def export_json(report: FinalReport, output_path: Path | None = None) -> Path:
    """Export report to JSON file."""
    import json

    data = report.model_dump(mode="json")

    if output_path is None:
        output_path = Path(f"data/outputs/{report.id}.json")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    logger.info(f"Exported JSON report to {output_path}")
    return output_path
