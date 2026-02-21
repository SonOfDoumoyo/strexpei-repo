from fastapi import APIRouter, Depends, status, BackgroundTasks
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from ..auth.utils import create_url_safe_token, decode_url_safe_token
from ..auth.dependencies import AccessTokenBearer, RefreshTokenBearer, RoleChecker, get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session_ini import get_session
from ...config import Config
import httpx
from ..bank.main import get_access_token
import uuid
from .staff_schema import JoinRequestStaffModel, GetAllStaffModel, UpdateAccountDetModel
from ..auth.service import AuthService
from ..company.service import CompanyService
from ...errors import (
    UserNotFound,
    CompanyNotFound,
    InvalidToken,
    ExistingStaffConflict,
    StaffNotFound,
    InvalidBankDetails
)
from ..db.models import User
import asyncio
import logging
from .service import StaffService
from ...mail import create_message, mail

admin_role = RoleChecker(['admin'])
staff_router = APIRouter()
staff_service = StaffService()
company_service = CompanyService()
auth_service = AuthService()


async def retry_email(message, n:int = 10):
    
    for attempt in range(1, n + 1):
        try:
            await mail.send_message(message)
            logging.info(f"Invite email sent successfully on attempt {attempt}")
            return "successful"
            
            
        except Exception as e:
            logging.warning(f"Attempt {attempt} failed: {e}")
            if attempt < n:
            
                await asyncio.sleep(2 ** attempt)
    logging.error("All retry attempts failed")            
    return "unsuccessful"

@staff_router.get('/get_staffs', dependencies=[Depends(admin_role)], response_model=GetAllStaffModel)
async def get_all_staffs(session: AsyncSession = Depends(get_session)):
    staffs = await staff_service.get_all_staffs(session)

    if not staffs:
        staffs = 'No staffs yet'
     
    return {'staffs':staffs}

@staff_router.get('/request_status/{cid}')
async def check_request_status(cid: uuid.UUID):
    pass

@staff_router.get('/salary_history')
async def get_salary_history():
    pass

@staff_router.get('/request_status/{cid}')
async def check_request_status(cid: uuid.UUID):
    pass

@staff_router.get('/salary_history')
async def get_salary_history():
    pass



@staff_router.get('/accept_request/{token}')
async def accept_join_request(token: str, session: AsyncSession = Depends(get_session)):
    token_details = decode_url_safe_token(token)

    if not token_details:
        raise InvalidToken()
    
    user_id = token_details['user_id']
    company_id = token_details['company_id']

    valid_user = await auth_service.get_user_by_uid(uid=user_id, session=session)

    if not valid_user:
        raise UserNotFound()
    
    valid_company = await company_service.get_company_by_cid(cid=company_id, session=session)

    if not valid_company:
        raise CompanyNotFound()
    
    add_staff = await staff_service.add_staff_to_company(user_details=valid_user, cid=valid_company.cid, role=token_details['position'], session=session)

    return JSONResponse(
        content={
            'message':f'successfully added {valid_user.firstname} to {valid_company.company_name} Company'
        },
        status_code=status.HTTP_201_CREATED
    )
    

@staff_router.post('/join_request_company')
async def request_to_join_organization(bg_tasks: BackgroundTasks, request_info: JoinRequestStaffModel, token_details: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)):
     
    token_user_id = token_details['user']['user_uid']

    valid_user = await auth_service.get_user_by_uid(uid=token_user_id, session=session)

    if not valid_user:
        raise UserNotFound()
    
    existing_staff = await staff_service.get_staff_by_uid(user_id=token_user_id, session=session)
    if existing_staff:
        raise ExistingStaffConflict()
     
    first_name = valid_user.firstname
    company_id = request_info.company_id
    valid_company = await company_service.get_company_by_cid(cid=company_id, session=session)

    if not valid_company:
        raise CompanyNotFound()
    
    #creating a token with the users uid so we can add them to the company if accepted
    send_data = {'user_id':str(valid_user.uid)}
    
    request_dict_data = request_info.model_dump_json()
    send_data['request_data'] = request_dict_data

    print(send_data)

    token = create_url_safe_token(send_data)
    
    email, verified_company = await staff_service.get_manager_by_company(cid=company_id, session=session)
    
    email_details = {
        'staff_name':valid_user.firstname,
        'staff_role':request_info.position,
        'company_name':valid_company.company_name
    }

    #details to be passed in as token
    data_details = {'company_id':str(valid_company.cid),
                    'user_id':str(valid_user.uid),
                    'role':request_info.position,
                    }
    
    token = create_url_safe_token(data=data_details)

    subject = f"Request to Join {valid_company.company_name}"
    body = await staff_service.request_email(details=email_details, token=token)

    message = create_message(
        recipients=[email],
        subject=subject,
        body=body
    )
    bg_tasks.add_task(retry_email, message=message)

    return JSONResponse(
        content={
            'message':'Request sent successfully'
        },
        status_code=status.HTTP_200_OK
    )


@staff_router.post('/update_bank_details/{company_id}')
async def bank_details_update(company_id: uuid.UUID, update_data: UpdateAccountDetModel, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    existing_company = await company_service.get_company_by_cid(cid=company_id, session=session)

    if not existing_company:
        raise CompanyNotFound()
    
    valid_staff = await staff_service.get_staff_by_uid_and_cid(user_id=user.uid, cid=existing_company.cid, session=session)

    if not valid_staff:
        raise StaffNotFound()
    
    update_data_dict = update_data.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=True)
    BASE_URL = Config.MONNIFY_BASE_URL
    token = await get_access_token()

    try:

        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{BASE_URL}/api/v1/disbursements/account/validate",
                params={
                    "accountNumber": update_data.accountnumber,
                    "bankCode": update_data.bankcode
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )

    except httpx.TimeoutException as e:
        logging.warning(f"[DEBUG] {e}")

    data = res.json()
    if not data.get("requestSuccessful"):
        raise HTTPException(status_code=400, detail=data)
    
    if data.get('responseBody').get('accountName').upper() != update_data.accountname.upper():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={'message':'account name mismatch'})
   
    
    update_details = await staff_service.update_company_staff(staff=valid_staff, staff_update_dict=update_data_dict, session=session)
    return update_details

