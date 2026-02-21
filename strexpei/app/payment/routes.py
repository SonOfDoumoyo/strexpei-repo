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
from ..auth.dependencies import get_current_user
from ..auth.service import AuthService

payment_router = APIRouter()
auth_service = AuthService()
company_service = CompanyService()
staff_service = StaffService()

BASE_URL = Config.MONNIFY_BASE_URL
CONTRACT_CODE = Config.MONNIFY_CONTRACT_CODE
PAYSTACK_SECRET_KEY = Config.PAYSTACK_SECRET_KEY

@payment_router.get('/see_receipt')
async def get_tranfers_receipts():
    pass

@payment_router.get('/successful_payments')
async def get_all_paid():
    pass

@payment_router.get('/failed_payments')
async def get_all_failed():
    pass

@payment_router.get('/retry_failed_payments')
async def retry_payments():
    pass

@payment_router.post('/send_payment/{company_id}')
async def make_payment(company_id: uuid.UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    valid_company = await company_service.get_company_by_cid(cid=company_id, session=session)

    if not valid_company:
        raise CompanyNotFound()
    
    if valid_company.manager_id != user.uid:
        raise InsufficientPermission()
    
    staffs = await staff_service.get_staffs_by_cid(cid=valid_company.cid, session=session)

    if not staffs:
        return {'message':'no staffs yet'}
    
    headers = {
        'Authorization':f'Bearer {PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json'
    }
    subaccounts_payload = []
    total_salary = 0
    for staff in staffs:
        user_staff = await auth_service.get_user_by_uid(uid=staff.user_id, session=session)

        total_salary += int(staff.salary)

        sub_acc = staff.sub_account
        if not sub_acc:

            url = 'https://api.paystack.co/subaccount'

            payload = {
                'business_name': valid_company.company_name,
                'settlement_bank': staff.bankcode,
                'account_number': staff.accountnumber,
                'percentage_charge': 0
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                data = response.json()

            sub_acc = data.get('data').get('subaccount_code')
            update_staff = await staff_service.update_company_staff(staff=staff, staff_update_dict={'sub_account':sub_acc}, session=session)
        
        if len(staffs) == 1:

            url4 = 'https://api.paystack.co/transaction/initialize'

            payload4 = {
                'email': user.email,
                'amount': total_salary * 100,
                'currency': 'NGN',
                'subaccount': sub_acc,
                'metadata': {
                    'staff_email': user_staff.email
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url4, json=payload4, headers=headers)
                return response.json()
                    

        subaccounts_payload.append({'subaccount':sub_acc, 'share':int(staff.salary) * 100})

    
        payload2 = {
            'name': user_staff.firstname,
            'type': 'flat',
            'subaccounts': subaccounts_payload,
            'currency': 'NGN'
        }

    url2 = 'https://api.paystack.co/split'
    async with httpx.AsyncClient() as client:
        response2 = await client.post(url2, json=payload2, headers=headers)
        data2 = response2.json()

    split_code = data2.get('data').get('split_code')

    url3 = 'https://api.paystack.co/transaction/initialize'

    payload3 = {
        'email': user.email,
        'amount': total_salary * 100,
        'currency': 'NGN',
        'split_code': split_code
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url3, json=payload3, headers=headers)
        return response.json()