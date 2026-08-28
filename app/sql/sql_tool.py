"""Read-only SQL execution against the incidents database.

Queries may come from LLM tool calls, so writes are blocked at two
layers: a SELECT-only check here, and a read-only SQLite connection
as defense in depth if that check is ever bypassed.
"""

import sqlite3
import time
from pathlib import Path

from app.tracing.tracer import log_event

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "incidents.db"


class SQLToolError(Exception):
    pass


def run_sql_query(query: str, request_id: str | None = None) -> list[dict]:
    start = time.perf_counter()
    error = None
    rows: list[dict] = []
    conn = None

    try:
        if not query.strip().upper().startswith("SELECT"):
            raise SQLToolError("Only SELECT queries are allowed.")

        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(query).fetchall()]
        return rows
    except SQLToolError as exc:
        error = str(exc)
        raise
    except sqlite3.Error as exc:
        error = str(exc)
        raise SQLToolError(f"SQL query failed: {error}") from exc
    finally:
        # conn is only ever unset if the SELECT-only check rejected the
        # query before a connection was opened -- every other path
        # (success or sqlite3.Error) must still close it, including
        # when conn.execute() itself is what raised.
        if conn is not None:
            conn.close()
        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            "tool_call",
            tool="sql",
            request_id=request_id,
            query=query,
            row_count=len(rows),
            latency_ms=round(latency_ms, 2),
            error=error,
        )
