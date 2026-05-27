from fastapi import APIRouter, Depends
from ..db.session_ini import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth.auth_schema import UserModel
from .service import WorkerService
from ...errors import UserNotFound


worker_router = APIRouter()
work_service = WorkerService()

@worker_router.get("/get_user/{user_uid}")
async def get_a_user(user_uid: str,session: AsyncSession = Depends(get_session)):
    user = await work_service.get_strexpei_user(user_uid, session)
    if not user:
        return UserNotFound()
    
    return {"users":UserModel.model_validate(user)}