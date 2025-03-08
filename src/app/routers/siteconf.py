from fastapi import APIRouter, Depends, HTTPException
# from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any
from app.services.siteconf_manager import load_config, update_config


router = APIRouter()
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.get("/config")
async def get_config() -> Dict[str, Any]:
    return load_config()

@router.put("/config")
async def update_config_route(config: Dict[str, Any]) -> Dict[str, Any]:
    update_config(config)
    return config