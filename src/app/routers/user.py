from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import get_current_user
from app.models import User, UserRead
import app.db as db

from app.models import UserRegister, UserCreate
from app.dependencies import SessionDep

router = APIRouter()

@router.post("/signup", response_model=UserRead)
def register_user(session: SessionDep, user_in: UserRegister) -> User:
    """
    Create a new user
    """
    user = db.get_user_by_username(session=session, username=user_in.username)
    if user:
        raise HTTPException(status_code=400, detail="Username already registered")
    user_create = UserCreate.model_validate(user_in)
    return db.create_user(session=session, user_create=user_create)