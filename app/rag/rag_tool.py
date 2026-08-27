"""Semantic search over the RAG corpus: embeds the query, searches
Chroma for the top-k most similar chunks, returns text + metadata.
"""

import time

import chromadb
import chromadb.errors
import openai
from openai import OpenAI

from app.config import settings
from app.rag.ingest import (
    CHROMA_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_PRICE_PER_1M_TOKENS,
)
from app.tracing.tracer import log_event


class RAGToolError(Exception):
    pass


def search(query: str, top_k: int = 5) -> list[dict]:
    start = time.perf_counter()
    error = None
    results: list[dict] = []
    tokens = 0
    cost_usd = 0.0

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        embed_response = client.embeddings.create(model=EMBEDDING_MODEL, input=[query])
        tokens = embed_response.usage.total_tokens
        cost_usd = tokens / 1_000_000 * EMBEDDING_PRICE_PER_1M_TOKENS
        query_embedding = embed_response.data[0].embedding

        chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        collection = chroma_client.get_collection(COLLECTION_NAME)
        raw = collection.query(query_embeddings=[query_embedding], n_results=top_k)

        results = [
            {"text": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(raw["documents"][0], raw["metadatas"][0], raw["distances"][0])
        ]
        return results
    except (openai.OpenAIError, chromadb.errors.ChromaError) as exc:
        error = str(exc)
        raise RAGToolError(f"RAG search failed: {error}") from exc
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        log_event(
            "tool_call",
            tool="rag",
            query=query,
            top_k=top_k,
            result_count=len(results),
            embedding_tokens=tokens,
            embedding_cost_usd=round(cost_usd, 6),
            latency_ms=round(latency_ms, 2),
            error=error,
        )
