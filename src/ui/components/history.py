from __future__ import annotations

import streamlit as st

from src.ui.components.api_client import api_get
from src.ui.components.styling import empty_state


def _status_badge_html(status: str) -> str:
    variant_map = {
        "completed": "success",
        "running": "info",
        "queued": "neutral",
        "failed": "error",
        "cancelled": "neutral",
    }
    dot_map = {
        "completed": "success",
        "running": "warning",
        "queued": "muted",
        "failed": "error",
        "cancelled": "muted",
    }
    variant = variant_map.get(status.lower(), "neutral")
    dot = dot_map.get(status.lower(), "muted")
    return f'<span class="badge badge-{variant}"><span class="status-dot {dot}"></span>{status.upper()}</span>'


def render():
    st.markdown(
        """
    <div class="toolbar">
        <div class="toolbar-left">
            <span style="font-size: 1.5rem;">📜</span>
            <span class="toolbar-title">Research History</span>
        </div>
        <div class="toolbar-right">
            <div class="filter-group">
                <label class="form-label" style="margin-bottom: 0; white-space: nowrap;">Filter:</label>""",
        unsafe_allow_html=True,
    )

    status_filter = st.selectbox(
        "Status",
        ["all", "completed", "running", "queued", "failed"],
        label_visibility="collapsed",
        key="history_filter",
    )

    st.markdown(
        """
            </div>
        </div>
    </div>""",
        unsafe_allow_html=True,
    )

    jobs = api_get(
        f"/research?limit=50{'' if status_filter == 'all' else f'&status={status_filter}'}"
    )

    if not jobs or not jobs.get("jobs"):
        empty_state("📜", "No research history found", "Start a new research job to see it here!")
        return

    total = jobs.get("total", len(jobs["jobs"]))
    st.caption(f"Showing {len(jobs['jobs'])} of {total} total jobs")

    for job in jobs["jobs"]:
        qs = job.get("quality_score", {})
        score = f"{qs['overall']}/10" if qs else "—"

        st.markdown(
            f"""
        <div class="card" style="margin-bottom: var(--space-3); cursor: pointer;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--space-4);">
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 600; font-size: var(--text-sm); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        {job.get("question", "Untitled")[:120]}
                    </div>
                    <div style="font-size: var(--text-xs); color: var(--color-muted-foreground);">
                        ID: {job["job_id"]} &middot; Updated: {job.get("updated_at", "—")}
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: var(--space-4); flex-shrink: 0;">
                    <div style="text-align: center;">
                        <div style="font-size: var(--text-xs); color: var(--color-muted-foreground); margin-bottom: 2px;">Status</div>
                        {_status_badge_html(job["status"])}
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: var(--text-xs); color: var(--color-muted-foreground); margin-bottom: 2px;">Iteration</div>
                        <div style="font-weight: 600; font-size: var(--text-sm);">{job["iteration"]}/{job["max_iterations"]}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: var(--text-xs); color: var(--color-muted-foreground); margin-bottom: 2px;">Score</div>
                        <div style="font-weight: 600; font-size: var(--text-sm);">{score}</div>
                    </div>""",
            unsafe_allow_html=True,
        )

        col_v, col_d = st.columns([1, 1])
        with col_v:
            if st.button("👁️ View", key=f"view_{job['job_id']}", use_container_width=True):
                st.session_state["last_job"] = job["job_id"]
                st.session_state["active_page"] = "Job Status"
                st.rerun()
        with col_d:
            if st.button("📄 Report", key=f"report_{job['job_id']}", use_container_width=True):
                st.session_state["last_job"] = job["job_id"]
                st.session_state["active_page"] = "Results"
                st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)
