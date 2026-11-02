from app.models.base import Base
from app.models.gps import GPSDevice, VehiclePosition
from app.models.operational import Personnel, RouteAssignment, ServiceAdjustment, Truck
from app.models.route import CollectionRoute, RouteSchedule

__all__ = [
    "Base",
    "GPSDevice",
    "VehiclePosition",
    "CollectionRoute",
    "Personnel",
    "RouteAssignment",
    "RouteSchedule",
    "ServiceAdjustment",
    "Truck",
]
