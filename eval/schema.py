"""Structure for one hand-written eval example. The dataset itself
(eval/dataset.jsonl) and any answer/groundedness grading logic are
written by hand, not generated here -- this only documents the shape.
"""

from dataclasses import dataclass


@dataclass
class EvalExample:
    id: str
    question: str
    expected_tool: str  # "sql" | "rag" | "both" -- graded automatically
    provider: str = "anthropic"
    expected_answer: str | None = None  # yours to define and grade
    notes: str | None = None
