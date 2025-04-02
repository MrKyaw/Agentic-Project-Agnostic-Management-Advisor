from fastapi import APIRouter, Request, Body
from fastapi.responses import StreamingResponse
from fastapi.exceptions import HTTPException
from pydantic import BaseModel
from app.dependencies import SessionDep, CurrentUser
from app.models import Chat, ChatsRead, ChatCreate, ChatRead
from sqlmodel import select, func
from sqlalchemy.orm.attributes import flag_modified
from app import db
import uuid
from app.logger import logger
from sqlmodel import Session
from app.db import engine

from app.services.siteconf_manager import load_config
from ollama import AsyncClient, Client

config = load_config()
OLLAMA_ENDPOINT, DEFAULT_MODEL = config["ollama_endpoint"], config["default_model"]
async_client = AsyncClient(
    host=OLLAMA_ENDPOINT,
)
client = Client(
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
    chat.context.append({'role': 'user', 'content': request.message})
    session.commit()

    async def generate_chat_wrapper():
        """Chat with the Ollama model and return the response as a Server-Sent Event."""
        with Session(engine) as inner_session:
            chat = inner_session.exec(select(Chat).where(Chat.id == chat_id)).first()

            stream = async_client.chat(
                model=DEFAULT_MODEL,
                messages=chat.context,
                stream=True,
            )

            full_response = ""
            async for chunk in await stream:
                full_response += chunk.message.content
                yield chunk.message.content
            if chat.title is None:
                chat.title = full_response[:150]
            chat.context.append({"role":"assistant", "content":full_response})
            logger.debug(chat.context)
            # session.add(chat)
            inner_session.commit()
            # session.refresh(chat)
            logger.debug(chat.context)



    return StreamingResponse(
        generate_chat_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

@router.post("/{chat_id}/sync")
def send_message(
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
    
    if not chat.context or chat.context[-1]['role'] != 'user':
        chat.context.append({'role': 'user', 'content': request.message})
    else:
        chat.context[-1] = {'role': 'user', 'content': request.message}
    flag_modified(chat, "context")

    session.commit()

    def generate_chat_wrapper():
        """Chat with the Ollama model and return the response as a Server-Sent Event."""
        with Session(engine) as inner_session:
            chat = inner_session.exec(select(Chat).where(Chat.id == chat_id)).first()

            stream = client.chat(
                model=DEFAULT_MODEL,
                messages=chat.context,
                stream=True,
            )

            full_response = ""
            for chunk in stream:
                full_response += chunk.message.content
                yield chunk.message.content
            if chat.title is None:
                chat.title = full_response[:150]

            chat.context.append({"role":"assistant", "content":full_response})
            flag_modified(chat, "context")
            logger.debug(chat.context)
            inner_session.commit()
            logger.debug(chat.context)




    return StreamingResponse(
        generate_chat_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )