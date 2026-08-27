"""OpenAI Chat Completions adapter. Normalizes the provider-specific
response shape (message.tool_calls, arguments as a JSON string) into
the agent loop's provider-agnostic LLMTurn.
"""

import json

from openai import OpenAI

from app.agent.tool_specs import ToolSpec
from app.agent.turn import LLMTurn, ToolCallRequest
from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings

MODEL = "gpt-4o-mini"
MAX_TOKENS = 1024


def build_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def build_initial_messages(question: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]


def run_turn(client: OpenAI, messages: list[dict], tools: list[ToolSpec]) -> LLMTurn:
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=messages,
        tools=[t.to_openai() for t in tools],
    )
    message = response.choices[0].message

    tool_calls = [
        ToolCallRequest(id=tc.id, name=tc.function.name, arguments=json.loads(tc.function.arguments))
        for tc in (message.tool_calls or [])
    ]

    return LLMTurn(
        text=message.content,
        tool_calls=tool_calls,
        raw_assistant_message=message.model_dump(exclude_none=True),
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )


def build_tool_result_messages(tool_calls: list[ToolCallRequest], results: list[str]) -> list[dict]:
    return [
        {"role": "tool", "tool_call_id": tc.id, "content": result}
        for tc, result in zip(tool_calls, results)
    ]
