import json
from unittest.mock import MagicMock

from app.rag import ingest


def _setup_docs_and_manifest(tmp_path, monkeypatch):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "runbook_a.md").write_text("# Runbook: A\n\n## Symptoms\n- x\n")
    manifest_path = tmp_path / "chroma" / "ingest_manifest.json"
    monkeypatch.setattr(ingest, "DOCS_DIR", docs_dir)
    monkeypatch.setattr(ingest, "MANIFEST_PATH", manifest_path)
    return docs_dir, manifest_path


def test_load_chunks_reads_all_markdown_files(tmp_path, monkeypatch):
    (tmp_path / "runbook_a.md").write_text("# Runbook: A\n\n## Symptoms\n- x\n")
    (tmp_path / "runbook_b.md").write_text("# Runbook: B\n\n## Symptoms\n- y\n\n## Prevention\n- z\n")
    monkeypatch.setattr(ingest, "DOCS_DIR", tmp_path)

    chunks = ingest.load_chunks()

    assert len(chunks) == 3  # 1 section from a, 2 sections from b
    sources = {c.metadata["source_file"] for c in chunks}
    assert sources == {"runbook_a.md", "runbook_b.md"}


def test_load_chunks_ignores_non_markdown_files(tmp_path, monkeypatch):
    (tmp_path / "runbook_a.md").write_text("# Runbook: A\n\n## Symptoms\n- x\n")
    (tmp_path / "notes.txt").write_text("not a doc")
    monkeypatch.setattr(ingest, "DOCS_DIR", tmp_path)

    chunks = ingest.load_chunks()

    assert len(chunks) == 1


def test_load_chunks_empty_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "DOCS_DIR", tmp_path)
    assert ingest.load_chunks() == []


def test_embed_texts_returns_embeddings_in_order():
    response = MagicMock()
    response.data = [MagicMock(embedding=[0.1, 0.2]), MagicMock(embedding=[0.3, 0.4])]
    response.usage.total_tokens = 20

    client = MagicMock()
    client.embeddings.create.return_value = response

    embeddings = ingest.embed_texts(client, ["text one", "text two"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    client.embeddings.create.assert_called_once_with(model=ingest.EMBEDDING_MODEL, input=["text one", "text two"])


def test_embed_texts_traces_cost_and_tokens(monkeypatch):
    logged = []
    monkeypatch.setattr(ingest, "log_event", lambda event_type, **fields: logged.append(fields))

    response = MagicMock()
    response.data = [MagicMock(embedding=[0.1])]
    response.usage.total_tokens = 1000

    client = MagicMock()
    client.embeddings.create.return_value = response

    ingest.embed_texts(client, ["one text"])

    assert len(logged) == 1
    assert logged[0]["tokens"] == 1000
    assert logged[0]["cost_usd"] == round(1000 / 1_000_000 * ingest.EMBEDDING_PRICE_PER_1M_TOKENS, 6)


def test_compute_corpus_hash_is_stable_for_same_content(tmp_path, monkeypatch):
    _setup_docs_and_manifest(tmp_path, monkeypatch)
    assert ingest.compute_corpus_hash() == ingest.compute_corpus_hash()


def test_compute_corpus_hash_changes_when_a_doc_changes(tmp_path, monkeypatch):
    docs_dir, _ = _setup_docs_and_manifest(tmp_path, monkeypatch)
    before = ingest.compute_corpus_hash()

    (docs_dir / "runbook_a.md").write_text("# Runbook: A\n\n## Symptoms\n- changed\n")

    assert ingest.compute_corpus_hash() != before


def test_needs_ingestion_true_when_no_manifest(tmp_path, monkeypatch):
    _setup_docs_and_manifest(tmp_path, monkeypatch)
    assert ingest.needs_ingestion() is True


def test_needs_ingestion_false_when_manifest_matches_current_corpus(tmp_path, monkeypatch):
    _setup_docs_and_manifest(tmp_path, monkeypatch)
    ingest.write_manifest(chunk_count=1)
    assert ingest.needs_ingestion() is False


def test_needs_ingestion_true_after_corpus_changes_even_with_manifest_present(tmp_path, monkeypatch):
    docs_dir, _ = _setup_docs_and_manifest(tmp_path, monkeypatch)
    ingest.write_manifest(chunk_count=1)

    (docs_dir / "runbook_a.md").write_text("# Runbook: A\n\n## Symptoms\n- changed\n")

    assert ingest.needs_ingestion() is True


def test_needs_ingestion_true_when_manifest_is_corrupt(tmp_path, monkeypatch):
    _, manifest_path = _setup_docs_and_manifest(tmp_path, monkeypatch)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("not valid json{{{", encoding="utf-8")

    assert ingest.needs_ingestion() is True


def test_write_manifest_records_hash_and_chunk_count(tmp_path, monkeypatch):
    _setup_docs_and_manifest(tmp_path, monkeypatch)

    ingest.write_manifest(chunk_count=42)

    manifest = json.loads(ingest.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["chunk_count"] == 42
    assert manifest["corpus_hash"] == ingest.compute_corpus_hash()
    assert manifest["embedding_model"] == ingest.EMBEDDING_MODEL
    assert "ingested_at" in manifest
