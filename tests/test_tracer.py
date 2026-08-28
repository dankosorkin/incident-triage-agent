import json

from app.tracing import tracer


def test_log_event_writes_json_line(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(tracer, "TRACE_LOG_PATH", path)

    tracer.log_event("tool_call", tool="sql", latency_ms=1.23)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event_type"] == "tool_call"
    assert entry["tool"] == "sql"
    assert entry["latency_ms"] == 1.23
    assert "timestamp" in entry


def test_log_event_appends_multiple_calls(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(tracer, "TRACE_LOG_PATH", path)

    tracer.log_event("tool_call", tool="sql")
    tracer.log_event("llm_call", provider="openai")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["tool"] == "sql"
    assert json.loads(lines[1])["provider"] == "openai"


def test_log_event_creates_parent_directory(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "dir" / "traces.jsonl"
    monkeypatch.setattr(tracer, "TRACE_LOG_PATH", path)

    tracer.log_event("tool_call")

    assert path.exists()
