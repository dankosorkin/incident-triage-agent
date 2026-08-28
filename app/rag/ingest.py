"""Embeds chunked RAG docs (postmortems + runbooks) with the OpenAI
embeddings API and writes them into a local persistent Chroma
collection. Anthropic has no embeddings endpoint, so OpenAI is used
here regardless of which provider the agent later uses for tool
calling.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from openai import OpenAI

from app.config import settings
from app.rag.chunking import Chunk, chunk_document
from app.tracing.tracer import log_event

DOCS_DIR = Path(__file__).resolve().parent / "docs"
CHROMA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "chroma"
MANIFEST_PATH = CHROMA_PATH / "ingest_manifest.json"
COLLECTION_NAME = "incident_docs"
EMBEDDING_MODEL = "text-embedding-3-small"
# https://openai.com/api/pricing/ -- re-check before trusting this for real cost reporting
EMBEDDING_PRICE_PER_1M_TOKENS = 0.02


def compute_corpus_hash() -> str:
    hasher = hashlib.sha256()
    for path in sorted(DOCS_DIR.glob("*.md")):
        hasher.update(path.name.encode("utf-8"))
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def needs_ingestion() -> bool:
    """True if Chroma has never been populated for the corpus as it
    currently exists on disk. Checked by hash, not by "does data/chroma/
    exist" -- a crash right after PersistentClient creates that
    directory (before collection.add() finishes) used to look
    identical to a completed ingestion and would be silently skipped
    forever; a doc edit with the old directory still present would be
    ignored the same way.
    """
    if not MANIFEST_PATH.exists():
        return True
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    return manifest.get("corpus_hash") != compute_corpus_hash()


def write_manifest(chunk_count: int) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "corpus_hash": compute_corpus_hash(),
                "chunk_count": chunk_count,
                "embedding_model": EMBEDDING_MODEL,
                "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        ),
        encoding="utf-8",
    )


def load_chunks() -> list[Chunk]:
    chunks = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        chunks.extend(chunk_document(path.read_text(encoding="utf-8"), path.name))
    return chunks


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    start = time.perf_counter()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    latency_ms = (time.perf_counter() - start) * 1000

    tokens = response.usage.total_tokens
    cost_usd = tokens / 1_000_000 * EMBEDDING_PRICE_PER_1M_TOKENS

    log_event(
        "embedding_call",
        model=EMBEDDING_MODEL,
        input_count=len(texts),
        tokens=tokens,
        cost_usd=round(cost_usd, 6),
        latency_ms=round(latency_ms, 2),
    )
    return [item.embedding for item in response.data]


def main() -> None:
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks from {DOCS_DIR}")

    client = OpenAI(api_key=settings.openai_api_key)
    embeddings = embed_texts(client, [c.text for c in chunks])

    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    existing = {c.name for c in chroma_client.list_collections()}
    if COLLECTION_NAME in existing:
        chroma_client.delete_collection(COLLECTION_NAME)
    collection = chroma_client.create_collection(COLLECTION_NAME)

    collection.add(
        ids=[f"{c.metadata['source_file']}::{c.metadata['section']}" for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings,
        metadatas=[c.metadata for c in chunks],
    )
    write_manifest(len(chunks))

    print(f"Wrote {len(chunks)} chunks into Chroma collection '{COLLECTION_NAME}' at {CHROMA_PATH}")


if __name__ == "__main__":
    main()
