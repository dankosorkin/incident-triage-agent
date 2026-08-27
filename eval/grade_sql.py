"""Mechanical grading for the SQL fact in sql_*/both_* eval cases.

Not true execution accuracy (Spider-style row-set comparison) --
expected_answer is stored as free text ("search-api, 18 incidents"),
not a structured expected result, so this extracts numbers and
name-like identifiers from that text and checks their presence in (a)
the tool's query arguments + raw result combined (execution_correct)
and (b) the agent's final text answer (answer_correct). For "both" cases, only the part before
"Guidance must include" is checked -- the guidance itself is a
groundedness judgment call, graded by hand elsewhere.

Cases this can't confidently resolve are flagged uncertain=True for
manual review, not silently marked right or wrong.
"""

import json
import re
from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent / "results.jsonl"
DATASET_PATH = Path(__file__).resolve().parent / "dataset.jsonl"
OUTPUT_PATH = Path(__file__).resolve().parent / "sql_grades.jsonl"

NUMBER_RE = re.compile(r"-?\d+\.?\d*")
SERVICE_NAME_RE = re.compile(r"\b[a-z]+(?:-[a-z]+)+\b")
PERSON_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b")


def extract_fact(expected_answer: str) -> str:
    fact = expected_answer.split("Guidance must include")[0].strip()
    if fact.lower().startswith("fact:"):
        fact = fact[len("fact:") :].strip()
    return fact.rstrip(". ").strip()


def numbers_in(text: str) -> list[float]:
    return [float(n) for n in NUMBER_RE.findall(text)]


def identifiers_in(text: str) -> set[str]:
    return set(SERVICE_NAME_RE.findall(text)) | set(PERSON_NAME_RE.findall(text))


def fact_present_in(fact: str, target: str, tol: float = 0.01) -> tuple[bool, list[str]]:
    """Returns (all_present, missing_pieces)."""
    missing = []
    target_lower = target.lower()

    target_numbers = numbers_in(target)
    for n in numbers_in(fact):
        if not any(abs(n - tn) <= tol for tn in target_numbers):
            missing.append(f"number {n}")

    for ident in identifiers_in(fact):
        if ident.lower() not in target_lower:
            missing.append(f"identifier {ident!r}")

    return (len(missing) == 0, missing)


def main() -> None:
    dataset = {json.loads(l)["id"]: json.loads(l) for l in DATASET_PATH.read_text().splitlines() if l.strip()}
    results = [json.loads(l) for l in RESULTS_PATH.read_text().splitlines() if l.strip()]

    graded = []
    for result in results:
        example = dataset[result["id"]]
        expected_answer = example.get("expected_answer")
        if example["expected_tool"] not in ("sql", "both") or not expected_answer:
            continue

        fact = extract_fact(expected_answer)
        if not numbers_in(fact) and not identifiers_in(fact):
            graded.append({"id": result["id"], "fact": fact, "uncertain": True, "reason": "no checkable numbers/identifiers extracted"})
            continue

        # Only sql_tool executions -- rag_tool's raw chunk text is full of
        # unrelated numbers (dates, incident IDs, similarity distances)
        # that can coincidentally match a fact's number and produce a
        # false pass. This check is specifically about SQL execution.
        sql_executions = [te for te in result["tool_executions"] if te["name"] == "sql_tool"]
        raw_result_text = json.dumps(
            [{"arguments": te["arguments"], "result": te["result"]} for te in sql_executions]
        )
        execution_correct, exec_missing = fact_present_in(fact, raw_result_text)
        answer_correct, answer_missing = fact_present_in(fact, result["answer"])

        graded.append(
            {
                "id": result["id"],
                "fact": fact,
                "execution_correct": execution_correct,
                "execution_missing": exec_missing,
                "answer_correct": answer_correct,
                "answer_missing": answer_missing,
                "uncertain": False,
            }
        )

    OUTPUT_PATH.write_text("\n".join(json.dumps(g) for g in graded) + "\n", encoding="utf-8")

    checkable = [g for g in graded if not g["uncertain"]]
    exec_ok = sum(g["execution_correct"] for g in checkable)
    answer_ok = sum(g["answer_correct"] for g in checkable)
    uncertain = [g for g in graded if g["uncertain"]]

    print(f"Graded {len(checkable)} cases ({len(uncertain)} flagged uncertain -- review by hand):")
    print(f"  execution_correct: {exec_ok}/{len(checkable)}")
    print(f"  answer_correct:    {answer_ok}/{len(checkable)}")
    for g in graded:
        if g["uncertain"]:
            print(f"  [UNCERTAIN] {g['id']}: {g['reason']}")
        elif not g["execution_correct"] or not g["answer_correct"]:
            print(f"  [CHECK] {g['id']}: exec_missing={g['execution_missing']} answer_missing={g['answer_missing']}")
    print(f"Full grades written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
