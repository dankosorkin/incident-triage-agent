from unittest.mock import MagicMock

from app.agent.providers import anthropic_provider
from app.agent.turn import ToolCallRequest


def make_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    block.model_dump.return_value = {"type": "text", "text": text}
    return block


def make_tool_use_block(block_id, name, tool_input):
    block = MagicMock()
    block.type = "tool_use"
    block.id = block_id
    block.name = name
    block.input = tool_input
    block.model_dump.return_value = {"type": "tool_use", "id": block_id, "name": name, "input": tool_input}
    return block


def make_response(blocks, input_tokens=10, output_tokens=5):
    response = MagicMock()
    response.content = blocks
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


def test_run_turn_text_only_response():
    client = MagicMock()
    client.messages.create.return_value = make_response([make_text_block("Hello")])

    turn = anthropic_provider.run_turn(client, [{"role": "user", "content": "hi"}], [])

    assert turn.text == "Hello"
    assert turn.tool_calls == []
    assert turn.input_tokens == 10
    assert turn.output_tokens == 5


def test_run_turn_parses_tool_use_block():
    client = MagicMock()
    client.messages.create.return_value = make_response(
        [make_tool_use_block("toolu_1", "sql_tool", {"query": "SELECT 1"})]
    )

    turn = anthropic_provider.run_turn(client, [], [])

    assert turn.text is None
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].id == "toolu_1"
    assert turn.tool_calls[0].name == "sql_tool"
    # Unlike OpenAI, Anthropic hands back input as an already-parsed dict.
    assert turn.tool_calls[0].arguments == {"query": "SELECT 1"}


def test_run_turn_handles_mixed_text_and_tool_use_in_one_response():
    client = MagicMock()
    client.messages.create.return_value = make_response(
        [make_text_block("Let me check."), make_tool_use_block("toolu_1", "sql_tool", {"query": "SELECT 1"})]
    )

    turn = anthropic_provider.run_turn(client, [], [])

    assert turn.text == "Let me check."
    assert len(turn.tool_calls) == 1


def test_run_turn_passes_system_prompt_and_max_tokens():
    client = MagicMock()
    client.messages.create.return_value = make_response([make_text_block("ok")])

    anthropic_provider.run_turn(client, [], [])

    _, kwargs = client.messages.create.call_args
    assert kwargs["system"] == anthropic_provider.SYSTEM_PROMPT
    assert kwargs["max_tokens"] == anthropic_provider.MAX_TOKENS


def test_build_initial_messages_has_no_system_message():
    messages = anthropic_provider.build_initial_messages("hello")
    assert messages == [{"role": "user", "content": "hello"}]
    assert all(m["role"] != "system" for m in messages)


def test_build_tool_result_messages_bundles_into_one_user_message():
    calls = [
        ToolCallRequest(id="c1", name="sql_tool", arguments={}),
        ToolCallRequest(id="c2", name="rag_tool", arguments={}),
    ]
    messages = anthropic_provider.build_tool_result_messages(calls, ["result1", "result2"])

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == [
        {"type": "tool_result", "tool_use_id": "c1", "content": "result1"},
        {"type": "tool_result", "tool_use_id": "c2", "content": "result2"},
    ]


def test_build_client_returns_anthropic_instance(monkeypatch):
    from anthropic import Anthropic

    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    client = anthropic_provider.build_client()
    assert isinstance(client, Anthropic)
