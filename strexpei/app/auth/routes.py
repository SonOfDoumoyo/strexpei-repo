from fastapi import APIRouter, Depends, BackgroundTasks, status, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from .service import AuthService, verify_email_html, account_verified_html, generate_otp
from .auth_schema import SignUpModel, LoginModel, PasswordResetModel, StatusModel
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session_ini import get_session
from .utils import create_url_safe_token, decode_url_safe_token, verify_password, create_access_token, generate_password_hash, create_refresh_token, refresh_access_token
from ...mail import create_message, mail
from .dependencies import AccessTokenBearer, RefreshTokenBearer, get_current_user, AccountStatus
from ...errors import(
    UserAlreadyExists,
    UserNotFound,
    InvalidCredentials,
    InvalidOtpCode,
    WrongOtp,
    MaxOtpAttempts,
    InvalidToken,
    AccountSuspendedError,
    AccountDeletedError,
    ExpiredToken
)
import logging
import asyncio
import uuid
from ...config import Config
import time
from datetime import timedelta, datetime
from .redis import verify_password_reset_otp, save_password_reset_otp, store_refresh_token
from ..staffs.service import StaffService
from ..company.service import CompanyService



REFRESH_TOKEN_EXPIRY=7

company_service = CompanyService()
staff_service = StaffService()
auth_service = AuthService()

auth_router = APIRouter()




async def retry_email(message, n:int = 10):
    
    for attempt in range(1, n + 1):
        try:
            await mail.send_message(message)
            logging.info(f"Email sent successfully on attempt {attempt}")
            return "successful"
            
            
        except Exception as e:
            logging.warning(f"Attempt {attempt} failed: {e}")
            if attempt < n:
            
                await asyncio.sleep(2 ** attempt)
    logging.error("All retry attempts failed")            
    return "unsuccessful"
        
    
@auth_router.get("/refresh_access")
async def access_token_refresh(request: Request, token_details: dict = Depends(RefreshTokenBearer()), session: AsyncSession = Depends(get_session)):
    
    device = auth_service.get_device_info(request)
    user = await auth_service.get_user_by_email(token_details['user_data']['email'], session)
    
    if not user:
        raise UserNotFound()
    
    if user.status != "suspended":
        new_access_token = await refresh_access_token(
            user=user,
            token_data=token_details,
            device=device
        )
        if not new_access_token:
            raise InvalidToken()
            
        return JSONResponse(
            content={
                "user":{
                      "email":token_details['user_data']['email'],
                      "access_token":new_access_token
                },
            },
        )
        
    raise AccountSuspendedError()
    

@auth_router.get('/verify/{token}')
async def verify_account(token: str, session: AsyncSession = Depends(get_session)):
    
    
    token_data = decode_url_safe_token(token)
    user_email = token_data
    
    if user_email:
        account_to_verify = await auth_service.get_user_by_email(user_email, session)
        if not account_to_verify:
            raise UserNotFound()
    
        uid = account_to_verify.uid
        
        await auth_service.update_user(uid, {"verified":True}, session)
        await auth_service.update_user(uid, {'status':'active'}, session)
        respond = account_verified_html(login_link="haha")
        
        return HTMLResponse(respond, status_code=status.HTTP_200_OK)
    
    return JSONResponse(
        content={
            "message":"Error occured during verification"
        },
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
            
        
    
@auth_router.post('/sign_up')
async def creating_account(request: Request ,bg_tasks: BackgroundTasks, signup_data: SignUpModel, session: AsyncSession = Depends(get_session)):
    
    created = await auth_service.create_account(signup_data, session)
    
    if not created:
        raise UserAlreadyExists()
    
       
    token = create_url_safe_token(signup_data.email)
    html_body = verify_email_html(verification_link=token, request=request)
        
    email = signup_data.email
    subject= "Verify your email to activate your Strexpei account"
    body = html_body
        
    message = create_message(
        recipients=[email],
        subject=subject,
        body=body
    )
    bg_tasks.add_task(retry_email, message=message)
    
    return JSONResponse(
        content={
            "message": "Account created. Check your email to verify."
        },
        status_code=status.HTTP_201_CREATED
    )
            
        

@auth_router.post('/sign_in')
async def login(request: Request, login_data: LoginModel, session: AsyncSession = Depends(get_session), account_status: str = Depends(AccountStatus())):
    email = login_data.email
    user = await auth_service.get_user_by_email(email, session)
    
    if not user:
        raise UserNotFound()
    
    fetched_password = user.password
    password = login_data.password
    
    
    valid_password = verify_password(password, fetched_password)
    
    if valid_password:
        if user.status == 'deleted':
            staff_data = await staff_service.get_staff_by_uid(user.uid, session)
            company_data = await company_service.get_company_by_uid(user.uid, session)
            if company_data:
                company_delete = {
                    "is_deleted":False,
                    "deleted_at":None,
                    "purge_at": None
                }
                await company_service.update_company(user.uid, company_delete, session)
            
            
            if staff_data:
                staff_delete = {
                    "is_deleted":False,
                    "deleted_at":None,
                    "purge_at":None
                }
                await staff_service.update_staff(user.uid, staff_delete, session)
            
            
            deleted_at = datetime.utcnow()
            purge_at = datetime.utcnow() + timedelta(days=1)
            delete_data = {
                "status":"active",
                "deleted_at":None,
                "purge_at":None
            }
            await auth_service.update_user(user.uid, delete_data, session)
        
        access_data = {
                'email':user.email,
                'role':user.role,
                'user_uid':str(user.uid),
                'created_datetime': user.created_at.isoformat(),
        }
        if user.role == 'admin':
            access_data['admin'] = 'admin'
        
        access_token = create_access_token(user_data=access_data)
            
        refresh_token, jti, payload = create_refresh_token(
            user_data = {
                'email':user.email,
                'user_uid':str(user.uid)
            },
            refresh = True,
            expiry = timedelta(days=REFRESH_TOKEN_EXPIRY)
        )
        
        device = auth_service.get_device_info(request)
        await store_refresh_token(access_data['user_uid'], payload, device)
        
            
        return JSONResponse(
            content={
                "message":"login successful",
                "access_token":access_token,
                "refresh_token":refresh_token,
                "user":{
                    "user_id":str(user.uid),
                    'user_email':user.email
                },
            },
            status_code=status.HTTP_200_OK
        )
        
        
    raise InvalidCredentials()
        
    
    
@auth_router.post('/reset_password/{email}')
async def password_reset(email: str, bg_tasks:BackgroundTasks, session: AsyncSession = Depends(get_session), account_status: str = Depends(AccountStatus())):
    
    user = await auth_service.get_user_by_email(email, session)
    
    if not user:
        raise UserNotFound()
    
    email = user.email
    otp = await generate_otp()

    
    await save_password_reset_otp(email, otp, expiry_seconds=60)
    subject = "Your One-Time Password (OTP) for Account Verification"
    
    body = f"""
    <p>Hello {user.firstname},</p>
    <p>Your OTP is:</p>
    <strong style="font-size:22px; letter-spacing:3px; color:#111; font-family:monospace;">{otp}</strong>
    <p>This code expires in <strong>60 seconds</strong>.</p>
    <p>If you didn't request this, ignore this email.</p>
    <p><strong>Strexpei Security Team</strong></p>
    """
    
    
    message = create_message(
        recipients=[email],
        subject=subject,
        body=body
    )
    
    bg_tasks.add_task(retry_email, message=message)
    
    return JSONResponse(
        content={
            'message':'(OTP) has been sent to your email'
        },
        status_code=status.HTTP_200_OK
    )
   
    
    
@auth_router.post('/new_password')
async def enter_new_password(reset_data: PasswordResetModel, session: AsyncSession = Depends(get_session)):
    
    email = reset_data.email
    
    valid_user = await auth_service.get_user_by_email(email, session)
    
    if not valid_user:
        raise UserNotFound()
    
    otp_code = reset_data.otp   
    verify_otp, message = await verify_password_reset_otp(email, otp_code)
    

    if message == "OTP expired or invalid":
        raise InvalidOtpCode()
    
    if message == "Maximum OTP attempts exceeded":
        raise MaxOtpAttempts()
        
    if message == "Invalid OTP":
        raise WrongOtp()
    

    password = generate_password_hash(reset_data.password)
    await auth_service.update_user(valid_user.uid,{'password':password}, session)
        
    return JSONResponse(
        content={
            "message":"Password changed successfully"
        },
        status_code=status.HTTP_200_OK
    )
    
    
@auth_router.delete('/delete_account')
async def delete_your_account(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session), account_status: str = Depends(AccountStatus())):
    
    user_uid = user.uid
    email = user.email
    
    user_data = await auth_service.get_user_by_uid(user_uid, session)
    
    if user_data.status != 'deleted':
        deleted_at = datetime.utcnow()
        purge_at = datetime.utcnow() + timedelta(days=1)
        
        staff_data = await staff_service.get_staff_by_uid(user_uid, session)
        company_data = await company_service.get_company_by_uid(user_uid, session)
        if company_data:
            company_delete = {
                "is_deleted":True,
                "deleted_at":deleted_at,
                "purge_at": purge_at
            }
            await company_service.update_company(user_uid, company_delete, session)
        
        
        if staff_data:
            staff_delete = {
                "is_deleted":True,
                "deleted_at":deleted_at,
                "purge_at": purge_at
            }
            await staff_service.update_staff(user_uid, staff_delete, session)
            
        delete_data = {
            "status":"deleted",
            "deleted_at":deleted_at,
            "purge_at": purge_at
        }
        await auth_service.update_user(user_uid, delete_data, session)
        return JSONResponse(
            content={
                "message":f"Your account will be deleted on {purge_at}"
            },
            status_code=status.HTTP_200_OK
        )
    
    if user_data.status == 'deleted':
        raise AccountDeletedError()