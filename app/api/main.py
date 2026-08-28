"""FastAPI entrypoint. Routes are plain `def`, not `async def` --
run_agent() makes blocking calls (sync OpenAI/Anthropic clients,
sqlite3, chromadb), and FastAPI runs sync route functions in a
threadpool so they don't block the event loop. `async def` here with
the same blocking calls inside would serialize every request.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agent.loop import BudgetExceededError, run_agent

app = FastAPI(title="incident-triage-agent")


class ChatRequest(BaseModel):
    question: str
    provider: str = "anthropic"


class ChatResponse(BaseModel):
    answer: str
    request_id: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = run_agent(request.question, provider=request.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BudgetExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return ChatResponse(answer=result.answer, request_id=result.request_id)
