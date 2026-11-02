"""Seed de datos operativos para la demostración local."""

import argparse
import asyncio
import hashlib
import secrets
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from seed_routes import seed_routes
from sqlalchemy import select

from app.core.config import get_settings
from app.database.session import AsyncSessionFactory, engine
from app.models.gps import GPSDevice
from app.models.operational import Personnel, RouteAssignment, Truck
from app.models.route import CollectionRoute, RouteSchedule


async def seed_demo(start_in_minutes: int) -> None:
    await seed_routes()
    zone = ZoneInfo(get_settings().timezone)
    now = datetime.now(zone)
    service_date = now.date()
    active_start = now + timedelta(minutes=start_in_minutes)
    effective_to = service_date + timedelta(days=14)

    async with AsyncSessionFactory() as session:
        routes = list(
            (
                await session.scalars(
                    select(CollectionRoute).where(
                        CollectionRoute.active.is_(True)
                    ).order_by(CollectionRoute.code)
                )
            ).all()
        )
        if len(routes) < 2:
            raise RuntimeError("El GeoJSON de demostración debe contener RUTA-1 y RUTA-2")

        trucks = []
        crews = []
        for index, route in enumerate(routes[:2], start=1):
            plate = f"AXM-{index:03d}"
            truck = await session.scalar(select(Truck).where(Truck.plate == plate))
            if not truck:
                truck = Truck(plate=plate, name=f"Camión demo {index}", status="available")
                session.add(truck)
                await session.flush()
            else:
                truck.name = f"Camión demo {index}"
                truck.active = True
                truck.status = "available"
            trucks.append(truck)

            crew = []
            for role, suffix, first_name in (
                ("driver", "C", "Conductor"),
                ("collector", "R", "Recolector"),
            ):
                employee_code = f"DEMO-{index}{suffix}"
                person = await session.scalar(
                    select(Personnel).where(Personnel.employee_code == employee_code)
                )
                if not person:
                    person = Personnel(
                        first_name=f"{first_name} {index}",
                        last_name="Demostración",
                        employee_code=employee_code,
                        role=role,
                        active=True,
                    )
                    session.add(person)
                    await session.flush()
                else:
                    person.active = True
                crew.append(person)
            crews.append(crew)

            assignment = await session.scalar(
                select(RouteAssignment).where(
                    RouteAssignment.route_id == route.id,
                    RouteAssignment.truck_id == truck.id,
                    RouteAssignment.effective_from == service_date,
                )
            )
            if not assignment:
                assignment = RouteAssignment(
                    route_id=route.id,
                    truck=truck,
                    personnel=crew,
                    effective_from=service_date,
                    effective_to=effective_to,
                    active=True,
                )
                session.add(assignment)
            else:
                assignment.effective_to = effective_to
                assignment.active = True
                assignment.personnel = crew

            for weekday in range(7):
                schedule = await session.scalar(
                    select(RouteSchedule).where(
                        RouteSchedule.route_id == route.id,
                        RouteSchedule.weekday == weekday,
                        RouteSchedule.effective_from == service_date,
                    )
                )
                start_time = (
                    active_start.time().replace(tzinfo=None, second=0, microsecond=0)
                    if weekday == service_date.weekday()
                    else time(6, 0)
                )
                if not schedule:
                    session.add(
                        RouteSchedule(
                            route_id=route.id,
                            weekday=weekday,
                            start_time=start_time,
                            duration_minutes=120,
                            effective_from=service_date,
                            effective_to=effective_to,
                            active=True,
                        )
                    )
                else:
                    schedule.start_time = start_time
                    schedule.effective_to = effective_to
                    schedule.active = True

            device_code = f"SIM-{plate}"
            device = await session.scalar(
                select(GPSDevice).where(GPSDevice.device_code == device_code)
            )
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            if not device:
                device = GPSDevice(
                    device_code=device_code,
                    truck_id=truck.id,
                    api_token_hash=token_hash,
                    active=True,
                )
                session.add(device)
            else:
                device.truck_id = truck.id
                device.api_token_hash = token_hash
                device.active = True
            print(f"Dispositivo {device_code} / {plate}: token={token}")

        await session.commit()
        print(f"Seed listo para {len(routes[:2])} rutas; jornada del {service_date}.")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cargar datos operativos GPS de demostración.")
    parser.add_argument("--start-in-minutes", type=int, default=2)
    args = parser.parse_args()
    if args.start_in_minutes < 0:
        parser.error("--start-in-minutes no puede ser negativo")
    asyncio.run(seed_demo(args.start_in_minutes))


if __name__ == "__main__":
    main()
