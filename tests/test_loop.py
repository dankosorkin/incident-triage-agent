from unittest.mock import MagicMock

import pytest

from app.agent import loop
from app.agent.turn import LLMTurn, ToolCallRequest
from app.config import settings


@pytest.fixture
def fake_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    # Isolate from the real traces.jsonl -- run_agent() checks
    # tracer.cost_today_usd() every iteration for the budget circuit
    # breaker, and reading the real (growing, real-money) trace log
    # here would make these tests depend on today's actual spend.
    monkeypatch.setattr(loop.tracer, "TRACE_LOG_PATH", tmp_path / "traces.jsonl")
    fake = MagicMock()
    fake.MODEL = "fake-model"
    fake.build_client.return_value = MagicMock()
    fake.build_initial_messages.return_value = [{"role": "user", "content": "q"}]
    fake.build_tool_result_messages.side_effect = lambda calls, results: [
        {"role": "tool_result", "content": r} for r in results
    ]
    monkeypatch.setitem(loop.PROVIDERS, "openai", fake)
    monkeypatch.setitem(loop.MODEL_PRICING, "fake-model", {"input_per_1m": 0, "output_per_1m": 0})
    return fake


def text_turn(text):
    return LLMTurn(text=text, tool_calls=[], raw_assistant_message={"role": "assistant"}, input_tokens=1, output_tokens=1)


def tool_call_turn(name, arguments, call_id="c1"):
    return LLMTurn(
        text=None,
        tool_calls=[ToolCallRequest(id=call_id, name=name, arguments=arguments)],
        raw_assistant_message={"role": "assistant"},
        input_tokens=1,
        output_tokens=1,
    )


def test_run_agent_returns_text_when_no_tool_calls(fake_provider):
    fake_provider.run_turn.return_value = text_turn("the answer")

    result = loop.run_agent("question", provider="openai")

    assert result.answer == "the answer"
    assert result.tool_executions == []


def test_run_agent_dispatches_sql_tool_and_returns_final_answer(fake_provider, monkeypatch):
    monkeypatch.setitem(loop.TOOL_DISPATCH, "sql_tool", lambda args, request_id: [{"count": 10}])
    fake_provider.run_turn.side_effect = [
        tool_call_turn("sql_tool", {"query": "SELECT COUNT(*)"}),
        text_turn("There are 10."),
    ]

    result = loop.run_agent("question", provider="openai")

    assert result.answer == "There are 10."
    assert len(result.tool_executions) == 1
    assert result.tool_executions[0].name == "sql_tool"
    assert result.tool_executions[0].arguments == {"query": "SELECT COUNT(*)"}
    assert result.tool_executions[0].result == "[{\"count\": 10}]"


def test_run_agent_handles_both_tools_in_one_turn(fake_provider, monkeypatch):
    monkeypatch.setitem(loop.TOOL_DISPATCH, "sql_tool", lambda args, request_id: "sql result")
    monkeypatch.setitem(loop.TOOL_DISPATCH, "rag_tool", lambda args, request_id: "rag result")
    turn_with_two_calls = LLMTurn(
        text=None,
        tool_calls=[
            ToolCallRequest(id="c1", name="sql_tool", arguments={}),
            ToolCallRequest(id="c2", name="rag_tool", arguments={}),
        ],
        raw_assistant_message={},
        input_tokens=1,
        output_tokens=1,
    )
    fake_provider.run_turn.side_effect = [turn_with_two_calls, text_turn("done")]

    result = loop.run_agent("question", provider="openai")

    assert {te.name for te in result.tool_executions} == {"sql_tool", "rag_tool"}


def test_run_agent_tool_failure_does_not_crash_and_is_recorded(fake_provider, monkeypatch):
    def failing_tool(args, request_id):
        raise ValueError("boom")

    monkeypatch.setitem(loop.TOOL_DISPATCH, "sql_tool", failing_tool)
    fake_provider.run_turn.side_effect = [
        tool_call_turn("sql_tool", {"query": "bad"}),
        text_turn("I couldn't run that query."),
    ]

    result = loop.run_agent("question", provider="openai")

    assert result.answer == "I couldn't run that query."
    assert "Error: boom" in result.tool_executions[0].result


def test_run_agent_stops_at_max_iterations(fake_provider, monkeypatch):
    monkeypatch.setitem(loop.TOOL_DISPATCH, "sql_tool", lambda args, request_id: "result")
    # Always requests another tool call, never returns final text.
    fake_provider.run_turn.side_effect = [tool_call_turn("sql_tool", {}) for _ in range(loop.MAX_ITERATIONS)]

    result = loop.run_agent("question", provider="openai")

    assert "iteration limit" in result.answer
    assert fake_provider.run_turn.call_count == loop.MAX_ITERATIONS


def test_run_agent_unknown_provider_raises_value_error():
    with pytest.raises(ValueError, match="Unknown provider"):
        loop.run_agent("question", provider="not-a-real-provider")


def test_run_agent_raises_budget_exceeded_when_over_daily_limit(fake_provider, monkeypatch):
    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)
    monkeypatch.setattr(loop.tracer, "cost_today_usd", lambda: 1.50)
    fake_provider.run_turn.return_value = text_turn("should never be reached")

    with pytest.raises(loop.BudgetExceededError, match=r"\$1\.00"):
        loop.run_agent("question", provider="openai")

    fake_provider.run_turn.assert_not_called()


def test_run_agent_allows_request_under_budget(fake_provider, monkeypatch):
    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)
    monkeypatch.setattr(loop.tracer, "cost_today_usd", lambda: 0.50)
    fake_provider.run_turn.return_value = text_turn("answer")

    result = loop.run_agent("question", provider="openai")

    assert result.answer == "answer"


def test_run_agent_traces_llm_call(fake_provider, monkeypatch):
    logged = []
    monkeypatch.setattr(loop.tracer, "log_event", lambda event_type, **fields: logged.append((event_type, fields)))
    fake_provider.run_turn.return_value = text_turn("answer")

    loop.run_agent("question", provider="openai")

    assert len(logged) == 1
    event_type, fields = logged[0]
    assert event_type == "llm_call"
    assert fields["provider"] == "openai"
    assert fields["model"] == "fake-model"


def test_run_agent_request_id_is_consistent_across_llm_and_tool_calls(fake_provider, monkeypatch):
    seen_request_ids = []
    monkeypatch.setattr(
        loop.tracer,
        "log_event",
        lambda event_type, **fields: seen_request_ids.append(fields["request_id"]),
    )
    monkeypatch.setitem(
        loop.TOOL_DISPATCH,
        "sql_tool",
        lambda args, request_id: seen_request_ids.append(request_id) or "result",
    )
    fake_provider.run_turn.side_effect = [tool_call_turn("sql_tool", {}), text_turn("done")]

    result = loop.run_agent("question", provider="openai")

    # Two llm_call traces (one per adapter.run_turn) + one from inside the
    # fake tool dispatch = 3 recordings, all the same id, matching the
    # AgentResult's own request_id.
    assert len(seen_request_ids) == 3
    assert len(set(seen_request_ids)) == 1
    assert seen_request_ids[0] == result.request_id


def test_run_agent_different_calls_get_different_request_ids(fake_provider):
    fake_provider.run_turn.return_value = text_turn("answer")

    first = loop.run_agent("question one", provider="openai")
    second = loop.run_agent("question two", provider="openai")

    assert first.request_id != second.request_id
