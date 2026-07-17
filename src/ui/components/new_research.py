from __future__ import annotations

import streamlit as st

from src.ui.components.api_client import api_post
from src.ui.components.styling import hero, section_label, divider


TEMPLATES = [
    {"icon": "📚", "title": "Literature Review", "desc": "Survey recent papers on a topic"},
    {"icon": "🔬", "title": "Technical Survey", "desc": "Compare architectures & methods"},
    {"icon": "📊", "title": "Market Analysis", "desc": "Analyze industry trends & players"},
    {"icon": "🧪", "title": "Experiment Design", "desc": "Plan methodology & evaluation"},
]


DEFAULT_QUESTIONS = [
    "What are the latest advances in retrieval-augmented generation for domain-specific applications?",
    "Compare transformer architectures for long-context language understanding",
    "Summarize recent breakthroughs in multimodal AI reasoning",
    "What are the key challenges in aligning large language models with human values?",
]


def render():
    hero("🔬", "Multi-Agent Research Lab", "Submit a question to the multi-agent research system with automated quality loops.")

    col_form, col_templates = st.columns([3, 2])

    with col_form:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        with st.form("research_form", clear_on_submit=False):
            question = st.text_area(
                "Research Question",
                placeholder="e.g., What are the latest advances in retrieval-augmented generation for domain-specific applications?",
                max_chars=2000,
                help="Enter your research question (minimum 10 characters)",
            )

            col1, col2 = st.columns(2)
            with col1:
                max_iter = st.slider("Max Iterations", 1, 5, 3, help="How many quality improvement cycles to run")
                tags = st.text_input("Tags", placeholder="rag, llm, survey", help="Comma-separated tags for categorization")

            with col2:
                threshold = st.slider("Quality Threshold", 5.0, 10.0, 8.0, 0.5, help="Minimum quality score to accept results")
                priority = st.selectbox("Priority", ["normal", "low", "high"], help="Job priority level")

            col_submit, col_draft = st.columns([3, 1])
            with col_submit:
                submitted = st.form_submit_button("🚀 Start Research", use_container_width=True, type="primary")
            with col_draft:
                st.form_submit_button("💾 Save Draft", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

        if submitted and question.strip():
            if len(question.strip()) < 10:
                st.error("Question must be at least 10 characters.")
            else:
                with st.spinner("Queuing research job..."):
                    result = api_post("/research", {
                        "question": question.strip(),
                        "max_iterations": max_iter,
                        "quality_threshold": threshold,
                        "tags": [t.strip() for t in tags.split(",") if t.strip()],
                        "priority": priority,
                    })
                if result:
                    st.session_state["last_job"] = result["job_id"]
                    st.session_state["active_page"] = "Job Status"
                    st.toast(f"🚀 Job {result['job_id']} queued successfully!", icon="✅")
                    st.rerun()

    with col_templates:
        st.markdown('<div class="card" style="margin-bottom: var(--space-4)">', unsafe_allow_html=True)
        st.markdown('<div class="card-header"><span class="card-title">📋 Quick Templates</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-body">', unsafe_allow_html=True)
        st.markdown('<div class="template-grid">', unsafe_allow_html=True)
        for t in TEMPLATES:
            st.markdown(f"""
            <div class="template-card" onclick="document.querySelector('textarea').value='{t['title']}'">
                <div class="template-card-icon">{t['icon']}</div>
                <div class="template-card-title">{t['title']}</div>
                <div class="template-card-desc">{t['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div></div></div>', unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header"><span class="card-title">💡 Example Questions</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-body">', unsafe_allow_html=True)
        for i, q in enumerate(DEFAULT_QUESTIONS):
            if st.button(f"{q[:70]}...", key=f"example_{i}", use_container_width=True):
                pass
        st.markdown('</div></div>', unsafe_allow_html=True)

    divider()

    st.markdown("""
    <div style="display: flex; gap: var(--space-6); flex-wrap: wrap; justify-content: center; padding: var(--space-4) 0;">
        <div style="text-align: center; font-size: var(--text-sm); color: var(--color-muted-foreground);">
            <span style="font-size: 1.5rem;">🧠</span><br>
            <strong>7 Agents</strong><br>
            PI, Researchers, Analyst, Critic, Writer
        </div>
        <div style="text-align: center; font-size: var(--text-sm); color: var(--color-muted-foreground);">
            <span style="font-size: 1.5rem;">🔄</span><br>
            <strong>Quality Loops</strong><br>
            Up to 5 iterations
        </div>
        <div style="text-align: center; font-size: var(--text-sm); color: var(--color-muted-foreground);">
            <span style="font-size: 1.5rem;">📐</span><br>
            <strong>5 Dimensions</strong><br>
            Hard gates at < 6/10
        </div>
        <div style="text-align: center; font-size: var(--text-sm); color: var(--color-muted-foreground);">
            <span style="font-size: 1.5rem;">🗄️</span><br>
            <strong>Hybrid Memory</strong><br>
            ChromaDB + Neo4j + SQLite
        </div>
    </div>
    """, unsafe_allow_html=True)
