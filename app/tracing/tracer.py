"""Append-only JSON Lines logger for tool/LLM call tracing."""

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
    with TRACE_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
