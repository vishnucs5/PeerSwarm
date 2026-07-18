from __future__ import annotations

import json
import os
from typing import Any

import httpx
import streamlit as st

from supabase import Client, create_client


def _get_supabase() -> Client | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if url and key:
        try:
            return create_client(url, key)
        except Exception:
            return None
    return None


def _get_api_base() -> str:
    if "api_base" not in st.session_state:
        st.session_state.api_base = os.getenv("API_URL", "http://localhost:8000/api/v1")
    return st.session_state.api_base


def set_api_base(url: str):
    st.session_state.api_base = url


def _get_auth_headers() -> dict[str, str]:
    headers = {}
    api_key_enabled = os.getenv("SECURITY_API_KEY_ENABLED", "false").lower() == "true"
    if api_key_enabled:
        api_keys_str = os.getenv("SECURITY_API_KEYS", "[]")
        try:
            api_keys = json.loads(api_keys_str)
            if isinstance(api_keys, list) and api_keys:
                headers["X-API-Key"] = api_keys[0]
            elif isinstance(api_keys, str) and api_keys:
                headers["X-API-Key"] = api_keys
        except Exception:
            cleaned = api_keys_str.strip("[]").strip("'\"").strip()
            if cleaned:
                headers["X-API-Key"] = cleaned
    return headers


def api_get(path: str) -> dict[str, Any] | None:
    """Fetch from backend API. Falls back to Supabase direct read for known endpoints."""
    try:
        r = httpx.get(
            f"{_get_api_base()}{path}",
            headers=_get_auth_headers(),
            timeout=30,
        )
        if r.status_code == 400:
            try:
                detail = r.json().get("detail", r.text)
                st.warning(detail)
            except Exception:
                st.error(f"API Error: {r.text}")
            return None
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        # Backend unreachable — try Supabase direct read
        return _supabase_fallback_get(path)
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(path: str, data: dict) -> dict[str, Any] | None:
    try:
        r = httpx.post(
            f"{_get_api_base()}{path}",
            json=data,
            headers=_get_auth_headers(),
            timeout=120.0,
        )
        if r.status_code == 400:
            try:
                detail = r.json().get("detail", r.text)
                st.warning(detail)
            except Exception:
                st.error(f"API Error: {r.text}")
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def _supabase_fallback_get(path: str) -> dict[str, Any] | None:
    """Direct Supabase read when backend is unreachable."""
    sb = _get_supabase()
    if not sb:
        return None

    try:
        # GET /research — list jobs
        if path == "/research" or path.startswith("/research?"):
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(path)
            params = parse_qs(parsed.query)
            status = params.get("status", [None])[0]
            limit = min(int(params.get("limit", [50])[0]), 200)

            query = sb.table("jobs").select("*").order("created_at", desc=True).limit(limit)
            if status and status != "all":
                query = query.eq("status", status)
            result = query.execute()
            jobs = [
                {
                    "job_id": j["id"],
                    "question": j["question"],
                    "status": j["status"],
                    "iteration": j.get("iteration", 0),
                    "max_iterations": j.get("max_iterations", 3),
                    "quality_score": j.get("quality_score"),
                    "tags": j.get("tags", []),
                    "priority": j.get("priority", "normal"),
                    "created_at": j.get("created_at"),
                    "updated_at": j.get("updated_at"),
                }
                for j in result.data
            ]
            return {"jobs": jobs, "total": len(jobs)}

        # GET /research/{id} — job status
        job_match = __import__("re").match(r"^/research/([a-f0-9-]+)$", path)
        if job_match:
            job_id = job_match.group(1)
            result = sb.table("jobs").select("*").eq("id", job_id).execute()
            if result.data:
                j = result.data[0]
                return {
                    "job_id": j["id"],
                    "question": j["question"],
                    "status": j["status"],
                    "iteration": j.get("iteration", 0),
                    "max_iterations": j.get("max_iterations", 3),
                    "quality_score": j.get("quality_score"),
                    "error": j.get("error"),
                    "tags": j.get("tags", []),
                    "priority": j.get("priority", "normal"),
                    "created_at": j.get("created_at"),
                    "updated_at": j.get("updated_at"),
                }
            return None

        # GET /research/{id}/result — job result
        result_match = __import__("re").match(r"^/research/([a-f0-9-]+)/result$", path)
        if result_match:
            job_id = result_match.group(1)
            result = sb.table("job_results").select("*").eq("job_id", job_id).execute()
            if result.data:
                r = result.data[0]
                return {
                    "question": r["question"],
                    "job_id": r["job_id"],
                    "executive_summary": r.get("executive_summary", ""),
                    "key_takeaways": r.get("key_takeaways", []),
                    "references": r.get("references", []),
                    "sections": r.get("sections", []),
                    "report_markdown": r.get("report_markdown", ""),
                    "report": r.get("report", {}),
                    "quality_score": r.get("quality_score"),
                    "duration_seconds": r.get("duration_seconds", 0),
                    "iterations": r.get("iterations", 0),
                }
            return None

    except Exception:
        pass

    return None


def supabase_health() -> bool:
    """Check if Supabase is reachable."""
    sb = _get_supabase()
    if not sb:
        return False
    try:
        sb.table("jobs").select("id").limit(1).execute()
        return True
    except Exception:
        return False
