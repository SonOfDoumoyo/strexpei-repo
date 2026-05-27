from fastapi import Request, status, Depends
from ..db.models import User
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from ..auth.utils import decode_token
from ..auth.redis import token_in_blocklist, get_refresh_token
from ..db.session_ini import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from .service import AuthService
from typing import List, Any, Dict
from ..admin.admin_schema import AllUsersModel
import uuid
from ...errors import AccountNotVerified, InsufficientPermission, ExpiredToken, InvalidAuthorizationCredentials, RefreshTokenRequired, AccessTokenRequired, InvalidToken, RevokedToken, CompanyTokenRequired, InactiveAccount, AccountBannedError, AccountDeletedError, AccountPendingError, AccountSuspendedError, UserNotFound

auth_service = AuthService()


class AccessTokenBearer:
    """Reads access token from Authorization: Bearer <token>"""
    async def __call__(self, request: Request) -> Dict[str, Any]:
        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer"):

            raise HTTPException(status_code=401, detail="Missing bearer token")
        
        token = auth.split(" ", 1)[1].strip()
        data = decode_token(token)

        if data.get("type") != "access":
            raise AccessTokenRequired()

        return data
    
class LogoutTokenBearer:
    """Reads access token from Authorization: Bearer <token>"""
    async def __call__(self, request: Request) -> Dict[str, Any]:
        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer"):

            raise HTTPException(status_code=401, detail="Missing bearer token")
        
        token = auth.split(" ", 1)[1].strip()
        data = decode_token(token)

        if data.get("type") != "access":
            raise AccessTokenRequired()

        return token

class RefreshTokenBearer(HTTPBearer):
    """Reads refresh token form HttpOnly cookie"""
    def __init__(self, auto_error: bool=True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Dict:
        uid = request.query_params.get("uid")

        if not uid:
            raise InvalidAuthorizationCredentials()
        
        token = request.cookies.get(f"refresh_token_{uid}")

        if not token:
            raise ExpiredToken()
        
        token_data = decode_token(token)

        if not token_data:
            raise InvalidToken()
        
        if not token_data.get("refresh"):
            raise RefreshTokenRequired()
        
        device = token_data.get("device")
        stored_token = await get_refresh_token(uid, device)

        if not stored_token:
            raise ExpiredToken()
        
        if stored_token != token:
            raise RevokedToken()
        
        return token_data


async def get_current_user(token_details: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)):
    user_id = token_details['user']['user_uid']
    user = await auth_service.get_user_by_uid(user_id, session)
    if user is None:
        raise UserNotFound()
    
    if user.status == "suspended":
        raise AccountSuspendedError()
        
    elif user.status == "deleted":
        raise AccountDeletedError()
    
    elif user.status == "banned":
        raise AccountBannedError()
    
    elif user.status == "pending" or user.verified == False:
        raise AccountPendingError()

    elif user.verified == True:
        return AllUsersModel.model_validate(user)
    

async def get_full_user(user_id: uuid.UUID, session: AsyncSession):
    user = await auth_service.get_user_by_uid(user_id, session)
    if user is None:
        raise UserNotFound()
    
    if user.status == "suspended":
        raise AccountSuspendedError()
        
    elif user.status == "deleted":
        raise AccountDeletedError()
    
    elif user.status == "banned":
        raise AccountBannedError()
    
    elif user.status == "pending" or user.verified == False:
        raise AccountPendingError()

    elif user.verified == True:
        return AllUsersModel.model_validate(user)



async def require_session(request: Request):
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    #validates session-id 
    return refresh_token

    
class RoleChecker:
    
    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles
        
    async def __call__(self, current_user: User = Depends(get_current_user)) -> bool:
    
        if not current_user.verified:
            raise AccountNotVerified()
        if current_user.role in self.allowed_roles:
            return True
            
        raise InsufficientPermission()
  
       