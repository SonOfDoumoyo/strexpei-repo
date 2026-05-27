from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from sqlalchemy.orm import selectinload
from ...config import Config
from ..auth.utils import generate_password_hash
from ..auth.redis import save_password_reset_otp
from ..auth.auth_schema import (
    SignUpModel,
    LoginModel,
    UserModel,
    UserUpdateModel
)
from .user_schema import NotifyData
from fastapi import Request
from user_agents import parse
from ...config import Config
import uuid
from ..db.models import (
    User,
    Company,
    Staff,
    RequestJoin,
    Notification
)
from datetime import datetime, timedelta
from ...errors import(
    UserNotFound
)
from ..auth.redis import redis_client
from ..admin.admin_schema import AllUsersModel
import secrets

class UserService:

    async def get_notification(self, nid: uuid.UUID, session: AsyncSession):
        stmt = select(Notification).where(Notification.nid == nid)
        response = await session.execute(stmt)
        notify = response.scalars().first()

        return notify
    

    async def get_user_notifications(self, receiver_id: uuid.UUID, session: AsyncSession):
        stmt = select(Notification).options(selectinload(Notification.sender), selectinload(Notification.sender).selectinload(User.sent), selectinload(Notification.receiver), selectinload(Notification.receiver).selectinload(User.received)).where(Notification.receiver_id == receiver_id)
        response = await session.execute(stmt)
        notifications = response.scalars().first()

        return notifications


    async def update_notification(self, nid: uuid.UUId, update_notify: dict, session: AsyncSession):
        try:

            notify = await self.get_notification(nid=nid, session=session)
            allowed_updates = ['isRead']

            for k, v in update_notify.items():
                if k in allowed_updates:
                    setattr(notify, k, v)

            await session.commit()
            await session.refresh(notify)

            return True

        except Exception as e:
            await session.rollback()
            raise e
        
    async def add_notification(self, notify_add: NotifyData, session: AsyncSession):
        try:
            new_not = Notification(
                **notify_add
            )

            session.add(new_not)
            await session.commit()
            await session.refresh(new_not)

            return new_not
        
        except Exception as e:
            await session.rollback()
            raise e