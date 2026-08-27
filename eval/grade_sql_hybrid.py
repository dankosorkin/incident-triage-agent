"""Hybrid SQL fact grading: the free regex heuristic (grade_sql.py)
runs first; only cases it can't confidently resolve (flagged
uncertain, or execution_correct/answer_correct False) get escalated
to the LLM judge (grade_sql_llm.py). Confident heuristic verdicts are
kept as-is, at zero extra cost -- only the ambiguous minority pay for
a judge call. This is the canonical output: eval/sql_grades.jsonl.
"""

import json
from pathlib import Path

from openai import OpenAI

from app.config import settings
from eval.grade_sql import extract_fact, fact_present_in, identifiers_in, numbers_in
from eval.grade_sql_llm import judge

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"
RESULTS_PATH = Path(__file__).resolve().parent / "results.jsonl"
OUTPUT_PATH = Path(__file__).resolve().parent / "sql_grades.jsonl"


def main() -> None:
    dataset = {json.loads(l)["id"]: json.loads(l) for l in DATASET_PATH.read_text().splitlines() if l.strip()}
    results = [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]
    client = OpenAI(api_key=settings.openai_api_key)

    graded = []
    escalated = 0

    for result in results:
        example = dataset[result["id"]]
        expected_answer = example.get("expected_answer")
        if example["expected_tool"] not in ("sql", "both") or not expected_answer:
            continue

        fact = extract_fact(expected_answer)
        sql_executions = [te for te in result["tool_executions"] if te["name"] == "sql_tool"]

        if not numbers_in(fact) and not identifiers_in(fact):
            # Heuristic has nothing to check at all -- always escalate.
            verdict = judge(client, fact, sql_executions, result["answer"])
            verdict.update(id=result["id"], fact=fact, method="llm_judge")
            escalated += 1
        else:
            raw_result_text = json.dumps(
                [{"arguments": te["arguments"], "result": te["result"]} for te in sql_executions]
            )
            execution_correct, exec_missing = fact_present_in(fact, raw_result_text)
            answer_correct, answer_missing = fact_present_in(fact, result["answer"])

            if execution_correct and answer_correct:
                verdict = {
                    "id": result["id"],
                    "fact": fact,
                    "execution_correct": True,
                    "execution_reasoning": "heuristic: all expected numbers/identifiers present",
                    "answer_correct": True,
                    "answer_reasoning": "heuristic: all expected numbers/identifiers present",
                    "method": "heuristic",
                }
            else:
                # Heuristic flagged something -- let the judge decide for real.
                verdict = judge(client, fact, sql_executions, result["answer"])
                verdict.update(
                    id=result["id"],
                    fact=fact,
                    method="llm_judge",
                    heuristic_flagged=True,
                    heuristic_exec_missing=exec_missing,
                    heuristic_answer_missing=answer_missing,
                )
                escalated += 1

        graded.append(verdict)
        marks = f"exec={'OK' if verdict['execution_correct'] else 'MISS'} answer={'OK' if verdict['answer_correct'] else 'MISS'}"
        print(f"[{marks}] ({verdict['method']}) {result['id']}: {fact}")

    OUTPUT_PATH.write_text("\n".join(json.dumps(g) for g in graded) + "\n", encoding="utf-8")

    exec_ok = sum(g["execution_correct"] for g in graded)
    answer_ok = sum(g["answer_correct"] for g in graded)
    print()
    print(f"execution_correct: {exec_ok}/{len(graded)}")
    print(f"answer_correct:    {answer_ok}/{len(graded)}")
    print(f"Escalated to LLM judge: {escalated}/{len(graded)} (rest graded free by heuristic)")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
