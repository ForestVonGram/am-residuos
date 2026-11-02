import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models.gps import GPSDevice
from app.repositories.gps import GPSRepository
from app.schemas.gps import (
    GPSDeviceCreate,
    GPSDeviceRead,
    GPSDeviceUpdate,
    LiveVehicle,
    PositionInput,
)
from app.services.admin import AdminError, ResourceConflict, ResourceNotFound


class InvalidDeviceToken(AdminError):
    status_code = 401


class InvalidPosition(AdminError):
    status_code = 422


class GPSService:
    def __init__(self, repository: GPSRepository) -> None:
        self.repository = repository
        self.timezone = get_settings().timezone

    @staticmethod
    def _new_token() -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        return token, hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _device_read(device: GPSDevice, plate: str) -> GPSDeviceRead:
        now = datetime.now(UTC)
        online = bool(device.last_seen_at and (now - device.last_seen_at).total_seconds() < 30)
        return GPSDeviceRead(
            id=device.id,
            device_code=device.device_code,
            truck_id=device.truck_id,
            active=device.active,
            last_seen_at=device.last_seen_at,
            created_at=device.created_at,
            updated_at=device.updated_at,
            online=online,
            truck_plate=plate,
        )

    async def create_device(self, data: GPSDeviceCreate) -> tuple[GPSDeviceRead, str]:
        truck = await self.repository.get_truck(data.truck_id)
        if not truck or not truck.active:
            raise ResourceNotFound("Camión activo no encontrado")
        token, token_hash = self._new_token()
        try:
            device = await self.repository.save(
                GPSDevice(
                    device_code=data.device_code,
                    truck_id=data.truck_id,
                    api_token_hash=token_hash,
                )
            )
        except IntegrityError as error:
            await self.repository.rollback()
            raise ResourceConflict("El código o camión ya tiene un dispositivo GPS") from error
        return self._device_read(device, truck.plate), token

    async def list_devices(self) -> list[GPSDeviceRead]:
        return [
            self._device_read(device, truck.plate)
            for device, truck in await self.repository.list_devices()
        ]

    async def update_device(
        self, device_id: UUID, data: GPSDeviceUpdate
    ) -> GPSDeviceRead:
        device = await self.repository.get_device(device_id)
        if not device:
            raise ResourceNotFound("Dispositivo GPS no encontrado")
        values = data.model_dump(exclude_unset=True)
        truck = (
            await self.repository.get_truck(values["truck_id"])
            if "truck_id" in values
            else None
        )
        if "truck_id" in values:
            if not truck or not truck.active:
                raise ResourceNotFound("Camión activo no encontrado")
            device.truck_id = truck.id
        if "active" in values and values["active"] is not None:
            device.active = values["active"]
        try:
            device = await self.repository.save(device)
        except IntegrityError as error:
            await self.repository.rollback()
            raise ResourceConflict("El camión ya tiene otro dispositivo GPS") from error
        truck = truck or await self.repository.get_truck(device.truck_id)
        return self._device_read(device, truck.plate)

    async def deactivate_device(self, device_id: UUID) -> None:
        await self.update_device(device_id, GPSDeviceUpdate(active=False))

    async def regenerate_token(self, device_id: UUID) -> tuple[GPSDeviceRead, str]:
        device = await self.repository.get_device(device_id)
        if not device:
            raise ResourceNotFound("Dispositivo GPS no encontrado")
        token, device.api_token_hash = self._new_token()
        device = await self.repository.save(device)
        truck = await self.repository.get_truck(device.truck_id)
        return self._device_read(device, truck.plate), token

    async def ingest(
        self, raw_token: str, positions: list[PositionInput]
    ) -> tuple[int, int]:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        device = await self.repository.find_device_by_hash(token_hash)
        if not device or not hmac.compare_digest(device.api_token_hash, token_hash):
            raise InvalidDeviceToken("Token de dispositivo inválido")
        if not device.active:
            raise InvalidDeviceToken("El dispositivo GPS está inactivo")

        now = datetime.now(UTC)
        accepted = 0
        duplicates = 0
        for position in positions:
            recorded_at = position.recorded_at.astimezone(UTC)
            if (recorded_at - now).total_seconds() > 60:
                raise InvalidPosition(
                    "La fecha de la posición no puede estar más de 1 minuto en el futuro"
                )
            values = position.model_dump()
            values["recorded_at"] = recorded_at
            if await self.repository.insert_position(device, values):
                accepted += 1
            else:
                duplicates += 1
        await self.repository.touch_device(device, now)
        return accepted, duplicates

    async def live_vehicles(self) -> list[LiveVehicle]:
        from zoneinfo import ZoneInfo

        local_now = datetime.now(ZoneInfo(self.timezone))
        service_date = local_now.date()
        operations = await self.repository.active_operations(
            service_date, local_now.weekday(), local_now.time().replace(tzinfo=None)
        )
        cancelled = await self.repository.cancelled_schedule_ids(
            [schedule.id for schedule, _, _, _ in operations], service_date
        )
        operations = [row for row in operations if row[0].id not in cancelled]
        positions = await self.repository.latest_positions(
            [truck.id for _, _, _, truck in operations]
        )
        now_utc = datetime.now(UTC)
        return [
            LiveVehicle(
                truck_plate=truck.plate,
                truck_name=truck.name,
                latitude=position.latitude,
                longitude=position.longitude,
                speed_kmh=position.speed_kmh,
                heading=position.heading,
                recorded_at=position.recorded_at,
                stale=(now_utc - position.recorded_at).total_seconds() > 60,
                route_id=route.id,
            )
            for _, route, _, truck in operations
            if (position := positions.get(truck.id)) is not None
        ]
