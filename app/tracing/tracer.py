"""Append-only JSON Lines logger for tool/LLM call tracing."""

import fcntl
import json
from datetime import datetime, timezone
from pathlib import Path

TRACE_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "traces.jsonl"


def log_event(event_type: str, **fields) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event_type": event_type,
        **fields,
    }
    TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry) + "\n"
    # FastAPI runs sync routes in a threadpool, so concurrent requests can
    # call this at the same time. A plain open("a").write() is not
    # guaranteed atomic once the JSON line is long enough to cross a
    # single write() syscall, so two lines could interleave into one
    # corrupted line. flock() serializes writers across threads *and*
    # processes (e.g. multiple uvicorn workers) sharing this file.
    with TRACE_LOG_PATH.open("a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def cost_today_usd() -> float:
    """Sums cost_usd/embedding_cost_usd across today's trace entries
    (UTC). Used as the data source for the daily budget circuit
    breaker in loop.py -- traces.jsonl is already the source of truth
    for cost, so this doesn't need a separate counter to keep in sync.
    """
    if not TRACE_LOG_PATH.exists():
        return 0.0

    today = datetime.now(timezone.utc).date().isoformat()
    total = 0.0
    for line in TRACE_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if not entry.get("timestamp", "").startswith(today):
            continue
        total += entry.get("cost_usd") or 0
        total += entry.get("embedding_cost_usd") or 0
    return total
