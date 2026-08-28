"""Readiness checks for /ready -- distinct from /health (liveness).
/health only says the process is up; this actually touches the
dependencies the agent needs (DB, Chroma, provider keys) so a broken
deployment fails its readiness probe instead of reporting healthy.
"""

import chromadb

from app.config import settings
from app.rag.ingest import CHROMA_PATH, COLLECTION_NAME
from app.sql.sql_tool import SQLToolError, run_sql_query


def check_database() -> str:
    try:
        run_sql_query("SELECT 1")
        return "ok"
    except SQLToolError as exc:
        return f"error: {exc}"


def check_chroma() -> str:
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        collection = client.get_collection(COLLECTION_NAME)
        count = collection.count()
        return "ok" if count > 0 else "empty"
    except Exception as exc:
        # Broad on purpose: readiness must report a broken dependency,
        # never raise and take the probe endpoint itself down with it.
        return f"error: {exc}"


def check_provider_keys() -> str:
    if settings.openai_api_key or settings.anthropic_api_key:
        return "ok"
    return "missing"


def run_readiness_checks() -> dict[str, str]:
    return {
        "database": check_database(),
        "chroma": check_chroma(),
        "provider_keys": check_provider_keys(),
    }
