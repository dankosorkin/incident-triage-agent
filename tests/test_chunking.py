from app.rag.chunking import chunk_document, parse_metadata_block

RUNBOOK_TEXT = """# Runbook: OOM Crash

## Symptoms
- Service process restarts unexpectedly.

## Prevention
- Set memory limits with headroom.
"""

POSTMORTEM_TEXT = """# Postmortem: payments-api: OOM crash

**Incident ID:** 42
**Service:** payments-api
**Severity:** P1
**Status:** resolved
**Opened:** 2025-01-01T00:00:00
**Resolved:** 2025-01-01T02:00:00
**Resolved by:** Alice Chen
**Duration:** 2h 0m

## Summary
payments-api experienced OOM crash.

## Resolution
Restarted the affected instances.
"""


def test_chunk_document_splits_on_section_headers():
    chunks = chunk_document(RUNBOOK_TEXT, "runbook_oom_crash.md")
    assert len(chunks) == 2
    assert [c.metadata["section"] for c in chunks] == ["Symptoms", "Prevention"]


def test_chunk_document_prepends_title_to_each_chunk():
    chunks = chunk_document(RUNBOOK_TEXT, "runbook_oom_crash.md")
    assert all(c.text.startswith("Runbook: OOM Crash") for c in chunks)


def test_chunk_document_detects_runbook_type():
    chunks = chunk_document(RUNBOOK_TEXT, "runbook_oom_crash.md")
    assert all(c.metadata["doc_type"] == "runbook" for c in chunks)
    assert all("incident_id" not in c.metadata for c in chunks)


def test_chunk_document_detects_postmortem_type_and_parses_metadata():
    chunks = chunk_document(POSTMORTEM_TEXT, "incident_42.md")
    assert all(c.metadata["doc_type"] == "postmortem" for c in chunks)
    assert all(c.metadata["incident_id"] == "42" for c in chunks)
    assert all(c.metadata["service"] == "payments-api" for c in chunks)
    assert all(c.metadata["resolved_by"] == "Alice Chen" for c in chunks)


def test_chunk_document_source_file_recorded():
    chunks = chunk_document(RUNBOOK_TEXT, "runbook_oom_crash.md")
    assert all(c.metadata["source_file"] == "runbook_oom_crash.md" for c in chunks)


def test_parse_metadata_block_ignores_non_matching_lines():
    block = "**Service:** payments-api\nsome unrelated line\n**Severity:** P1"
    metadata = parse_metadata_block(block)
    assert metadata == {"service": "payments-api", "severity": "P1"}


def test_parse_metadata_block_empty_input():
    assert parse_metadata_block("") == {}
