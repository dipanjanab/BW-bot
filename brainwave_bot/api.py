from fastapi import FastAPI, HTTPException
from .models import AskRequest, AskResponse
from .orchestrator import MarketAuthorizationError, default_orchestrator

app = FastAPI(title="Brainwave Bot", version="0.1.0")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        return default_orchestrator().ask(request.question, request.allowed_markets)
    except MarketAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
