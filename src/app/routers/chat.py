from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.services.ollama_manager import generate_chat_stream
from pydantic import BaseModel

# ephemeral context for current user
# TODO: store this in a database
context = []

class ChatRequest(BaseModel):
    message: str

router = APIRouter()
@router.post("/chat")
async def chat(request: ChatRequest):
    """Chat with the Ollama model and return the response as a Server-Sent Event."""
    return StreamingResponse(
        generate_chat_stream(request.message, context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
