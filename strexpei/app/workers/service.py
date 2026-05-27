from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from sqlmodel import select
from ..db.models import User


class WorkerService:

    async def get_strexpei_user(self, uid: uuid.UUID, session: AsyncSession):
        statement = select(User).where(User.uid == uid)
        response = await session.execute(statement)
        result = response.scalars().first()

        return result