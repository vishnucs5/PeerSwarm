from __future__ import annotations

import json

import streamlit as st

from src.ui.components.api_client import api_get
from src.ui.components.styling import metric_card, divider, empty_state


def render():
    st.markdown("""
    <div class="toolbar">
        <div class="toolbar-left">
            <span style="font-size: 1.5rem;">📄</span>
            <span class="toolbar-title">Research Results</span>
        </div>
    </div>""", unsafe_allow_html=True)

    job_id = st.text_input(
        "Job ID",
        value=st.session_state.get("last_job", ""),
        key="result_job_id",
        placeholder="Enter the completed job ID...",
        label_visibility="collapsed",
    )

    if st.button("📂 Load Report", type="primary", use_container_width=False) and job_id:
        with st.spinner("Loading report..."):
            result = api_get(f"/research/{job_id}/result")
        if result:
            st.session_state["current_result"] = result
            st.rerun()

    result = st.session_state.get("current_result")
    if not result:
        empty_state("📄", "No report loaded", "Enter a completed job ID and click Load Report to view results.")
        return

    st.markdown(f"""
    <div class="card" style="margin-bottom: var(--space-6)">
        <div style="display: flex; align-items: center; gap: var(--space-3);">
            <span style="font-size: 1.5rem;">📄</span>
            <div>
                <div style="font-family: var(--font-heading); font-size: var(--text-2xl); font-weight: 600;">
                    {result.get('question', 'Research Report')[:100]}
                </div>
                <div style="font-size: var(--text-sm); color: var(--color-muted-foreground);">
                    Duration: {result.get('duration_seconds', 0):.0f}s &middot; Iterations: {result.get('iterations', 0)} &middot; ID: {job_id}
                </div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        qs = result.get("quality_score", {})
        metric_card(f"{qs.get('overall', '—')}/10", "Overall Quality")
    with col2:
        metric_card(f"{result.get('iterations', 0)}", "Iterations Completed")
    with col3:
        metric_card(f"{result.get('duration_seconds', 0):.0f}s", "Duration")
    with col4:
        refs = result.get("references", [])
        metric_card(f"{len(refs)}", "References")

    if qs:
        dims = qs.get("dimensions", {})
        if dims:
            overall = qs.get("overall", 0) / 10
            st.markdown(f"""
            <div class="progress-bar" style="margin-bottom: var(--space-4); height: 12px;">
                <div class="progress-fill {'success' if overall >= 0.7 else 'warning' if overall >= 0.4 else 'error'}" 
                     style="width: {overall * 100}%"></div>
            </div>""", unsafe_allow_html=True)
            dim_parts = [f"{k.replace('_', ' ').title()}: {v}/10" for k, v in dims.items()]
            st.caption(" | ".join(dim_parts))

    divider()

    executive_summary = result.get("executive_summary", "")
    if executive_summary:
        with st.expander("📋 Executive Summary", expanded=True):
            st.markdown(executive_summary)

    col_takeaways, col_refs = st.columns([1, 1])

    with col_takeaways:
        key_takeaways = result.get("key_takeaways", [])
        if key_takeaways:
            st.markdown("""
            <div class="card" style="margin-bottom: var(--space-4)">
                <div class="card-header"><span class="card-title">💡 Key Takeaways</span></div>
                <div class="card-body">""", unsafe_allow_html=True)
            for i, takeaway in enumerate(key_takeaways, 1):
                st.markdown(f"{i}. {takeaway}")
            st.markdown("</div></div>", unsafe_allow_html=True)

    with col_refs:
        references = result.get("references", [])
        if references:
            st.markdown("""
            <div class="card" style="margin-bottom: var(--space-4)">
                <div class="card-header"><span class="card-title">📚 References</span></div>
                <div class="card-body">""", unsafe_allow_html=True)
            for i, ref in enumerate(references, 1):
                st.markdown(f"{i}. {ref}")
            st.markdown("</div></div>", unsafe_allow_html=True)

    divider()

    sections = result.get("sections", [])
    if sections:
        st.markdown("<h3>📖 Full Report Sections</h3>", unsafe_allow_html=True)
        for section in sections:
            title = section.get("title", "Section")
            content = section.get("content", "")
            citations = section.get("citations", [])
            with st.expander(f"## {title}", expanded=False):
                st.markdown(content)
                if citations:
                    st.markdown("**Citations:** " + " ".join(f"[{j}]" for j, _ in enumerate(citations, 1)))
                    for j, c in enumerate(citations, 1):
                        st.caption(f"[{j}] {c}")

    divider()

    report_md = result.get("report_markdown")
    if report_md:
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "⬇ Download Report (Markdown)",
                report_md,
                file_name=f"research_{job_id}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_dl2:
            report_data = result.get("report", {})
            st.download_button(
                "⬇ Download Structured Data (JSON)",
                json.dumps(report_data, indent=2),
                file_name=f"research_{job_id}.json",
                mime="application/json",
                use_container_width=True,
            )

        with st.expander("📝 View Raw Markdown", expanded=False):
            st.code(report_md, language="markdown")
