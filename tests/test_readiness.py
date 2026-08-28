from unittest.mock import MagicMock

from app.api import readiness
from app.sql.sql_tool import SQLToolError


def test_check_database_ok(monkeypatch):
    monkeypatch.setattr(readiness, "run_sql_query", lambda query: [{"1": 1}])
    assert readiness.check_database() == "ok"


def test_check_database_reports_error(monkeypatch):
    def raise_error(query):
        raise SQLToolError("db is gone")

    monkeypatch.setattr(readiness, "run_sql_query", raise_error)
    assert readiness.check_database() == "error: db is gone"


def test_check_chroma_ok_when_collection_has_rows(monkeypatch):
    collection = MagicMock()
    collection.count.return_value = 130
    client = MagicMock()
    client.get_collection.return_value = collection
    monkeypatch.setattr(readiness.chromadb, "PersistentClient", lambda **kwargs: client)

    assert readiness.check_chroma() == "ok"


def test_check_chroma_reports_empty_collection(monkeypatch):
    collection = MagicMock()
    collection.count.return_value = 0
    client = MagicMock()
    client.get_collection.return_value = collection
    monkeypatch.setattr(readiness.chromadb, "PersistentClient", lambda **kwargs: client)

    assert readiness.check_chroma() == "empty"


def test_check_chroma_reports_error_when_collection_missing(monkeypatch):
    client = MagicMock()
    client.get_collection.side_effect = Exception("no such collection")
    monkeypatch.setattr(readiness.chromadb, "PersistentClient", lambda **kwargs: client)

    assert readiness.check_chroma().startswith("error:")


def test_check_provider_keys_ok_with_at_least_one(monkeypatch):
    monkeypatch.setattr(readiness.settings, "openai_api_key", "sk-x")
    monkeypatch.setattr(readiness.settings, "anthropic_api_key", None)
    assert readiness.check_provider_keys() == "ok"


def test_check_provider_keys_missing_when_both_unset(monkeypatch):
    monkeypatch.setattr(readiness.settings, "openai_api_key", None)
    monkeypatch.setattr(readiness.settings, "anthropic_api_key", None)
    assert readiness.check_provider_keys() == "missing"


def test_run_readiness_checks_aggregates_all_three(monkeypatch):
    monkeypatch.setattr(readiness, "check_database", lambda: "ok")
    monkeypatch.setattr(readiness, "check_chroma", lambda: "ok")
    monkeypatch.setattr(readiness, "check_provider_keys", lambda: "ok")

    assert readiness.run_readiness_checks() == {"database": "ok", "chroma": "ok", "provider_keys": "ok"}
