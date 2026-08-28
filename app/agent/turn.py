"""Provider-agnostic representation of one LLM turn in the agent loop."""

from dataclasses import dataclass


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMTurn:
    text: str | None
    tool_calls: list[ToolCallRequest]
    raw_assistant_message: object
    input_tokens: int
    output_tokens: int


@dataclass
class ToolExecution:
    name: str
    arguments: dict
    result: str


@dataclass
class AgentResult:
    answer: str
    tool_executions: list[ToolExecution]
    request_id: str
