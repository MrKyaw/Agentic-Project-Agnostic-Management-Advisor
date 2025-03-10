from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, siteconf, user
from app.settings import settings
from app.logger import logger

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
api_router = APIRouter()
api_router.include_router(siteconf.router)
api_router.include_router(chat.router)
api_router.include_router(user.router)
app.include_router(api_router, prefix=settings.API_V1_STR)

logger.info("App initialized")