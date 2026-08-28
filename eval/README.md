# Eval dataset

`dataset.jsonl` — one JSON object per line, written by hand (not generated).
Fields, matching `eval/schema.py`:

| field | type | meaning |
|---|---|---|
| `id` | str | unique identifier, e.g. `"sql_001"` |
| `question` | str | the question to send to the agent |
| `expected_tool` | `"sql"` \| `"rag"` \| `"both"` | graded automatically — exact match against the actual tool(s) called |
| `provider` | str, optional | `"openai"` \| `"anthropic"`, defaults to `"anthropic"` |
| `expected_answer` | str, optional | for `sql`/`both` cases: the fact to check, e.g. `"10"` or `"Fact: 2 P1 payments-api incidents. Guidance must include ..."` — see grading below. For `rag` cases: yours to define, not read automatically. |
| `notes` | str, optional | freeform |

Example row (illustrative only — not a real eval case, replace with your own):

```json
{"id": "example_001", "question": "How many P1 incidents happened last quarter?", "expected_tool": "sql", "provider": "openai", "expected_answer": null, "notes": "placeholder"}
```

## Running

```bash
python -m eval.run_eval
```

Runs every example through `run_agent()`, prints tool-selection accuracy, and
writes `eval/results.jsonl` — one row per example with the question, the
actual tool(s) called, the full tool executions (arguments + raw result), the
final answer, and your `expected_answer`/`notes` passed through unchanged.

## What's graded, and how

- **Tool selection accuracy** — computed in `run_eval.py`. Plain set
  comparison (`expected_tool` vs. the actual tool names called), no judgment
  call involved.

- **SQL fact accuracy** (`sql_*`/`both_*` cases) — `grade_sql_hybrid.py` is the
  canonical grader, writing `eval/sql_grades.jsonl`. It grades two things
  separately per case:
  - `execution_correct` — did the SQL query's result actually establish the
    fact in `expected_answer` (for `both_*` cases, only the part before
    `"Guidance must include"` — the guidance itself is a RAG judgment call,
    not graded here)?
  - `answer_correct` — did the agent's final text correctly convey that fact,
    regardless of whether the SQL was right? (Catches "SQL was right, agent
    misreported it" as a distinct failure from "SQL was wrong.")

  It's a hybrid of two graders, run in order to keep cost near zero:
  1. `grade_sql.py` — a free regex heuristic: extracts numbers and
     name-like identifiers from the fact, checks their presence in the SQL
     query + result (`execution_correct`) and in the final answer
     (`answer_correct`). Fast, deterministic, but can't tell a literal DB
     value from a descriptive phrase in the question (e.g. it can't verify
     that `LIKE '%latency%'` covers "high-latency incidents").
  2. `grade_sql_llm.py` — an LLM-as-judge (`gpt-4o-mini`, ~$0.0001/case).
     Only invoked by the hybrid script for cases the heuristic couldn't
     confidently pass — so most of the dataset costs nothing, and the
     ambiguous minority gets a real semantic judgment instead of a wrong
     regex verdict.

  Run standalone graders directly if you want to compare methods:
  `python -m eval.grade_sql` (heuristic only) or
  `python -m eval.grade_sql_llm` (LLM judge on everything). Otherwise:
  `python -m eval.grade_sql_hybrid`

- **RAG groundedness** — not automated, by design: whether a RAG answer is
  grounded in the retrieved chunks is a judgment call without a single "fact"
  to check against, unlike the SQL case. `grade_rag_manual.py` is a terminal
  tool for doing that judgment by hand, not a grader:

  ```bash
  python -m eval.grade_rag_manual
  ```

  For each `rag_*`/`both_*` case it prints the question, every retrieved
  chunk (source, section, distance), and the agent's final answer, then asks
  for three 0-2 scores -- context relevance, groundedness, answer relevance
  -- plus a `hallucinated_specific_fact` yes/no flag (a made-up name, ID, or
  number is a distinct, worse failure than "somewhat ungrounded"). Resumable:
  already-graded ids are skipped, and each grade is written to
  `eval/rag_grades.jsonl` immediately, so interrupting loses at most the case
  in progress. Unlike the other generated eval files, `rag_grades.jsonl` is
  **not** gitignored -- it encodes real judgment work, not something a script
  can regenerate.
