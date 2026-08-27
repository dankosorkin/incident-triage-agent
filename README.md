# incident-triage-agent

An incident-triage assistant that answers questions using two different
data sources — a structured incidents database (SQL) and a set of
unstructured postmortems/runbooks (RAG) — and decides for itself, via
LLM tool calling, which source (or both) a question needs.

```
"How many P1 incidents were there in July?"       -> SQL
"What do I do about an OOM in payments-api?"       -> RAG
"Why did the July payments-api P1 take so long?"   -> both
```

## How it works

- **Structured source**: a SQLite table of incidents (time, service,
  severity, status, resolver) — synthetic but deterministic data.
- **Unstructured source**: incident postmortems and general runbooks,
  chunked, embedded, and stored in Chroma.
- An LLM (OpenAI or Anthropic, pluggable) chooses which tool(s) to call
  based on the question, rather than a hardcoded router.
- Every tool call and LLM call is traced (tool selected, latency,
  tokens, cost) to a local JSON Lines log.
- Evaluated against a hand-authored eval set on three axes: SQL answer
  accuracy, RAG groundedness, and tool-selection accuracy.

## Status

- [x] Project scaffold, venv, git
- [x] Dependency management (`pyproject.toml`, editable install)
- [x] Typed config loaded from `.env`
- [x] SQL: incidents schema + synthetic dataset (deterministic, fixed seed)
- [x] SQL: read-only query tool with tracing
- [x] RAG: postmortem/runbook corpus
- [x] RAG: chunking, embeddings, Chroma ingestion
- [x] RAG: retrieval tool
- [x] Agent: tool-calling routing loop
- [ ] FastAPI endpoint
- [ ] Eval harness + metrics

## Tech stack

Python 3.13 · FastAPI · OpenAI SDK · Anthropic SDK · SQLite · Chroma · pydantic-settings

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env   # fill in OPENAI_API_KEY / ANTHROPIC_API_KEY

python -m app.sql.seed_data   # generates data/incidents.db
```

## Project layout

```
app/
├── api/          # FastAPI routes
├── agent/        # tool-calling routing loop
├── tools/        # sql_tool, rag_tool — what the model can call
├── sql/          # schema, synthetic data generation, query tool
├── rag/          # chunking, embeddings, Chroma access, source docs
├── tracing/      # JSON Lines logging of every tool/LLM call
└── config.py     # typed settings from .env

eval/             # hand-authored eval dataset + metrics (not code-generated)
data/             # generated artifacts: incidents.db, chroma/, traces.jsonl (gitignored)
```

## Design notes

A few decisions that aren't obvious from the code alone:

- **Synthetic data is deterministic** (`random.seed(42)`, fixed calendar
  year) — an eval question like "how many P1s in July" needs to keep
  the same answer across reruns, so nothing about the dataset can be
  relative to "now".
- **SQL tool is read-only at two layers**: a `SELECT`-only check on the
  query string, plus a SQLite connection opened in `mode=ro`. The model
  generates the SQL, so this is treated as an untrusted-input boundary.
- **Tracing exists before the tools that use it**, not bolted on after —
  latency/error is logged on every SQL call already, including
  rejected and failed ones.
