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
- Evaluated against a hand-authored eval set (`eval/`) on three axes:
  SQL answer accuracy, RAG groundedness, and tool-selection accuracy.
  Tool-selection accuracy is computed automatically; the other two are
  graded by hand-written logic, not automated -- deciding what counts
  as a correct answer is a judgment call.

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
- [x] FastAPI endpoint
- [x] Eval dataset (20 hand-written cases: 7 SQL, 7 RAG, 6 both)
- [x] Tool selection accuracy (automated, plain set comparison)
- [x] SQL fact accuracy (hybrid: free regex heuristic + LLM-judge fallback for ambiguous cases)
- [x] RAG groundedness (manual grading tool: `eval/grade_rag_manual.py`; grading itself not started)
- [x] Docker (Dockerfile + docker-compose, verified end-to-end)
- [x] Locked dependency versions (`requirements-lock.txt`, used by Docker build)
- [x] Unit tests (129 tests, 93% coverage on `app/`; mocked OpenAI/Anthropic/Chroma, no real API calls)
- [x] CI (`.github/workflows/ci.yml`): tests + `pip-audit` on every push/PR
- [x] Hardening: daily budget cap, explicit LLM timeouts/retries, non-root
      Docker user, request-id tracing, locked concurrent trace writes
- [x] `/chat` auth (optional API key) + per-IP rate limiting
- [x] `/ready` readiness probe (checks DB, Chroma, provider keys -- `/health` is liveness only)
- [x] Request validation: bounded question length, `provider` as an enum
- [x] Versioned/atomic Chroma ingestion (hash-based manifest, not directory existence)

## Tech stack

Python 3.13 · FastAPI · OpenAI SDK · Anthropic SDK · SQLite · Chroma · pydantic-settings

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
# or, for the exact versions this was built/tested against:
# pip install -r requirements-lock.txt && pip install --no-deps -e .

cp .env.example .env   # fill in OPENAI_API_KEY / ANTHROPIC_API_KEY

python -m app.sql.seed_data           # generates data/incidents.db
python -m app.rag.generate_postmortems  # generates app/rag/docs/incident_*.md
python -m app.rag.ingest              # embeds docs into data/chroma

uvicorn app.api.main:app --reload     # serves /chat, /health, /ready
```

### Or with Docker

```bash
cp .env.example .env   # fill in OPENAI_API_KEY / ANTHROPIC_API_KEY
docker compose up
```

First run seeds the DB, generates postmortems, and embeds the RAG corpus
inside the container (`docker-entrypoint.sh`) — same steps as above, just
automated. Data lands in a named volume (`triage_data`), not baked into the
image, so a restart doesn't re-run the (paid) embedding step; `docker compose
down -v` clears it if you want a clean regeneration.

## Running tests

```bash
pip install -e ".[dev]"
pytest --cov=app --cov-report=term-missing
```

Unit tests, not eval -- these check individual functions in isolation, not
end-to-end agent behavior (that's what `eval/` is for). No real OpenAI/
Anthropic/Chroma calls: provider adapters and `rag_tool`/`ingest` are tested
against mocked clients built with `unittest.mock`, so the suite runs free,
offline, and in about a second. `sql_tool` and `tracer` use real SQLite/file
I/O, but against `tmp_path` fixtures, never the actual `data/`.

## Project layout

```
app/
├── api/                 # FastAPI app
│   ├── main.py           # /chat, /health (liveness), /ready (readiness)
│   ├── rate_limiter.py   # in-memory per-IP sliding window
│   └── readiness.py      # DB / Chroma / provider-key checks for /ready
├── agent/               # the tool-calling loop
│   ├── loop.py          # run_agent() -- the turn-taking orchestration
│   ├── providers/       # openai_provider.py / anthropic_provider.py
│   ├── tool_specs.py    # what the model is told about each tool
│   ├── turn.py          # LLMTurn / AgentResult -- shared shapes
│   └── prompts.py       # system prompt
├── sql/                 # schema, synthetic data generation, sql_tool
├── rag/                 # chunking, ingestion, rag_tool, source docs
├── tracing/             # JSON Lines logging of every tool/LLM call
└── config.py            # typed settings from .env

eval/
├── schema.py             # EvalExample -- the dataset's row shape
├── run_eval.py           # runs the dataset, grades tool selection, writes results.jsonl
├── grade_sql.py          # free regex heuristic for SQL fact-checking
├── grade_sql_llm.py      # LLM-as-judge grader (same task, semantic understanding)
├── grade_sql_hybrid.py   # heuristic first, LLM judge only for flagged cases -- canonical
├── grade_rag_manual.py   # terminal tool for hand-scoring RAG groundedness
├── dataset.jsonl         # hand-authored eval questions (not code-generated)
├── results.jsonl         # generated by run_eval.py (gitignored)
├── sql_grades.jsonl      # generated by grade_sql_hybrid.py (gitignored)
└── rag_grades.jsonl      # hand-graded output -- NOT gitignored, it's judgment work

data/                     # generated artifacts: incidents.db, chroma/, traces.jsonl (gitignored)

tests/                    # unit tests -- see "Running tests" above

Dockerfile                # builds the FastAPI service image
docker-entrypoint.sh      # seeds/generates/embeds on first run, then serves
requirements-lock.txt     # exact resolved versions (pip freeze); pyproject.toml stays loose
docker-compose.yml        # app service + named volume for data/
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
- **`rag_tool`'s description tells the model not to put service names
  in its search query.** Found empirically: embedding a query like
  "OOM in payments-api" pulls results toward postmortems that mention
  "payments-api" by name, away from the generic runbook that's
  usually the better answer. Fixed at the prompt level, not by
  changing retrieval.
- **Cross-lingual RAG queries work, but degrade.** The corpus is
  English-only; a Russian query still retrieves relevant chunks
  (`text-embedding-3-small` is multilingual) but with consistently
  higher distance / lower confidence than the equivalent English
  query, and quality varies by topic. Not fixed -- noted as a known
  limitation, since "translate the query to English first" is a real
  design choice for a production version, not a one-line patch here.
- **`sql_tool`'s description explicitly says `resolved` and `closed`
  are both terminal statuses.** Found via eval: the agent inconsistently
  excluded `closed` incidents on aggregate questions ("how many X",
  "who resolved the most"), undercounting against the full data. Fixed
  at the prompt level (one clarifying paragraph, no schema/code
  change) -- verified by rerunning the full eval afterward: the two
  affected cases now pass (`execution_correct`/`answer_correct` went
  13/13 from 11/13 effective), and the other 18 cases were unaffected.
  This is the eval-driven loop the project is built around: find a
  concrete failure, form a hypothesis about the cause, apply the
  smallest fix that targets it, re-run the whole eval to confirm the
  fix and check for regressions.
- **`pyproject.toml` stays loose (`fastapi`, not `fastapi==0.141.1`);
  `requirements-lock.txt` (`pip freeze`) pins every resolved version,
  including transitive dependencies.** Two different jobs: the
  dependency list documents what the project conceptually needs,
  the lock file makes installs reproducible. Docker installs from the
  lock file specifically (`pip install -r requirements-lock.txt`,
  then the package itself with `--no-deps`) so the image doesn't
  silently drift to newer dependency versions on a future rebuild.
- **Daily budget circuit breaker.** `run_agent()` checks
  `tracer.cost_today_usd()` (sums `cost_usd`/`embedding_cost_usd` across
  today's trace entries) against `settings.daily_budget_usd` (default $5)
  before every LLM turn, not just once per request -- a single request
  making several tool-calling turns couldn't otherwise blow well past the
  limit before the check ran again. Raises `BudgetExceededError` -> API
  maps it to `429`.
- **Explicit LLM timeouts and retries.** Both SDKs default to a 600s read
  timeout and 2 retries -- fine defaults, but implicit and undocumented in
  this codebase. Now explicit in each provider's `build_client()`
  (`REQUEST_TIMEOUT_SECONDS = 30.0`, `MAX_RETRIES = 2`): a stuck call no
  longer ties up a threadpool worker for up to 10 minutes.
- **Non-root Docker user.** `Dockerfile` now creates `appuser` (uid 1000)
  and switches to it before `ENTRYPOINT`. The tricky part isn't the
  `USER` line itself -- it's that `/app/data` has to be `chown`'d to
  `appuser` *before* the volume mount takes it over, since Docker
  initializes a fresh named volume from the image directory's contents
  and ownership on first use.
- **Request-id tracing.** `run_agent()` generates one UUID per call and
  threads it through every `llm_call` and `tool_call` trace line for that
  request (`sql_tool`/`rag_tool` gained an optional `request_id` param
  just to carry it). Without this, concurrent requests interleave in
  `traces.jsonl` with no way to tell which lines belong together. Also
  returned in the `/chat` response so a client has a reference id to
  quote when reporting an issue.
- **Locked concurrent trace writes.** `tracer.log_event()` now takes an
  `flock` around the write -- FastAPI's threadpool means concurrent
  requests can call it at the same time, and a plain `open("a").write()`
  isn't guaranteed atomic once a line is long enough to cross a single
  `write()` syscall. Caveat, stated plainly: a 50-thread concurrent-write
  test couldn't actually reproduce corruption *without* the lock either,
  on this filesystem at this payload size -- the fix is still correct per
  POSIX (and necessary for larger payloads or networked filesystems), but
  the test is a concurrency smoke test, not a proven regression guard for
  this specific race.
- **`/chat` auth and rate limiting, found missing by an external
  production-readiness review.** `settings.service_api_key`, checked via
  an `X-API-Key` header dependency; unset by default (open, fine for
  local dev) so setting up auth isn't a precondition for running the
  project at all. Paired with a 20-req/min-per-IP in-memory limiter
  (`app/api/rate_limiter.py`) -- single-process only, matches the rest of
  this project's single-node architecture, would need a shared store
  behind multiple workers or replicas.
- **`/health` vs `/ready`, same review.** `/health` always returns `ok` --
  correct for a liveness probe (is the process up), wrong as the *only*
  check, since it stayed green with a missing DB, an empty Chroma
  collection, or no provider keys configured. `/ready`
  (`app/api/readiness.py`) actually checks those three and returns `503`
  if any fail.
- **Request validation, same review.** `question` now has a length bound
  (1-2000 chars) and `provider` is a `Literal["openai", "anthropic"]`
  instead of a free string -- invalid values are rejected by FastAPI
  before `run_agent()` is ever called, not after.
- **Failed LLM calls are now traced too.** `tracer.log_event()` for
  `llm_call` used to run only after `adapter.run_turn()` returned
  successfully -- a call that failed outright (SDK retries exhausted,
  auth error) left zero trace of the attempt. Now wrapped so the failure
  is logged (with the error and zero cost/tokens) before it propagates.
- **Postmortem root cause and resolution are drawn as a matching pair,
  not independently.** Found by the same review: `root_cause`,
  `resolution`, and `lessons` for a given issue type used to each get
  their own `random.choice()`, which could pair a described cause with a
  resolution that doesn't actually address it (e.g. "missing index"
  paired with "added a circuit breaker for a slow dependency"). Now one
  shared random index picks a coherent scenario across all three.
- **Chroma ingestion is now versioned by a content hash, not "does
  `data/chroma/` exist."** The old check meant a crash right after Chroma
  created that directory (before `collection.add()` finished) looked
  identical to a completed ingestion and would be silently skipped on
  every future start; a corpus edit with the old directory still present
  was ignored the same way. `app/rag/ingest.py` now writes a manifest
  (`corpus_hash`, `chunk_count`, `embedding_model`, timestamp) after a
  successful ingest, and `docker-entrypoint.sh` re-ingests whenever that
  hash doesn't match the current docs on disk.
- **`chromadb==1.5.9` has four open CVEs** (`pip-audit -r
  requirements-lock.txt`), no patched release available as of this
  writing. Their published exploit paths target Chroma's network
  API/auth providers; this project only ever uses an in-process
  `PersistentClient` and never runs `chromadb.HttpClient` or exposes a
  Chroma server, so the advisories don't appear reachable here -- stated
  as risk acceptance based on that reasoning, not proof, since it's an
  applicability inference rather than a verified non-exploitability
  claim. Revisit when a patched version ships.
