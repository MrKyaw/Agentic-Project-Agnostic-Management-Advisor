from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

from app.dependencies import get_current_user, SessionDep
from app.models import User, UserRead
import app.db as db

from app.models import UserRegister, UserCreate, Token
from app.settings import settings
import jwt

from typing import Any
from datetime import timedelta, datetime, timezone

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/signup", response_model=UserRead)
def register_user(session: SessionDep, user_in: UserRegister) -> User:
    """
    Create a new user
    """
    user = db.get_user_by_username(session=session, username=user_in.username)
    if user:
        raise HTTPException(status_code=400, detail=f"Username {user_in.username} already registered")
    user_create = UserCreate.model_validate(user_in)
    return db.create_user(session=session, user_create=user_create)

@router.post("/login")
def login_user(
    session: SessionDep, 
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = db.get_user_by_username(session=session, username=form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Username not found")
    if user.password != form_data.password:
        raise HTTPException(status_code=400, detail="Incorrect password")
    if user.is_active is False:
        raise HTTPException(status_code=400, detail="Inactive user")
    return Token(
        access_token=create_access_token(
            subject=user.id, 
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
    )


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    """
    Create a new access token
    """
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt