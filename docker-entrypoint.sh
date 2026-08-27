#!/bin/sh
set -e

if [ ! -f data/incidents.db ]; then
    echo "Seeding incidents database..."
    python -m app.sql.seed_data
fi

if [ -z "$(ls app/rag/docs/incident_*.md 2>/dev/null)" ]; then
    echo "Generating postmortems..."
    python -m app.rag.generate_postmortems
fi

if [ ! -d data/chroma ]; then
    echo "Embedding RAG corpus into Chroma..."
    python -m app.rag.ingest
fi

exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000
