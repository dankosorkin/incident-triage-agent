"""FastAPI entrypoint. Routes are plain `def`, not `async def` --
run_agent() makes blocking calls (sync OpenAI/Anthropic clients,
sqlite3, chromadb), and FastAPI runs sync route functions in a
threadpool so they don't block the event loop. `async def` here with
the same blocking calls inside would serialize every request.
"""

import logging
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent.loop import BudgetExceededError, run_agent
from app.api.rate_limiter import RateLimiter
from app.api.readiness import run_readiness_checks
from app.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="incident-triage-agent")

if settings.service_api_key is None:
    logger.warning(
        "SERVICE_API_KEY is not set -- /chat has no authentication. "
        "Fine for local dev, not for anything reachable by anyone else."
    )

# 20 requests/minute/IP. In-process only -- see rate_limiter.py.
chat_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.service_api_key is None:
        return
    if x_api_key != settings.service_api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


def check_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not chat_rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded, try again shortly")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    provider: Literal["openai", "anthropic"] = "anthropic"


class ChatResponse(BaseModel):
    answer: str
    request_id: str


@app.get("/health")
def health() -> dict:
    """Liveness only -- is the process up and answering HTTP at all.
    For "are dependencies actually working", see /ready."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:    
    checks = run_readiness_checks()
    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )


@app.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(verify_api_key), Depends(check_rate_limit)],
)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = run_agent(request.question, provider=request.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except BudgetExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return ChatResponse(answer=result.answer, request_id=result.request_id)
