from pathlib import Path

import streamlit as st


def load_css() -> str:
    css_path = Path(__file__).resolve().parent.parent / "assets" / "css" / "design-tokens.css"
    return css_path.read_text(encoding="utf-8")


def inject_css():
    custom_css = load_css()
    st.markdown(f"<style>{custom_css}</style>", unsafe_allow_html=True)


def hero(icon: str, title: str, subtitle: str):
    st.markdown(
        f"""
    <div class="hero fade-in">
        <div class="hero-icon">{icon}</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """,
        unsafe_allow_html=True,
    )


def metric_card(value: str, label: str, delta: str | None = None):
    delta_class = ""
    delta_html = ""
    if delta:
        direction = "up" if not delta.startswith("-") else "down"
        delta_class = direction
        delta_html = f'<div class="metric-delta {direction}">{delta}</div>'
    st.markdown(
        f"""
    <div class="metric-card fade-in">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
        {delta_html}
    </div>
    """,
        unsafe_allow_html=True,
    )


def badge(text: str, variant: str = "neutral"):
    st.markdown(f'<span class="badge badge-{variant}">{text}</span>', unsafe_allow_html=True)


def status_dot(variant: str):
    return f'<span class="status-dot {variant}"></span>'


def card(title: str | None = None, key: str | None = None):
    def decorator(content_func):
        def wrapper(*args, **kwargs):
            container = st.container(key=key)
            with container:
                html_parts = ['<div class="card">']
                if title:
                    html_parts.append(
                        f'<div class="card-header"><span class="card-title">{title}</span></div>'
                    )
                html_parts.append('<div class="card-body">')
                st.markdown("".join(html_parts), unsafe_allow_html=True)
                content_func(*args, **kwargs)
                st.markdown("</div></div>", unsafe_allow_html=True)
            return container

        return wrapper

    return decorator


def section_label(text: str):
    st.markdown(f'<div class="section-label">{text}</div>', unsafe_allow_html=True)


def divider():
    st.markdown('<hr class="divider">', unsafe_allow_html=True)


def empty_state(icon: str, text: str, hint: str = ""):
    st.markdown(
        f"""
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <div class="empty-state-text">{text}</div>
        <div class="empty-state-hint">{hint}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def alert(message: str, variant: str = "info"):
    st.markdown(f'<div class="alert alert-{variant}">{message}</div>', unsafe_allow_html=True)


def tooltip(text: str):
    return f'<span title="{text}" style="border-bottom: 1px dashed var(--color-border); cursor: help;">{text}</span>'
