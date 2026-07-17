"""
Analyst agent - synthesizes research findings into cohesive analysis.
"""
from __future__ import annotations

import json
from collections import defaultdict

from src.config import get_model_for_agent
from src.crew.agents.base import AgentContext, BaseAgent
from src.models.research import EvidenceType, FindingCluster, ResearchFinding, Synthesis
from src.utils.logger import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a Research Analyst synthesizing research findings into a coherent analysis.
Given findings from multiple researchers, produce a structured synthesis.

Output valid JSON:
{
  "executive_summary": "2-3 sentence summary",
  "key_insights": ["insight1", "insight2"],
  "limitations": ["limitation1"],
  "future_work": ["future direction"],
  "evidence_gaps": ["gap1"],
  "contradictions": ["contradiction1"]
}"""


class AnalystAgent(BaseAgent):
    """Analyst agent that synthesizes findings from all researchers."""

    def __init__(self, model: str | None = None, verbose: bool = False):
        from src.tools.citation_tool import get_citation_tool
        from src.tools.knowledge_base import get_kb_tool

        super().__init__(
            role="Research Analyst",
            goal="Synthesize research findings into coherent analysis, identify patterns and gaps",
            backstory="""You are a world-class research analyst who excels at synthesizing 
information from multiple sources. You identify themes, detect contradictions, 
find evidence gaps, and build a unified narrative from diverse findings. 
You think critically about source quality and the strength of evidence.""",
            tools=[
                get_kb_tool(),
                get_citation_tool(),
            ],
            model=model or get_model_for_agent("analyst"),
            verbose=verbose,
        )

    def execute(self, context: AgentContext, **kwargs) -> Synthesis:
        """Synthesize all research findings."""
        findings: list[ResearchFinding] = kwargs.get("findings", [])
        plan = kwargs.get("plan")

        logger.info(f"Analyzing {len(findings)} findings")

        clusters = self._cluster_findings(findings)
        llm_content = self._llm_synthesize(findings, context)
        synthesis = Synthesis(
            question=context.question,
            plan_id=plan.id if plan else "",
            executive_summary=llm_content.get("executive_summary") or self._generate_summary(findings, clusters),
            clusters=clusters,
            unified_narrative=self._build_narrative(clusters, findings),
            key_insights=llm_content.get("key_insights") or self._extract_insights(clusters),
            contradictions=llm_content.get("contradictions") or self._find_contradictions(clusters),
            evidence_gaps=llm_content.get("evidence_gaps") or self._identify_gaps(clusters),
            limitations=llm_content.get("limitations") or self._identify_limitations(findings),
            future_work=llm_content.get("future_work") or self._suggest_future_work(clusters, findings),
            all_findings=findings,
            citations=self._build_citations(findings),
        )

        logger.info(f"Synthesis complete: {len(synthesis.clusters)} clusters, {len(synthesis.key_insights)} insights")
        return synthesis

    def _llm_synthesize(self, findings: list[ResearchFinding], context: AgentContext) -> dict:
        """Generate synthesis content via LLM with fallback to empty dict."""
        findings_text = "\n".join(
            f"[{f.evidence_type.value}] {f.claim[:200]} (confidence: {f.confidence})"
            for f in findings[:15]
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Research question: {context.question}\n\nFindings:\n{findings_text}\n\nProduce synthesis JSON."},
        ]
        try:
            content, usage = self._llm_completion(messages, context)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]
            content = content.strip()
            return json.loads(content)
        except Exception as e:
            logger.warning(f"LLM synthesis failed ({e}), using heuristic fallback")
            return {}

    def _cluster_findings(self, findings: list[ResearchFinding]) -> list[FindingCluster]:
        """Group findings into thematic clusters."""
        if not findings:
            return []

        theme_map: dict[str, list[ResearchFinding]] = defaultdict(list)
        for finding in findings:
            main_tag = finding.tags[0] if finding.tags else "general"
            theme_map[main_tag].append(finding)

        # Only split if we have only one generic tag group
        if len(theme_map) <= 2 and "general" in theme_map and len(theme_map) == 1:
            theme_map["major_findings"] = findings[:len(findings)//2]
            theme_map["supporting_evidence"] = findings[len(findings)//2:]

        clusters = []
        for theme, cluster_findings in theme_map.items():
            cluster = FindingCluster(
                theme=theme.replace("_", " ").title(),
                findings=cluster_findings,
                summary=f"Cluster of {len(cluster_findings)} findings related to {theme}",
                contradictions=[],
                gaps=[],
                confidence=sum(f.confidence for f in cluster_findings) / max(len(cluster_findings), 1),
            )
            clusters.append(cluster)

        return clusters

    def _generate_summary(self, findings: list[ResearchFinding], clusters: list[FindingCluster]) -> str:
        """Generate executive summary."""
        if not clusters:
            return "No findings were generated. Unable to produce a summary."

        source_types = defaultdict(int)
        for f in findings:
            source_types[f.evidence_type.value] += 1

        source_summary = ", ".join(f"{k}: {v}" for k, v in source_types.items())
        return f"""Analysis of {len(findings)} findings across {len(clusters)} themes ({source_summary}).
The research identified {sum(len(c.findings) for c in clusters)} key evidence points 
organized around {len(clusters)} major themes."""

    def _build_narrative(self, clusters: list[FindingCluster], findings: list[ResearchFinding]) -> str:
        """Build a unified narrative from clusters."""
        if not clusters:
            return "Insufficient data to build a narrative."

        parts = []
        for i, cluster in enumerate(clusters):
            parts.append(f"{i+1}. {cluster.theme}: {cluster.summary}")

        return "\n".join(parts)

    def _extract_insights(self, clusters: list[FindingCluster]) -> list[str]:
        """Extract key insights from clusters."""
        insights = []
        for cluster in clusters:
            top_findings = sorted(cluster.findings, key=lambda f: f.confidence, reverse=True)[:2]
            for f in top_findings:
                if f.confidence >= 0.7:
                    insights.append(f.claim[:150])
        return insights[:5]

    def _find_contradictions(self, clusters: list[FindingCluster]) -> list[str]:
        """Identify contradictions across clusters."""
        contradictions = []
        for cluster in clusters:
            if cluster.contradictions:
                contradictions.extend(cluster.contradictions)
        return contradictions[:3]

    def _identify_gaps(self, clusters: list[FindingCluster]) -> list[str]:
        """Identify evidence gaps."""
        gaps = []
        for cluster in clusters:
            if cluster.gaps:
                gaps.extend(cluster.gaps)

        if not gaps and clusters:
            gaps.append("Consider expanding research to cover more recent developments")
        return gaps[:3]

    def _identify_limitations(self, findings: list[ResearchFinding]) -> list[str]:
        """Identify research limitations."""
        limitations = []
        if not findings:
            limitations.append("No findings available for analysis")
            return limitations

        if all(f.confidence < 0.7 for f in findings):
            limitations.append("Most findings have low confidence scores")

        if sum(1 for f in findings if f.evidence_type == EvidenceType.ACADEMIC_PAPER) < 2:
            limitations.append("Limited academic sources available")

        return limitations

    def _suggest_future_work(self, clusters: list[FindingCluster], findings: list[ResearchFinding]) -> list[str]:
        """Suggest future research directions."""
        suggestions = []
        for cluster in clusters:
            if cluster.gaps:
                for gap in cluster.gaps[:1]:
                    suggestions.append(f"Address gap: {gap}")
        return suggestions[:3]

    def _build_citations(self, findings: list[ResearchFinding]) -> dict[str, str]:
        """Build citation map."""
        citations = {}
        for f in findings:
            if f.citation:
                citations[f.id] = f.citation
        return citations


def create_analyst_agent(model: str | None = None, verbose: bool = False) -> AnalystAgent:
    return AnalystAgent(model=model, verbose=verbose)
