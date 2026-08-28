from unittest.mock import MagicMock

from app.agent.providers import openai_provider
from app.agent.turn import ToolCallRequest


def make_response(content=None, tool_calls=None, prompt_tokens=10, completion_tokens=5):
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    message.model_dump.return_value = {"role": "assistant", "content": content}

    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    return response


def test_run_turn_text_only_response():
    client = MagicMock()
    client.chat.completions.create.return_value = make_response(content="Hello")

    turn = openai_provider.run_turn(client, [{"role": "user", "content": "hi"}], [])

    assert turn.text == "Hello"
    assert turn.tool_calls == []
    assert turn.input_tokens == 10
    assert turn.output_tokens == 5


def test_run_turn_parses_tool_calls():
    tc = MagicMock()
    tc.id = "call_123"
    tc.function.name = "sql_tool"
    tc.function.arguments = '{"query": "SELECT 1"}'

    client = MagicMock()
    client.chat.completions.create.return_value = make_response(content=None, tool_calls=[tc])

    turn = openai_provider.run_turn(client, [], [])

    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].id == "call_123"
    assert turn.tool_calls[0].name == "sql_tool"
    assert turn.tool_calls[0].arguments == {"query": "SELECT 1"}


def test_run_turn_no_tool_calls_gives_empty_list_not_none():
    client = MagicMock()
    client.chat.completions.create.return_value = make_response(content="done", tool_calls=None)

    turn = openai_provider.run_turn(client, [], [])
    assert turn.tool_calls == []


def test_run_turn_passes_model_and_max_tokens():
    client = MagicMock()
    client.chat.completions.create.return_value = make_response(content="ok")

    openai_provider.run_turn(client, [], [])

    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"] == openai_provider.MODEL
    assert kwargs["max_tokens"] == openai_provider.MAX_TOKENS


def test_build_initial_messages_includes_system_prompt():
    messages = openai_provider.build_initial_messages("hello")
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "hello"}


def test_build_tool_result_messages_one_message_per_call():
    calls = [
        ToolCallRequest(id="c1", name="sql_tool", arguments={}),
        ToolCallRequest(id="c2", name="rag_tool", arguments={}),
    ]
    messages = openai_provider.build_tool_result_messages(calls, ["result1", "result2"])
    assert messages == [
        {"role": "tool", "tool_call_id": "c1", "content": "result1"},
        {"role": "tool", "tool_call_id": "c2", "content": "result2"},
    ]


def test_build_client_returns_openai_instance(monkeypatch):
    from openai import OpenAI

    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = openai_provider.build_client()
    assert isinstance(client, OpenAI)
