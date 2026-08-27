"""Runs eval/dataset.jsonl (hand-written -- see eval/README.md)
through the agent and writes raw results to eval/results.jsonl.

Tool selection accuracy is computed and printed here since it's a
plain set comparison against expected_tool. SQL-answer accuracy and
RAG groundedness are NOT graded here -- what counts as a correct
answer is a judgment call, not something to automate away. Write that
grading against eval/results.jsonl yourself, in a separate script.
"""

import json
from pathlib import Path

from app.agent.loop import run_agent
from eval.schema import EvalExample

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"
RESULTS_PATH = Path(__file__).resolve().parent / "results.jsonl"

EXPECTED_TOOLS = {
    "sql": {"sql_tool"},
    "rag": {"rag_tool"},
    "both": {"sql_tool", "rag_tool"},
}


def load_dataset() -> list[EvalExample]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"{DATASET_PATH} not found -- write your eval examples there first. "
            f"See eval/README.md for the format."
        )
    return [
        EvalExample(**json.loads(line))
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    examples = load_dataset()
    results = []
    correct_tool_selection = 0

    for example in examples:
        agent_result = run_agent(example.question, provider=example.provider)
        actual_tools = {te.name for te in agent_result.tool_executions}
        tool_selection_correct = actual_tools == EXPECTED_TOOLS[example.expected_tool]
        correct_tool_selection += tool_selection_correct

        print(f"[{'OK' if tool_selection_correct else 'MISS'}] {example.id}: {example.question}")

        results.append(
            {
                "id": example.id,
                "question": example.question,
                "provider": example.provider,
                "expected_tool": example.expected_tool,
                "actual_tools": sorted(actual_tools),
                "tool_selection_correct": tool_selection_correct,
                "answer": agent_result.answer,
                "tool_executions": [
                    {"name": te.name, "arguments": te.arguments, "result": te.result}
                    for te in agent_result.tool_executions
                ],
                "expected_answer": example.expected_answer,
                "notes": example.notes,
            }
        )

    RESULTS_PATH.write_text("\n".join(json.dumps(r) for r in results) + "\n", encoding="utf-8")

    print()
    print(f"Tool selection accuracy: {correct_tool_selection}/{len(examples)}")
    print(f"Full results written to {RESULTS_PATH}")
    print("SQL accuracy and RAG groundedness: write your own grading against that file.")


if __name__ == "__main__":
    main()
