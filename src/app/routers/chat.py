from fastapi import APIRouter, Request, Body
from fastapi.responses import StreamingResponse
from fastapi.exceptions import HTTPException
from app.services.ollama_manager import generate_chat_stream
from pydantic import BaseModel
from app.dependencies import SessionDep, CurrentUser
from app.models import Chat, ChatsRead, ChatCreate, ChatRead
from sqlmodel import select, func
from app import db
import uuid

# ephemeral context for current user
# TODO: store this in a database
context = []



router = APIRouter(prefix="/chat", tags=["chat"])
@router.get("/")
async def read_chats(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 20
):
    """Return chat conversations of the user"""
    if current_user.is_admin:
        count_statement = select(func.count()).select_from(Chat)
        count = session.exec(count_statement).one()
        statement = select(Chat).offset(skip).limit(limit)
        chats = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Chat)
            .where(Chat.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Chat)
            .where(Chat.owner_id == current_user.id)
            .offset(skip)
            .limit(limit)
        )
        chats = session.exec(statement).all()

    return ChatsRead(chats=chats, count=count)

@router.post("/create_chat", response_model=ChatRead)
async def create_chat(
    session: SessionDep,
    current_user: CurrentUser,
):
    """Create a new chat conversation"""

    chat = db.create_chat(
        session=session,
        chat_create=ChatCreate(owner_id=current_user.id)
    )
    return chat

@router.post("/{chat_id}")
async def send_message(
    session: SessionDep,
    current_user: CurrentUser,

    chat_id: uuid.UUID,
    request: BaseModel = Body(..., example={"message": "Hello"}),
):
    """Chat with the Ollama model and return the response as a Server-Sent Event."""
    chat = db.get_chat_by_id(session=session, chat_id=chat_id)
    if not chat or chat.owner != current_user:
        raise HTTPException(status_code=403, detail="Forbidden")

    return StreamingResponse(
        generate_chat_stream(request.message, context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
