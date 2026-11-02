from fastapi import APIRouter, Depends

from app.api.routes import admin, citizen, gps
from app.core.security import require_admin

api_router = APIRouter()
api_router.include_router(citizen.router, prefix="/citizen", tags=["citizen"])
api_router.include_router(gps.router, prefix="/gps", tags=["gps"])
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
