"""Interactive manual grading for rag_*/both_* eval cases. Shows the
question, the retrieved chunks, and the agent's final answer, then
asks for three 0-2 scores (context relevance, groundedness, answer
relevance) plus a hallucination flag. Resumable: already-graded ids
are skipped, and each grade is written immediately, so Ctrl+C loses
at most the case in progress.
"""

import json
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"
RESULTS_PATH = Path(__file__).resolve().parent / "results.jsonl"
OUTPUT_PATH = Path(__file__).resolve().parent / "rag_grades.jsonl"

RUBRIC = """
Context relevance -- do the retrieved chunks actually relate to the question?
  0 = chunks are unrelated       1 = partially relevant / noisy       2 = contain what's needed

Groundedness -- is every claim in the answer backed by the retrieved chunks?
  0 = significant unsupported claims   1 = core claim ok, extra/inaccurate details   2 = fully supported

Answer relevance -- does the answer actually address the question asked?
  0 = doesn't answer it           1 = partial / vague                  2 = direct, sufficient
"""


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prompt_score(label: str) -> int:
    while True:
        raw = input(f"{label} (0/1/2): ").strip()
        if raw in ("0", "1", "2"):
            return int(raw)
        print("  enter 0, 1, or 2")


def prompt_yn(label: str) -> bool:
    while True:
        raw = input(f"{label} (y/n): ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  enter y or n")


def print_summary(grades: list[dict]) -> None:
    if not grades:
        return
    n = len(grades)
    avg = lambda key: sum(g[key] for g in grades) / n
    hallucinated = sum(g["hallucinated_specific_fact"] for g in grades)
    print(f"\n{n} case(s) graded so far:")
    print(f"  avg context_relevance:  {avg('context_relevance'):.2f}")
    print(f"  avg groundedness:       {avg('groundedness'):.2f}")
    print(f"  avg answer_relevance:   {avg('answer_relevance'):.2f}")
    print(f"  hallucinated_specific_fact: {hallucinated}/{n}")


def main() -> None:
    dataset = {row["id"]: row for row in load_jsonl(DATASET_PATH)}
    results = {row["id"]: row for row in load_jsonl(RESULTS_PATH)}
    graded = load_jsonl(OUTPUT_PATH)
    already_graded_ids = {g["id"] for g in graded}

    todo = [
        id_
        for id_, example in dataset.items()
        if example["expected_tool"] in ("rag", "both") and id_ not in already_graded_ids
    ]

    if not todo:
        print("Nothing left to grade.")
        print_summary(graded)
        return

    print(RUBRIC)
    print(f"{len(todo)} case(s) to grade. Ctrl+C any time -- progress is saved after each case.\n")

    for id_ in todo:
        result = results[id_]
        print("=" * 70)
        print(f"[{id_}] {result['question']}\n")

        for call in result["tool_executions"]:
            if call["name"] != "rag_tool":
                continue
            print(f"rag_tool query: {call['arguments'].get('query')!r}")
            chunks = json.loads(call["result"])
            for i, chunk in enumerate(chunks, 1):
                meta = chunk["metadata"]
                print(f"  [{i}] {meta['source_file']} / {meta['section']} (distance={chunk['distance']:.3f})")
                print(f"      {chunk['text'][:200]}")
            print()

        print(f"ANSWER: {result['answer']}\n")

        grade = {
            "id": id_,
            "context_relevance": prompt_score("Context relevance"),
            "groundedness": prompt_score("Groundedness"),
            "answer_relevance": prompt_score("Answer relevance"),
            "hallucinated_specific_fact": prompt_yn("Hallucinated a specific fact (name/ID/number not in chunks)"),
            "notes": input("Notes (optional, Enter to skip): ").strip() or None,
        }

        with OUTPUT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(grade) + "\n")
        graded.append(grade)
        print(f"Saved. ({len(graded)}/{len(dataset)} total)\n")

    print_summary(graded)


if __name__ == "__main__":
    main()
