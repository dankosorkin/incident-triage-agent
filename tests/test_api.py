from fastapi.testclient import TestClient

from app.agent.loop import BudgetExceededError
from app.agent.turn import AgentResult
from app.api import main


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


def test_chat_unknown_provider_returns_400(monkeypatch):
    def raise_value_error(question, provider):
        raise ValueError(f"Unknown provider: {provider}")

    monkeypatch.setattr(main, "run_agent", raise_value_error)
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "hi", "provider": "bogus"})

    assert response.status_code == 400
    assert "bogus" in response.json()["detail"]


def test_chat_missing_question_returns_422():
    client = TestClient(main.app)
    response = client.post("/chat", json={})
    assert response.status_code == 422


def test_chat_budget_exceeded_returns_429(monkeypatch):
    def raise_budget_exceeded(question, provider):
        raise BudgetExceededError("Daily budget of $5.00 exceeded")

    monkeypatch.setattr(main, "run_agent", raise_budget_exceeded)
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "hi"})

    assert response.status_code == 429
    assert "budget" in response.json()["detail"].lower()
