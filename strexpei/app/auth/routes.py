from fastapi import APIRouter, Depends, BackgroundTasks, status, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import HTTPException
from .service import AuthService, verify_email_html, account_verified_html, generate_otp, resend_otp
from .auth_schema import SignUpModel, LoginModel, PasswordResetModel, StatusModel, LoginRequest, RefreshRequest
from ..admin.admin_schema import AllUsersModel
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session_ini import get_session
from .utils import create_url_safe_token, decode_url_safe_token, verify_password, create_access_token, generate_password_hash, create_refresh_token, refresh_access_token
from ...mail import create_message, mail
from .dependencies import AccessTokenBearer, RefreshTokenBearer, get_current_user, get_full_user, LogoutTokenBearer
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
from ..admin.admin_schema import AllUsersModel
import logging
import asyncio
import uuid
from ...config import Config
import time
from datetime import timedelta, datetime
from .redis import verify_password_reset_otp, save_password_reset_otp, store_refresh_token, add_jti_to_blocklist
from ..staffs.service import StaffService
from ..company.service import CompanyService



REFRESH_TOKEN_EXPIRY=7

company_service = CompanyService()
staff_service = StaffService()
auth_service = AuthService()

auth_router = APIRouter()




async def retry_email(message, n:int = 1):
    
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


@auth_router.get("/current_user")
async def fetch_current_user(user: dict = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authenticated")
    return user
        
    
@auth_router.post("/refresh_access")
async def access_token_refresh(request: Request,response: Response, token_details: dict = Depends(RefreshTokenBearer()), session: AsyncSession = Depends(get_session)):
    
    uid = token_details.get("user_uid")
    device = token_details.get("device")
    user = await auth_service.get_user_by_email(token_details['user_data']['email'], session)
    
    if not user:
        raise UserNotFound()
    
    if user.status != "suspended":
        new_access_token = await refresh_access_token(
            user=user,
            token_data=token_details,
            
        )
        if not new_access_token:
            raise InvalidToken()
        
        refresh_token, jti, payload = create_refresh_token(
            user_data = {
                'email':user.email,
                'user_uid':str(user.uid),
                'device':device
            },
            refresh = True,
            expiry = timedelta(days=REFRESH_TOKEN_EXPIRY)
        )

        await store_refresh_token(str(user.uid), payload, device)


        response.set_cookie(
            key=f"refresh_token_{uid}",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
            max_age=7 * 24 * 60 * 60,
            domain="localhost"
        )    
        return JSONResponse(
            content={
                "user":{
                      "email":token_details['user_data']['email'],
                      "access_token":new_access_token,
                      "user_id":token_details['user_data']['user_uid']
                },
            },
        )
        
    raise AccountSuspendedError()
    

@auth_router.post('/verify/{email}/{otp_code}')
async def verify_account(email: str, otp_code: str, session: AsyncSession = Depends(get_session)):
    
    user_email = email
    
    if user_email:
        account_to_verify = await auth_service.get_user_by_email(user_email, session)
        
        if not account_to_verify:
            raise UserNotFound()
        
        verify_otp, message = await verify_password_reset_otp(email, otp_code)
        if message == "OTP expired or invalid":
            raise InvalidOtpCode()
    
        if message == "Maximum OTP attempts exceeded":
            raise MaxOtpAttempts()
            
        if message == "Invalid OTP":
            raise WrongOtp()
        
        uid = account_to_verify.uid
        
        await auth_service.update_user(uid, {"verified":True, "status":"active"}, session)
        
        return JSONResponse(
            content={
                "message":"verified"
                },
            status_code=status.HTTP_200_OK
        )
    
    return JSONResponse(
        content={
            "message":"Error occured during verification"
        },
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


@auth_router.post('/otp_resend/{email}')
async def resend_ver_otp(request: Request, email: str, bg_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):

    user = await auth_service.get_user_by_email(email=email, session=session)
    if not user:
        raise UserNotFound()
    
    otp = await resend_otp(user_id=user.uid, email=email)

    if isinstance(otp, dict) and not otp.get("success"):
        return JSONResponse(
            content={
                "allowed":otp.get("success"),
                "message":otp.get("message"),
            }
        )
    
    html_body = verify_email_html(request=request, otp=otp, name=user.firstname)
        
    email = user.email
    subject= f"Your verification code: {otp}"
    body = html_body

    
    await save_password_reset_otp(user_email=email, otp=str(otp), expiry_seconds=300)
        
    message = create_message(
        recipients=[email],
        subject=subject,
        body=body
    )
    bg_tasks.add_task(retry_email, message=message)
    
    return JSONResponse(
        content={
            "code":str(otp),
            "success": True,
            "message": "Account created. Check your email to verify."
        },
        status_code=status.HTTP_201_CREATED
    )            
        
    
@auth_router.post('/sign_up')
async def creating_account(request: Request ,bg_tasks: BackgroundTasks, signup_data: SignUpModel, session: AsyncSession = Depends(get_session)):
    
    created = await auth_service.create_account(signup_data, session)
    
    if not created:
        raise UserAlreadyExists()
    
    otp = await generate_otp()
    html_body = verify_email_html(request=request, otp=otp, name=signup_data.firstname)
        
    email = signup_data.email
    subject= f"Your verification code: {otp}"
    body = html_body

    
    await save_password_reset_otp(user_email=email, otp=otp, expiry_seconds=300)
        
    message = create_message(
        recipients=[email],
        subject=subject,
        body=body
    )
    bg_tasks.add_task(retry_email, message=message)
    
    return JSONResponse(
        content={
            "code":str(otp),
            "success": True,
            "message": "Account created. Check your email to verify."
        },
        status_code=status.HTTP_201_CREATED
    )  


@auth_router.get('/get/{email}')
async def get_signin_email(email: str, session: AsyncSession = Depends(get_session)):
    user = await auth_service.get_user_by_email(email=email, session=session)
    if not user:
        raise UserNotFound()
    
    return True
        

@auth_router.get('/sign_in/{email}/{password}/{remember_me}')
async def login(bg_tasks: BackgroundTasks, response: Response, email: str, password: str, request: Request, session: AsyncSession = Depends(get_session), remember_me: bool = False):
    user = await auth_service.get_user_by_email(email, session)
    
    if not user:
        raise UserNotFound()
    
    fetched_password = user.password
    
    
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
        device = auth_service.get_device_info(request)
        refresh_token, jti, payload = create_refresh_token(
            user_data = {
                'email':user.email,
                'user_uid':str(user.uid),
                'device':device,
            },
            refresh = True,
            expiry = timedelta(days=REFRESH_TOKEN_EXPIRY)
        )
        
        device = auth_service.get_device_info(request)
        await store_refresh_token(access_data['user_uid'], payload, device)
        
        if user.verified == False:
            otp = await generate_otp()
            html_body = verify_email_html(request=request, otp=otp, name=user.firstname)
                
            email = user.email
            subject= f"Your verification code: {otp}"
            body = html_body

            
            await save_password_reset_otp(user_email=email, otp=otp, expiry_seconds=300)
                
            message = create_message(
                recipients=[email],
                subject=subject,
                body=body
            )
            bg_tasks.add_task(retry_email, message=message)
            
            resp = JSONResponse(
                content={
                    "code":str(otp),
                    "success": True,
                    "message": "Check your email to verify."
                },
                status_code=status.HTTP_201_CREATED
            )

            resp.set_cookie(
                key=f"refresh_token_{user.uid}",
                value=refresh_token,
                httponly=True,
                secure=False,
                samesite="lax",
                path="/",
                max_age=7 * 24 * 60 * 60,
                domain="localhost"
            )

            return resp
    current_user = await get_full_user(user_id=user.uid, session=session)
    if current_user:

        resp = JSONResponse(
            content={
                "message":"login successful",
                "access_token":access_token,
                "refresh_token":refresh_token,
                "user":{
                    "user_id":str(user.uid),
                    'user_email':user.email,
                    "account_status":user.status,
                    "user_details":current_user.model_dump_json()
                },
            },
            status_code=status.HTTP_200_OK
        )

        max_age = 60 * 60 * 24 * 30 if remember_me else 60 * 60 * 24
        resp.set_cookie(
            key=f"refresh_token_{user.uid}",
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
            domain="localhost",
            max_age=max_age
        )

        return resp
    
    
    raise InvalidCredentials()


@auth_router.post('/logout')
async def logout_current_user(response: Response, token: str = Depends(LogoutTokenBearer())):
    
    response.delete_cookie(key="refresh_token", httponly=True, domain="localhost", samesite="lax", secure=False, path="/")
    await add_jti_to_blocklist(token)
    return JSONResponse(
        content={
            'message': 'Logged out successfully'
        },
        status_code=status.HTTP_200_OK
    )
    
    
@auth_router.post('/reset_password/{email}')
async def password_reset(email: str, bg_tasks:BackgroundTasks, session: AsyncSession = Depends(get_session)):
    
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
async def delete_your_account(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    
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