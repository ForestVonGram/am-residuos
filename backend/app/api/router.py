from fastapi import APIRouter

from app.api.routes import citizen

api_router = APIRouter()
api_router.include_router(citizen.router, prefix="/citizen", tags=["citizen"])
