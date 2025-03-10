from fastapi import APIRouter, Request, Body
from fastapi.responses import StreamingResponse
from fastapi.exceptions import HTTPException
from pydantic import BaseModel
from app.dependencies import SessionDep, CurrentUser
from app.models import Chat, ChatsRead, ChatCreate, ChatRead
from sqlmodel import select, func
from app import db
import uuid
from app.logger import logger


from app.services.siteconf_manager import load_config
from ollama import AsyncClient

config = load_config()
OLLAMA_ENDPOINT, DEFAULT_MODEL = config["ollama_endpoint"], config["default_model"]
client = AsyncClient(
    host=OLLAMA_ENDPOINT,
)


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

class MessageRequest(BaseModel):
    message: str

@router.post("/{chat_id}")
async def send_message(
    session: SessionDep,
    current_user: CurrentUser,

    chat_id: uuid.UUID,
    request: MessageRequest = Body(..., example={"message": "Hello"}),
):
    """Chat with the Ollama model and return the response as a Server-Sent Event."""
    # load chat from db
    # chat = db.get_chat_by_id(session=session, chat_id=chat_id)
    chat = session.exec(select(Chat).where(Chat.id == chat_id)).first()
    if not chat or chat.owner != current_user:
        raise HTTPException(status_code=403, detail=f"You do not have permission to access chat-{chat_id}")

    # append user message to context
    if chat.title is None:
        chat.title = request.message[:150]
    chat.context.append({'role': 'user', 'content': request.message})

    async def generate_chat_wrapper():
        """Chat with the Ollama model and return the response as a Server-Sent Event."""
        stream = client.chat(
            model=DEFAULT_MODEL,
            messages=chat.context,
            stream=True,
        )

        full_response = ""
        async for chunk in await stream:
            full_response += chunk.message.content
            yield chunk.message.content
        chat.context.append({"role":"assistant", "content":full_response})
        session.add(chat)
        session.commit()
        session.refresh(chat)
        logger.debug(chat.context)

        return



    return StreamingResponse(
        generate_chat_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
