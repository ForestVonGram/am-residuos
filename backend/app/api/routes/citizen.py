from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CitizenServiceDependency
from app.schemas.citizen import ETAResponse, RouteDetail, RouteSummary, ScheduleItem
from app.services.citizen import RouteNotFoundError

router = APIRouter()

Latitude = Annotated[float, Query(ge=-90, le=90, examples=[4.5339])]
Longitude = Annotated[float, Query(ge=-180, le=180, examples=[-75.6811])]


@router.get("/routes", response_model=list[RouteSummary])
async def list_routes(
    service: CitizenServiceDependency,
    latitude: Latitude | None = None,
    longitude: Longitude | None = None,
    radius_m: Annotated[int, Query(ge=50, le=10_000)] = 750,
) -> list[RouteSummary]:
    """Lista rutas activas; si hay coordenadas, limita el resultado por cercania."""
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="latitude y longitude deben enviarse juntas",
        )
    return await service.list_routes(latitude, longitude, radius_m)


@router.get("/routes/{route_id}", response_model=RouteDetail)
async def get_route(route_id: UUID, service: CitizenServiceDependency) -> RouteDetail:
    """Devuelve el trazado GeoJSON y los datos publicos de una ruta."""
    try:
        return await service.get_route(route_id)
    except RouteNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/schedules", response_model=list[ScheduleItem])
async def list_schedules(
    service: CitizenServiceDependency,
    service_date: date | None = None,
    route_id: UUID | None = None,
) -> list[ScheduleItem]:
    """Consulta las jornadas programadas para una fecha local de Armenia."""
    return await service.list_schedules(service_date, route_id)


@router.get("/eta", response_model=ETAResponse)
async def estimate_arrival(
    latitude: Latitude,
    longitude: Longitude,
    service: CitizenServiceDependency,
    route_id: UUID | None = None,
    at: datetime | None = None,
    radius_m: Annotated[int, Query(ge=50, le=10_000)] = 750,
) -> ETAResponse:
    """Calcula la proxima llegada programada al punto indicado sobre la ruta."""
    try:
        return await service.estimate_arrival(
            latitude=latitude,
            longitude=longitude,
            route_id=route_id,
            at=at,
            radius_m=radius_m,
        )
    except RouteNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
