from unittest.mock import MagicMock

import chromadb.errors
import openai
import pytest

from app.rag import rag_tool


def make_fake_openai_client(embedding=None, tokens=10, raise_error=None):
    client = MagicMock()
    if raise_error:
        client.embeddings.create.side_effect = raise_error
    else:
        response = MagicMock()
        response.data = [MagicMock(embedding=embedding or [0.1, 0.2])]
        response.usage.total_tokens = tokens
        client.embeddings.create.return_value = response
    return client


def make_fake_chroma_client(query_result=None, raise_error=None):
    collection = MagicMock()
    if raise_error:
        collection.query.side_effect = raise_error
    else:
        collection.query.return_value = query_result
    chroma_client = MagicMock()
    chroma_client.get_collection.return_value = collection
    return chroma_client, collection


@pytest.fixture
def query_result():
    return {
        "documents": [["chunk one text", "chunk two text"]],
        "metadatas": [[{"source_file": "a.md"}, {"source_file": "b.md"}]],
        "distances": [[0.5, 0.8]],
    }


def test_search_returns_text_metadata_distance(monkeypatch, query_result):
    fake_openai = make_fake_openai_client()
    fake_chroma, collection = make_fake_chroma_client(query_result=query_result)

    monkeypatch.setattr(rag_tool, "OpenAI", lambda **kwargs: fake_openai)
    monkeypatch.setattr(rag_tool.chromadb, "PersistentClient", lambda **kwargs: fake_chroma)

    results = rag_tool.search("test query", top_k=2)

    assert results == [
        {"text": "chunk one text", "metadata": {"source_file": "a.md"}, "distance": 0.5},
        {"text": "chunk two text", "metadata": {"source_file": "b.md"}, "distance": 0.8},
    ]


def test_search_passes_top_k_and_embedding_to_chroma_query(monkeypatch, query_result):
    fake_openai = make_fake_openai_client(embedding=[0.9, 0.9])
    fake_chroma, collection = make_fake_chroma_client(query_result=query_result)

    monkeypatch.setattr(rag_tool, "OpenAI", lambda **kwargs: fake_openai)
    monkeypatch.setattr(rag_tool.chromadb, "PersistentClient", lambda **kwargs: fake_chroma)

    rag_tool.search("test query", top_k=3)

    collection.query.assert_called_once_with(query_embeddings=[[0.9, 0.9]], n_results=3)


def test_search_wraps_openai_error(monkeypatch):
    fake_openai = make_fake_openai_client(raise_error=openai.OpenAIError("rate limited"))
    monkeypatch.setattr(rag_tool, "OpenAI", lambda **kwargs: fake_openai)

    with pytest.raises(rag_tool.RAGToolError, match="rate limited"):
        rag_tool.search("test query")


def test_search_wraps_chroma_error(monkeypatch):
    fake_openai = make_fake_openai_client()
    fake_chroma, _ = make_fake_chroma_client(raise_error=chromadb.errors.NotFoundError("no such collection"))

    monkeypatch.setattr(rag_tool, "OpenAI", lambda **kwargs: fake_openai)
    monkeypatch.setattr(rag_tool.chromadb, "PersistentClient", lambda **kwargs: fake_chroma)

    with pytest.raises(rag_tool.RAGToolError):
        rag_tool.search("test query")


def test_search_traces_success_with_result_count_and_cost(monkeypatch, query_result):
    fake_openai = make_fake_openai_client(tokens=100)
    fake_chroma, _ = make_fake_chroma_client(query_result=query_result)
    monkeypatch.setattr(rag_tool, "OpenAI", lambda **kwargs: fake_openai)
    monkeypatch.setattr(rag_tool.chromadb, "PersistentClient", lambda **kwargs: fake_chroma)

    logged = []
    monkeypatch.setattr(rag_tool, "log_event", lambda event_type, **fields: logged.append(fields))

    rag_tool.search("test query", top_k=2)

    assert len(logged) == 1
    assert logged[0]["tool"] == "rag"
    assert logged[0]["result_count"] == 2
    assert logged[0]["embedding_tokens"] == 100
    assert logged[0]["error"] is None


def test_search_traces_failure_with_error_and_zero_results(monkeypatch):
    fake_openai = make_fake_openai_client(raise_error=openai.OpenAIError("boom"))
    monkeypatch.setattr(rag_tool, "OpenAI", lambda **kwargs: fake_openai)

    logged = []
    monkeypatch.setattr(rag_tool, "log_event", lambda event_type, **fields: logged.append(fields))

    with pytest.raises(rag_tool.RAGToolError):
        rag_tool.search("test query")

    assert logged[0]["result_count"] == 0
    assert "boom" in logged[0]["error"]
