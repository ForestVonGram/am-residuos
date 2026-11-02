from typing import Annotated

from fastapi import APIRouter, Header, HTTPException

from app.api.dependencies import GPSServiceDependency
from app.schemas.gps import PositionIngestResponse, PositionInput
from app.services.gps import InvalidPosition

router = APIRouter()


@router.post("/positions", response_model=PositionIngestResponse)
async def ingest_positions(
    payload: list[PositionInput] | PositionInput,
    service: GPSServiceDependency,
    x_device_token: Annotated[str | None, Header()] = None,
) -> PositionIngestResponse:
    if not x_device_token:
        raise HTTPException(status_code=401, detail="Token de dispositivo requerido")
    positions = payload if isinstance(payload, list) else [payload]
    if not positions:
        raise HTTPException(status_code=422, detail="El lote debe contener posiciones")
    if len(positions) > 50:
        raise HTTPException(status_code=422, detail="El lote admite máximo 50 posiciones")
    try:
        accepted, duplicates = await service.ingest(x_device_token, positions)
    except InvalidPosition as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return PositionIngestResponse(accepted=accepted, duplicates=duplicates)
