from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse, FileResponse
from typing import Literal
from pathlib import Path
from generate import generate_response_stream

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="closedai-chatbot API")

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=8000)
    history: list[ChatMessage] = Field(default_factory=list)
    history_window: int = Field(default=6, ge=0, le=20)


@app.get("/")
def get_root() -> FileResponse:
    return FileResponse(path=INDEX_HTML_PATH)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/question")
def question(payload: QuestionRequest) -> StreamingResponse:
    try:
        token_stream = generate_response_stream(
            question=payload.question,
            context=payload.context,
            history=payload.history,
            history_window=payload.history_window,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    return StreamingResponse(token_stream, media_type="text/plain; charset=utf-8")
