from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from internal.ollama_manager import generate_chat_stream


# ephemeral context for current user
# TODO: store this in a database
context = []

router = APIRouter()
@router.get("/chat")
async def chat(message: str):
    """Chat with the Ollama model and return the response as a Server-Sent Event."""
    return StreamingResponse(
        generate_chat_stream(message, context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
