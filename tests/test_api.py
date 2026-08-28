from fastapi.testclient import TestClient

from app.agent.turn import AgentResult
from app.api import main


def test_health_returns_ok():
    client = TestClient(main.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_returns_agent_answer(monkeypatch):
    monkeypatch.setattr(
        main, "run_agent", lambda question, provider: AgentResult(answer="10 incidents", tool_executions=[])
    )
    client = TestClient(main.app)

    response = client.post("/chat", json={"question": "how many?", "provider": "openai"})

    assert response.status_code == 200
    assert response.json() == {"answer": "10 incidents"}


def test_chat_defaults_provider_to_anthropic(monkeypatch):
    captured = {}

    def fake_run_agent(question, provider):
        captured["provider"] = provider
        return AgentResult(answer="ok", tool_executions=[])

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
