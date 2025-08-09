from fastapi import APIRouter
from app.api.endpoints import management

api_router = APIRouter()
api_router.include_router(management.router, tags=["Management"])