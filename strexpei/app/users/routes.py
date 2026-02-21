from fastapi import APIRouter, Depends
from ..auth.dependencies import AccessTokenBearer, get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session_ini import get_session
from .user_schema import UserEditModel
from ..auth.service import AuthService
from ..db.models import User

user_router = APIRouter()
auth_service = AuthService()



@user_router.get('/fetch_current_user')
async def current_user(user: dict = Depends(get_current_user)):
    return user

@user_router.patch('/edit_details')
async def update_userinfo(update_info: UserEditModel, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    update_info_dict = update_info.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True)

    update_user = await auth_service.update_user(uid=user.uid, user_data=update_info_dict, session=session)

    return update_user
