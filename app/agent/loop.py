"""The agent loop: sends the conversation + tool specs to the chosen
provider, dispatches any requested tool calls, feeds results back,
and repeats until the model returns a final text answer.
"""

import json
import time

from app.agent.providers import anthropic_provider, openai_provider
from app.agent.tool_specs import TOOLS
from app.agent.turn import AgentResult, ToolExecution
from app.rag.rag_tool import search as rag_search
from app.sql.sql_tool import run_sql_query
from app.tracing import tracer

MAX_ITERATIONS = 5

TOOL_DISPATCH = {
    "sql_tool": lambda args: run_sql_query(args["query"]),
    "rag_tool": lambda args: rag_search(args["query"], top_k=args.get("top_k", 5)),
}

# Verify against current provider pricing pages before trusting this for
# real cost reporting -- same caveat as EMBEDDING_PRICE_PER_1M_TOKENS.
MODEL_PRICING = {
    openai_provider.MODEL: {"input_per_1m": 0.15, "output_per_1m": 0.60},
    anthropic_provider.MODEL: {"input_per_1m": 1.00, "output_per_1m": 5.00},
}

PROVIDERS = {"openai": openai_provider, "anthropic": anthropic_provider}


def run_agent(question: str, provider: str = "anthropic") -> AgentResult:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    adapter = PROVIDERS[provider]
    client = adapter.build_client()
    messages = adapter.build_initial_messages(question)
    tool_executions: list[ToolExecution] = []

    for _ in range(MAX_ITERATIONS):
        start = time.perf_counter()
        turn = adapter.run_turn(client, messages, TOOLS)
        latency_ms = (time.perf_counter() - start) * 1000

        pricing = MODEL_PRICING[adapter.MODEL]
        cost_usd = (
            turn.input_tokens / 1_000_000 * pricing["input_per_1m"]
            + turn.output_tokens / 1_000_000 * pricing["output_per_1m"]
        )
        tracer.log_event(
            "llm_call",
            provider=provider,
            model=adapter.MODEL,
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
            cost_usd=round(cost_usd, 6),
            latency_ms=round(latency_ms, 2),
            tool_calls=[tc.name for tc in turn.tool_calls],
        )

        messages.append(turn.raw_assistant_message)

        if not turn.tool_calls:
            return AgentResult(answer=turn.text or "", tool_executions=tool_executions)

        results = []
        for tc in turn.tool_calls:
            try:
                result = TOOL_DISPATCH[tc.name](tc.arguments)
                result_str = json.dumps(result)
            except Exception as exc:
                # Tool failures are handed back to the model as the tool
                # result, not raised -- the model can see the error and
                # decide whether to retry with different arguments, fall
                # back to the other tool, or explain the failure to the
                # user. Broad on purpose: any failure at this boundary
                # (ours or the tool's) should reach the model this way.
                result_str = f"Error: {exc}"
            results.append(result_str)
            tool_executions.append(ToolExecution(name=tc.name, arguments=tc.arguments, result=result_str))

        messages.extend(adapter.build_tool_result_messages(turn.tool_calls, results))

    return AgentResult(
        answer="Agent could not resolve the question within the iteration limit.",
        tool_executions=tool_executions,
    )
