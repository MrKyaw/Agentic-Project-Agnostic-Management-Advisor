from app.settings import settings
from sqlmodel import create_engine, SQLModel, Session, select
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

def init_db(session: Session):
    # lazy way to create tables instead of using migrations
    SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.username == settings.FIRST_SUPERUSER_USERNAME)
    ).first()

    if not user:
        user_in = UserCreate(
            username=settings.FIRST_SUPERUSER_USERNAME,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_admin=True,
        )
        user = create_user(
            session=session,
            user_create=user_in,
            )

def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"password": user_create.password}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj

def get_user_by_username(*, session: Session, username: str) -> User | None:
    return session.exec(select(User).where(User.username == username)).first()
