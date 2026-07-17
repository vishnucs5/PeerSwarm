from __future__ import annotations

import streamlit as st

from src.ui.components.api_client import api_get
from src.ui.components.styling import metric_card, status_dot


PIPELINE_STEPS = [
    {"id": "planning", "label": "Planning", "icon": "📋"},
    {"id": "researching", "label": "Researching", "icon": "🔍"},
    {"id": "analyzing", "label": "Analyzing", "icon": "📊"},
    {"id": "evaluating", "label": "Evaluating", "icon": "⭐"},
    {"id": "writing", "label": "Writing", "icon": "✍️"},
]

AGENTS = [
    {"id": "researcher_a", "name": "Researcher A", "role": "Academic Sources", "icon": "📚", "source": "arXiv & Semantic Scholar"},
    {"id": "researcher_b", "name": "Researcher B", "role": "Web Search", "icon": "🌐", "source": "Search Engines & Web"},
    {"id": "researcher_c", "name": "Researcher C", "role": "Knowledge Base", "icon": "🗃️", "source": "ChromaDB & Neo4j"},
]

STEP_ORDER = [s["id"] for s in PIPELINE_STEPS]


def _get_step_state(step_id: str, current_step: str):
    if current_step == "failed":
        return "failed"
    if current_step in ("completed", "cancelled"):
        return "done"
    try:
        current_idx = STEP_ORDER.index(current_step)
    except ValueError:
        return "queued"
    try:
        step_idx = STEP_ORDER.index(step_id)
    except ValueError:
        return "queued"
    if step_idx < current_idx:
        return "done"
    if step_idx == current_idx:
        return "active"
    return "queued"


def _render_pipeline(current_step: str):
    pipeline_html = '<div class="pipeline">'
    for i, step in enumerate(PIPELINE_STEPS):
        state = _get_step_state(step["id"], current_step)
        pipeline_html += f"""
        <div class="pipeline-step {state}">
            <div class="pipeline-node">{step["icon"]}</div>
            <div class="pipeline-label">{step["label"]}</div>
        </div>
        """
        if i < len(PIPELINE_STEPS) - 1:
            connector_state = "done" if state == "done" else "active" if state == "active" else ""
            pipeline_html += f'<div class="pipeline-connector {connector_state}"></div>'
    pipeline_html += '</div>'
    st.markdown(pipeline_html, unsafe_allow_html=True)


def _render_parallel_agents():
    st.markdown("""
    <div class="agent-grid">""", unsafe_allow_html=True)
    for agent in AGENTS:
        st.markdown(f"""
        <div class="agent-card active">
            <div class="agent-card-header">
                <div class="agent-icon">{agent["icon"]}</div>
                <div>
                    <div class="agent-name">{agent["name"]}</div>
                    <div class="agent-role">{agent["role"]}</div>
                </div>
            </div>
            <div class="agent-stats">
                <span>🔍 Querying {agent["source"]}...</span>
            </div>
            <div style="margin-top: var(--space-2)">
                <span class="agent-status running">⏳ RUNNING</span>
            </div>
        </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render():
    st.markdown("""
    <div class="toolbar">
        <div class="toolbar-left">
            <span style="font-size: 1.5rem;">📊</span>
            <span class="toolbar-title">Job Status</span>
        </div>
    </div>""", unsafe_allow_html=True)

    job_id = st.text_input(
        "Job ID",
        value=st.session_state.get("last_job", ""),
        placeholder="Enter your research job ID...",
        label_visibility="collapsed",
    )

    col_refresh, col_view = st.columns([1, 5])
    with col_refresh:
        refresh = st.button("🔄 Refresh", use_container_width=True, type="primary")
    with col_view:
        st.markdown(
            f'<div style="padding: 7px 0; font-size: var(--text-sm); color: var(--color-muted-foreground);">'
            f'Enter a job ID above and click Refresh to see live status.</div>',
            unsafe_allow_html=True,
        )

    if (refresh or job_id) and job_id and len(job_id) >= 4:
        status = api_get(f"/research/{job_id}")
        if status:
            current_step = status["status"].lower()

            elapsed = status.get("elapsed_time", 0)
            estimated = status.get("estimated_total_seconds", 0)
            remaining = max(0, round(estimated - elapsed, 1)) if estimated else 0

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                metric_card(status["status"].upper(), "Status")
            with col2:
                metric_card(f"{status['iteration']}/{status['max_iterations']}", "Iteration")
            with col3:
                qs = status.get("quality_score")
                metric_card(f"{qs['overall']}/10" if qs else "—", "Quality")
            with col4:
                if current_step in ("completed", "failed", "cancelled"):
                    metric_card("✓ Done", "Remaining")
                else:
                    metric_card(f"~{remaining}s", "Remaining")

            if status.get("error"):
                st.error(f"Error: {status['error']}")

            st.markdown("### 🤖 Pipeline Progress")
            _render_pipeline(current_step)

            if current_step == "researching":
                st.markdown("### ⚡ Parallel Research Agents")
                _render_parallel_agents()

            if current_step not in ("completed", "failed", "cancelled") and estimated > 0:
                progress = max(0, min(100, int((elapsed / estimated) * 100)))
                st.markdown(f"""
                <div class="eta-bar">
                    <span class="eta-label">⏱️ Estimated Time</span>
                    <div class="eta-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {progress}%"></div>
                        </div>
                    </div>
                    <span class="eta-time">~{remaining}s remaining</span>
                </div>""", unsafe_allow_html=True)

            if qs := status.get("quality_score"):
                dims = qs.get("dimensions", {})
                if dims:
                    st.markdown("### 📐 Quality Dimensions")
                    dim_cols = st.columns(len(dims))
                    for i, (dim, val) in enumerate(dims.items()):
                        with dim_cols[i]:
                            metric_card(f"{val}/10", dim.replace("_", " ").title())

            if status["status"] == "completed":
                st.success("✅ Research complete!")
                if st.button("📄 View Report", type="primary", use_container_width=True):
                    st.session_state["active_page"] = "Results"
                    st.rerun()
        else:
            st.warning(f"Job {job_id} not found or API unreachable.")
    elif refresh and (not job_id or len(job_id) < 4):
        st.info("Enter a valid job ID to check status.")
