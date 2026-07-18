"""
Multi-Agent Research Lab — Streamlit dashboard.
Swiss Modernism 2.0 design language.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from src.ui.components import history, job_status, new_research, results, system_health
from src.ui.components.api_client import api_get, set_api_base
from src.ui.components.styling import inject_css

# ── Page Config ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="Multi-Agent Research Lab",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# ── Session State ──────────────────────────────────────────────────

if "active_page" not in st.session_state:
    st.session_state["active_page"] = "New Research"

PAGES = ["New Research", "Job Status", "Results", "History", "System Health"]

# ── Sidebar ────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        """
    <div style="padding: var(--space-4) 0; text-align: center;">
        <div style="font-size: 2rem; margin-bottom: var(--space-2);">🔬</div>
        <div style="font-family: var(--font-heading); font-size: var(--text-lg); font-weight: 600;">
            Multi-Agent<br>Research Lab
        </div>
        <div style="font-size: var(--text-xs); color: var(--color-muted-foreground); margin-top: var(--space-1);">
            v0.1.0
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    selection = st.session_state["active_page"]
    nav_index = PAGES.index(selection) if selection in PAGES else 0

    page = st.radio(
        "Navigation",
        PAGES,
        index=nav_index,
        label_visibility="collapsed",
    )
    st.session_state["active_page"] = page

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    api_url = st.text_input(
        "API URL",
        value=os.getenv("API_URL", "http://localhost:8000/api/v1"),
        label_visibility="collapsed",
        placeholder="API URL",
    )
    set_api_base(api_url)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 API Health", use_container_width=True):
            health = api_get("/health")
            if health:
                st.success(f"API: {health['status']}")
            else:
                st.error("API unreachable")
    with col2:
        if st.button("🗄️ DB Health", use_container_width=True):
            from src.ui.components.api_client import supabase_health

            ok = supabase_health()
            if ok:
                st.success("Supabase: connected")
            else:
                st.error("Supabase: unreachable")

    st.markdown(
        """
    <div style="margin-top: var(--space-6); padding: var(--space-3); font-size: var(--text-xs); color: var(--color-muted-foreground); text-align: center;">
        7 agents · Quality loops · Hybrid memory
    </div>
    """,
        unsafe_allow_html=True,
    )

# ── Pages ───────────────────────────────────────────────────────────

if page == "New Research":
    new_research.render()
elif page == "Job Status":
    job_status.render()
elif page == "Results":
    results.render()
elif page == "History":
    history.render()
elif page == "System Health":
    system_health.render()
