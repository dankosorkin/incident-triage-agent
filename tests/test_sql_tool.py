import sqlite3

import pytest

from app.sql import sql_tool
from app.sql.sql_tool import SQLToolError, run_sql_query


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE incidents (id INTEGER PRIMARY KEY, severity TEXT)")
    conn.executemany("INSERT INTO incidents (severity) VALUES (?)", [("P1",), ("P2",), ("P1",)])
    conn.commit()
    conn.close()
    monkeypatch.setattr(sql_tool, "DB_PATH", db_path)
    return db_path


def test_run_sql_query_returns_rows_as_dicts(temp_db):
    rows = run_sql_query("SELECT * FROM incidents WHERE severity = 'P1'")
    assert rows == [{"id": 1, "severity": "P1"}, {"id": 3, "severity": "P1"}]


def test_run_sql_query_rejects_non_select(temp_db):
    with pytest.raises(SQLToolError, match="Only SELECT"):
        run_sql_query("DROP TABLE incidents")


def test_run_sql_query_rejects_delete(temp_db):
    with pytest.raises(SQLToolError):
        run_sql_query("DELETE FROM incidents")


def test_run_sql_query_connection_is_actually_read_only(temp_db):
    # Defense in depth: even if the string check were bypassed, the
    # connection itself should refuse writes.
    with pytest.raises(SQLToolError):
        run_sql_query("SELECT 1; DROP TABLE incidents;")


def test_run_sql_query_invalid_sql_raises_sqltoolerror(temp_db):
    with pytest.raises(SQLToolError):
        run_sql_query("SELECT * FROM nonexistent_table")


def test_run_sql_query_closes_connection_on_success_and_on_error(temp_db, monkeypatch):
    # Regression test: conn.execute() raising used to skip conn.close(),
    # leaking the connection on every failed query.
    real_connect = sqlite3.connect
    opened_connections = []

    def spying_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        opened_connections.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", spying_connect)

    run_sql_query("SELECT * FROM incidents")
    with pytest.raises(SQLToolError):
        run_sql_query("SELECT * FROM nonexistent_table")

    assert len(opened_connections) == 2
    for conn in opened_connections:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")  # closed connections refuse to execute


def test_run_sql_query_traces_call(temp_db, tmp_path, monkeypatch):
    from app.tracing import tracer

    trace_path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(tracer, "TRACE_LOG_PATH", trace_path)

    run_sql_query("SELECT COUNT(*) as n FROM incidents")

    assert trace_path.exists()
    import json

    entry = json.loads(trace_path.read_text().splitlines()[0])
    assert entry["event_type"] == "tool_call"
    assert entry["tool"] == "sql"
    assert entry["error"] is None
