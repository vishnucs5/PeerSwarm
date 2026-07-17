from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_url: str | None = None
_key: str | None = None
_client: Client | None = None


def get_supabase() -> Client:
    global _client, _url, _key

    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL") or _url
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY") or _key

    if not url or not key:
        raise RuntimeError(
            "Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "in your .env file."
        )

    _url = url
    _key = key
    _client = create_client(url, key)
    return _client


def create_job(
    question: str,
    max_iterations: int = 3,
    tags: list[str] | None = None,
    priority: str = "normal",
) -> dict[str, Any]:
    sb = get_supabase()
    result = (
        sb.table("jobs")
        .insert({
            "question": question,
            "max_iterations": max_iterations,
            "tags": tags or [],
            "priority": priority,
            "status": "queued",
        })
        .execute()
    )
    return result.data[0]


def update_job(job_id: str, data: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    result = (
        sb.table("jobs")
        .update(data)
        .eq("id", job_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def get_job(job_id: str) -> dict[str, Any] | None:
    sb = get_supabase()
    result = (
        sb.table("jobs")
        .select("*")
        .eq("id", job_id)
        .execute()
    )
    return result.data[0] if result.data else None


def get_job_result(job_id: str) -> dict[str, Any] | None:
    sb = get_supabase()
    result = (
        sb.table("job_results")
        .select("*")
        .eq("job_id", job_id)
        .execute()
    )
    return result.data[0] if result.data else None


def list_jobs(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    sb = get_supabase()
    query = sb.table("jobs").select("*").order("created_at", desc=True).limit(limit)
    if status and status != "all":
        query = query.eq("status", status)
    result = query.execute()
    return result.data


def insert_result(job_id: str, data: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    result = (
        sb.table("job_results")
        .insert({**data, "job_id": job_id})
        .execute()
    )
    return result.data[0]
