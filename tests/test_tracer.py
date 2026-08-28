import json

import pytest

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


def test_log_event_concurrent_writes_do_not_corrupt_lines(tmp_path, monkeypatch):
    import concurrent.futures

    path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(tracer, "TRACE_LOG_PATH", path)

    n_writers = 50

    def write_one(i):
        # A large-ish field pushes the line past a single write() syscall
        # more reliably, which is exactly the condition that can interleave
        # without locking.
        tracer.log_event("tool_call", worker_id=i, padding="x" * 2000)

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_writers) as executor:
        list(executor.map(write_one, range(n_writers)))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == n_writers
    worker_ids = set()
    for line in lines:
        entry = json.loads(line)  # raises if a line got interleaved/corrupted
        worker_ids.add(entry["worker_id"])
    assert worker_ids == set(range(n_writers))


def test_cost_today_usd_no_file_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(tracer, "TRACE_LOG_PATH", tmp_path / "does_not_exist.jsonl")
    assert tracer.cost_today_usd() == 0.0


def test_cost_today_usd_sums_cost_usd_and_embedding_cost_usd(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(tracer, "TRACE_LOG_PATH", path)

    tracer.log_event("llm_call", cost_usd=1.5)
    tracer.log_event("tool_call", tool="rag", embedding_cost_usd=0.25)
    tracer.log_event("tool_call", tool="sql")  # no cost field at all

    assert tracer.cost_today_usd() == pytest.approx(1.75)


def test_cost_today_usd_ignores_entries_from_other_days(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(tracer, "TRACE_LOG_PATH", path)
    old_entry = json.dumps({"timestamp": "2020-01-01T00:00:00.000+00:00", "cost_usd": 100.0})
    path.write_text(old_entry + "\n", encoding="utf-8")

    tracer.log_event("llm_call", cost_usd=0.10)

    assert tracer.cost_today_usd() == pytest.approx(0.10)
