from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.repositories.citizen import CitizenRepository
from app.services.citizen import CitizenService

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_citizen_service(session: DatabaseSession) -> CitizenService:
    return CitizenService(CitizenRepository(session))


CitizenServiceDependency = Annotated[CitizenService, Depends(get_citizen_service)]
