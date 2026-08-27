"""LLM-as-judge grading for the same sql_*/both_* fact-checking task
as grade_sql.py, for comparison against the regex heuristic. One
judge call per case grades both execution_correct and answer_correct
together (cheaper than two separate calls).
"""

import json
import time
from pathlib import Path

from openai import OpenAI

from app.config import settings
from app.tracing import tracer
from eval.grade_sql import extract_fact

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"
RESULTS_PATH = Path(__file__).resolve().parent / "results.jsonl"
OUTPUT_PATH = Path(__file__).resolve().parent / "sql_grades_llm.jsonl"

JUDGE_MODEL = "gpt-4o-mini"

JUDGE_PROMPT = """You are grading an AI agent's use of a database tool.

Fact that should be true: "{fact}"

The SQL query the agent ran, and what it returned:
{sql_json}

The agent's final answer to the user:
"{answer}"

Judge two things independently:
1. execution_correct: does the SQL query's result actually establish the fact
   (right filters, right computation, right value)?
2. answer_correct: does the agent's final answer correctly convey the fact to
   the user (regardless of whether the SQL was right)?

Respond with JSON only:
{{"execution_correct": true/false, "execution_reasoning": "one sentence",
  "answer_correct": true/false, "answer_reasoning": "one sentence"}}"""


def judge(client: OpenAI, fact: str, sql_executions: list[dict], answer: str) -> dict:
    sql_json = json.dumps([{"arguments": te["arguments"], "result": te["result"]} for te in sql_executions])
    prompt = JUDGE_PROMPT.format(fact=fact, sql_json=sql_json, answer=answer)

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    latency_ms = (time.perf_counter() - start) * 1000
    verdict = json.loads(response.choices[0].message.content)

    tracer.log_event(
        "llm_judge_call",
        model=JUDGE_MODEL,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        latency_ms=round(latency_ms, 2),
    )
    return verdict


def main() -> None:
    dataset = {json.loads(l)["id"]: json.loads(l) for l in DATASET_PATH.read_text().splitlines() if l.strip()}
    results = [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]
    client = OpenAI(api_key=settings.openai_api_key)

    graded = []
    for result in results:
        example = dataset[result["id"]]
        expected_answer = example.get("expected_answer")
        if example["expected_tool"] not in ("sql", "both") or not expected_answer:
            continue

        fact = extract_fact(expected_answer)
        sql_executions = [te for te in result["tool_executions"] if te["name"] == "sql_tool"]
        verdict = judge(client, fact, sql_executions, result["answer"])
        verdict["id"] = result["id"]
        verdict["fact"] = fact
        graded.append(verdict)

        marks = f"exec={'OK' if verdict['execution_correct'] else 'MISS'} answer={'OK' if verdict['answer_correct'] else 'MISS'}"
        print(f"[{marks}] {result['id']}: {fact}")

    OUTPUT_PATH.write_text("\n".join(json.dumps(g) for g in graded) + "\n", encoding="utf-8")

    exec_ok = sum(g["execution_correct"] for g in graded)
    answer_ok = sum(g["answer_correct"] for g in graded)
    print()
    print(f"execution_correct: {exec_ok}/{len(graded)}")
    print(f"answer_correct:    {answer_ok}/{len(graded)}")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
