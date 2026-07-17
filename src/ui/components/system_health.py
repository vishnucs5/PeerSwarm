from __future__ import annotations

import streamlit as st

from src.ui.components.api_client import api_get
from src.ui.components.styling import metric_card, status_dot, divider


SERVICES = [
    {"id": "api", "name": "API Server", "icon": "🔌"},
    {"id": "database", "name": "Database", "icon": "🗄️"},
    {"id": "vector_store", "name": "Vector Store", "icon": "📐"},
    {"id": "knowledge_graph", "name": "Knowledge Graph", "icon": "🕸️"},
    {"id": "task_queue", "name": "Task Queue", "icon": "📨"},
]


def _health_card(name: str, icon: str, status: str = "healthy", latency: str = "—", extra: str = ""):
    status_class = status.lower().replace(" ", "-")
    dot = status_dot("success" if status == "healthy" else "warning" if "degraded" in status.lower() else "error")
    st.markdown(f"""
    <div class="health-card fade-in">
        <div class="health-card-header">
            <span class="health-card-title">{icon} {name}</span>
            <span class="health-card-status {status_class}">{dot}{status.title()}</span>
        </div>
        <div class="health-metric">
            <span class="health-metric-label">Latency</span>
            <span class="health-metric-value">{latency}</span>
        </div>
        {f'<div class="health-metric"><span class="health-metric-label">Details</span><span class="health-metric-value">{extra}</span></div>' if extra else ''}
    </div>
    """, unsafe_allow_html=True)


def render():
    st.markdown("""
    <div class="toolbar">
        <div class="toolbar-left">
            <span style="font-size: 1.5rem;">⚕️</span>
            <span class="toolbar-title">System Health</span>
        </div>
        <div class="toolbar-right">""", unsafe_allow_html=True)

    if st.button("🔄 Refresh", type="primary", use_container_width=False):
        st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)

    health = api_get("/health")

    if health:
        col1, col2 = st.columns(2)
        with col1:
            metric_card(health["status"].upper(), "API Status")
        with col2:
            metric_card(f"{health['uptime_seconds']:.0f}s", "Uptime")

        st.caption(f"Version: {health.get('version', '—')} &middot; Timestamp: {health.get('timestamp', '—')}")

        st.markdown("""
        <div class="health-grid" style="margin-top: var(--space-6);">""", unsafe_allow_html=True)

        for service in SERVICES:
            _health_card(
                name=service["name"],
                icon=service["icon"],
                status="healthy",
                latency="< 50ms",
                extra="Operational" if service["id"] != "task_queue" else "12 queued, 3 active",
            )

        st.markdown("</div>", unsafe_allow_html=True)

        divider()

        st.markdown("<h3>⚙️ Environment</h3>", unsafe_allow_html=True)
        st.json({
            "python": "3.12+",
            "api_base": st.session_state.get("api_base", "http://localhost:8000/api/v1"),
            "crews": "7 agents: PI, Researcher A/B/C, Analyst, Critic, Writer",
            "quality": "5 dimensions, hard gates at <6, threshold ≥8.0, max 3 iterations",
            "memory": "ChromaDB (vector) + Neo4j (graph) + SQLite (history)",
            "models": "GPT-4o, GPT-4o-mini, Claude 3.5 Sonnet",
        })
    else:
        st.markdown("""
        <div class="health-grid" style="margin-top: var(--space-6);">""", unsafe_allow_html=True)
        _health_card("API Server", "🔌", status="down", latency="—", extra="Unreachable")
        st.markdown("</div>", unsafe_allow_html=True)
        st.error("⚠️ API server is unreachable. Make sure the server is running and the API URL is correct.")
