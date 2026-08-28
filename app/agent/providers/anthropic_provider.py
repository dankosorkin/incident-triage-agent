"""Anthropic Messages API adapter. Normalizes the provider-specific
response shape (response.content as a list of text/tool_use blocks,
tool input already a parsed dict) into the agent loop's
provider-agnostic LLMTurn.

Anthropic takes the system prompt as its own top-level parameter, not
a message in the conversation -- unlike OpenAI, where it's just a
message with role "system". That difference is contained here so the
agent loop's message-building logic doesn't need to know about it.
"""

from anthropic import Anthropic

from app.agent.tool_specs import ToolSpec
from app.agent.turn import LLMTurn, ToolCallRequest
from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
# Same reasoning as openai_provider.py: SDK default read timeout is 600s,
# too long for a threadpool-blocking request; 2 retries is the SDK
# default, made explicit rather than left implicit.
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 2


def build_client() -> Anthropic:
    return Anthropic(
        api_key=settings.anthropic_api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=MAX_RETRIES
    )


def build_initial_messages(question: str) -> list[dict]:
    return [{"role": "user", "content": question}]


def run_turn(client: Anthropic, messages: list[dict], tools: list[ToolSpec]) -> LLMTurn:
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=[t.to_anthropic() for t in tools],
    )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    tool_calls = [
        ToolCallRequest(id=block.id, name=block.name, arguments=block.input)
        for block in response.content
        if block.type == "tool_use"
    ]

    return LLMTurn(
        text="\n".join(text_blocks) if text_blocks else None,
        tool_calls=tool_calls,
        raw_assistant_message={"role": "assistant", "content": [b.model_dump() for b in response.content]},
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def build_tool_result_messages(tool_calls: list[ToolCallRequest], results: list[str]) -> list[dict]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tc.id, "content": result}
                for tc, result in zip(tool_calls, results)
            ],
        }
    ]
