from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.database.session import engine
from app.services.admin import AdminError

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "API publica para consultar rutas, horarios y tiempos estimados "
        "de recoleccion de residuos en Armenia."
    ),
    lifespan=lifespan,
)

if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-Admin-Key", "X-Device-Token", "Content-Type"],
    )

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.exception_handler(AdminError)
async def admin_error_handler(_: Request, error: AdminError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": str(error)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    if any("at" in item.get("loc", ()) for item in error.errors()):
        return JSONResponse(
            status_code=422,
            content={"detail": "El parámetro 'at' debe ser una fecha y hora válida."},
        )
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(error.errors())},
    )


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
