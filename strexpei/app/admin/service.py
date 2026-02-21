from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from ...config import Config
from ..auth.utils import generate_password_hash
from ..auth.auth_schema import (
    SignUpModel,
    LoginModel,
    UserModel,
    UserUpdateModel
)
from .admin_schema import(
    AllUsersModel
)
from ...config import Config
import uuid
from ..db.models import (
    User,
    Company,
    Staff
)
from ...errors import(
    UserNotFound
)


class AdminService:
    
    async def get_all_users(self, session: AsyncSession):
        result = await session.execute(select(User))
        users = result.scalars().all()
        return users