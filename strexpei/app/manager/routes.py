from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from ..db.session_ini import get_session
from ..db.models import User
from ..staffs.service import StaffService
from ..company.service import CompanyService
from fastapi.responses import JSONResponse
from ...config import Config
from ..bank.main import get_access_token
from ...errors import(
    CompanyNotFound,
    StaffNotFound,
    InsufficientPermission
)
import httpx
from ..staffs.staff_schema import SalaryUpdateModel
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from ..auth.dependencies import get_current_user, AccessTokenBearer

manager_router = APIRouter()
staff_service = StaffService()
company_service = CompanyService()

BASE_URL = Config.MONNIFY_BASE_URL
CONTRACT_CODE = Config.MONNIFY_CONTRACT_CODE
PAYSTACK_SECRET_KEY = Config.PAYSTACK_SECRET_KEY


@manager_router.get('/fund_account/{amount}')
async def fund_your_account(amount: int, user: User = Depends(get_current_user)):

    url = "https://api.paystack.co/transaction/initialize"

    headers = {
        'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json'
    }

    payload = {
        'email': user.email,
        'amount': str(amount * 100),
        'currency': 'NGN',
        'channels': ['bank', 'card', 'ussd']
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        data = response.json()

    if not data.get('status'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=data)
    
    
    return {
        'authorization_url': data['data']['authorization_url'],
        'reference': data['data']['reference']
    }


@manager_router.post('/set_salary/{company_id}/{staff_id}')
async def set_staff_salary(salary_update: SalaryUpdateModel, company_id: uuid.UUID, staff_id: uuid.UUID,user_: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):

    valid_company = await company_service.get_company_by_cid(cid=company_id, session=session)
    if not valid_company:
        raise CompanyNotFound()
    
    if not valid_company.manager_id == user_.uid:
        raise InsufficientPermission()

    valid_company_staff = await staff_service.get_staff_by_sid(sid=staff_id, session=session)

    if not valid_company_staff:
        raise StaffNotFound()

    salary_update_dict = salary_update.model_dump()
    update_staff =  await staff_service.update_company_staff(staff=valid_company_staff, staff_update_dict=salary_update_dict, session=session)

    return update_staff


@manager_router.post('/set_payday')
async def remove_a_staff():
    pass


@manager_router.delete('/remove_staff/{company_id}/{staff_id}')
async def set_staffs_payday(company_id: uuid.UUID, staff_id: uuid.UUID, user: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)):

    valid_staff = await staff_service.get_staff_by_sid(sid=staff_id, session=session)
    if not valid_staff:
        raise StaffNotFound()
    
    delete_staff = await staff_service.delete_staff(cid=company_id, sid=staff_id, session=session)

    if not delete_staff:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail= {'message': f'something went wrong: {delete_staff}'}
        )
    
    return JSONResponse(
        content={
            'message':'deleted successfully'
        },
        status_code=status.HTTP_204_NO_CONTENT
    )


@manager_router.delete('/remove_staffs')
async def staffs_removal():
    pass

