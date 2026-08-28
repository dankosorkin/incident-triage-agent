import pytest
from fastapi.testclient import TestClient

from app.agent.loop import BudgetExceededError
from app.agent.turn import AgentResult
from app.api import main
from app.api.rate_limiter import RateLimiter


@pytest.fixture(autouse=True)
def reset_rate_limiter(monkeypatch):
    # TestClient uses a fixed fake IP for every request, and the real
    # limiter is a module-level singleton -- without this, tests would
    # trip each other's rate limit just from sharing that IP across the
    # whole file.
    monkeypatch.setattr(main, "chat_rate_limiter", RateLimiter(max_requests=1000, window_seconds=60))


def test_health_returns_ok():
    client = TestClient(main.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_agent_answer(monkeypatch):
    monkeypatch.setattr(
        main,
        "run_agent",
        lambda question, provider: AgentResult(
            answer="10 incidents", tool_executions=[], request_id="req-123"
        ),
    )
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "how many?", "provider": "openai"})

    assert response.status_code == 200
    assert response.json() == {"answer": "10 incidents", "request_id": "req-123"}


def test_chat_defaults_provider_to_anthropic(monkeypatch):
    captured = {}

    def fake_run_agent(question, provider):
        captured["provider"] = provider
        return AgentResult(answer="ok", tool_executions=[], request_id="req-456")

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    client = TestClient(main.app)

    client.post("/chat", json={"question": "hi"})

    assert captured["provider"] == "anthropic"


def test_chat_invalid_provider_returns_422():
    # provider is a Literal now -- rejected by request validation before
    # run_agent (and its own ValueError check) is ever reached.
    client = TestClient(main.app)
    response = client.post("/chat", json={"question": "hi", "provider": "bogus"})
    assert response.status_code == 422


def test_chat_missing_question_returns_422():
    client = TestClient(main.app)
    response = client.post("/chat", json={})
    assert response.status_code == 422


def test_chat_empty_question_returns_422():
    client = TestClient(main.app)
    response = client.post("/chat", json={"question": ""})
    assert response.status_code == 422


def test_chat_overlong_question_returns_422():
    client = TestClient(main.app)
    response = client.post("/chat", json={"question": "x" * 2001})
    assert response.status_code == 422


def test_chat_budget_exceeded_returns_429(monkeypatch):
    def raise_budget_exceeded(question, provider):
        raise BudgetExceededError("Daily budget of $5.00 exceeded")

    monkeypatch.setattr(main, "run_agent", raise_budget_exceeded)
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "hi"})

    assert response.status_code == 429
    assert "budget" in response.json()["detail"].lower()


def test_chat_open_by_default_when_no_service_api_key_configured(monkeypatch):
    monkeypatch.setattr(main.settings, "service_api_key", None)
    monkeypatch.setattr(
        main, "run_agent", lambda question, provider: AgentResult(answer="ok", tool_executions=[], request_id="r")
    )
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "hi"})

    assert response.status_code == 200


def test_chat_rejects_missing_api_key_when_configured(monkeypatch):
    monkeypatch.setattr(main.settings, "service_api_key", "secret-123")
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "hi"})

    assert response.status_code == 401


def test_chat_rejects_wrong_api_key_when_configured(monkeypatch):
    monkeypatch.setattr(main.settings, "service_api_key", "secret-123")
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "hi"}, headers={"x-api-key": "wrong"})

    assert response.status_code == 401


def test_chat_accepts_correct_api_key_when_configured(monkeypatch):
    monkeypatch.setattr(main.settings, "service_api_key", "secret-123")
    monkeypatch.setattr(
        main, "run_agent", lambda question, provider: AgentResult(answer="ok", tool_executions=[], request_id="r")
    )
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "hi"}, headers={"x-api-key": "secret-123"})

    assert response.status_code == 200


def test_chat_rate_limited_after_max_requests(monkeypatch):
    monkeypatch.setattr(main, "chat_rate_limiter", RateLimiter(max_requests=2, window_seconds=60))
    monkeypatch.setattr(
        main, "run_agent", lambda question, provider: AgentResult(answer="ok", tool_executions=[], request_id="r")
    )
    client = TestClient(main.app)

    first = client.post("/chat", json={"question": "hi"})
    second = client.post("/chat", json={"question": "hi"})
    third = client.post("/chat", json={"question": "hi"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_ready_returns_200_when_all_checks_pass(monkeypatch):
    monkeypatch.setattr(main, "run_readiness_checks", lambda: {"database": "ok", "chroma": "ok", "provider_keys": "ok"})
    client = TestClient(main.app)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_returns_503_when_a_check_fails(monkeypatch):
    monkeypatch.setattr(
        main, "run_readiness_checks", lambda: {"database": "ok", "chroma": "error: no collection", "provider_keys": "ok"}
    )
    client = TestClient(main.app)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["chroma"] == "error: no collection"
