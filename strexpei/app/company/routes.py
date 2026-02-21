from fastapi import APIRouter, Depends, BackgroundTasks, status, Form, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from ..auth.service import AuthService, verify_email_html, account_verified_html, generate_otp
from .company_schema import CompanyModel, AddCompanyModel, ResponseCompanyModel, CreateInviteModel
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session_ini import get_session
from ..auth.utils import create_url_safe_token, decode_url_safe_token, verify_password, create_access_token, generate_password_hash,create_company_token, create_refresh_token, refresh_access_token, create_company_refresh_token, decode_token
from ...mail import create_message, mail
from ..auth.dependencies import AccessTokenBearer, RefreshTokenBearer, get_current_user, RoleChecker
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
    InviteExpired,
    CompanyNotFound
)
import logging
import asyncio
import uuid
from ...config import Config
import time
from datetime import timedelta, datetime
from ..auth.redis import verify_password_reset_otp, save_password_reset_otp, store_refresh_token
from ..staffs.service import StaffService
from ..staffs.staff_schema import DisplayToManagerModel
from .service import CompanyService
from ..db.models import Staff, User


company_router = APIRouter()
company_service = CompanyService()
useradmin_session = RoleChecker(['user','admin'])
REFRESH_TOKEN_EXPIRY = 7
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


@company_router.get('/get_company_staffs', response_model=DisplayToManagerModel)
async def fetch_company_staffs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    
    user_id = user.uid
    staffs = await company_service.get_a_company_staffs(manager_id=user_id, session=session)

    return {'staffs':staffs}
    


@company_router.get('/valid_invite/{token:path}', response_class=HTMLResponse)
async def get_invite_link(token: str, session: AsyncSession = Depends(get_session)):
    
    try:
        invite_details = await company_service.get_invite_with_token(token, session)
        
        if not invite_details:
            raise InviteExpired()
        
        token_details = decode_url_safe_token(token)
        
        company_id = token_details['company_id']
        email = token_details['email']
        position = token_details['position']
        valid_company = await company_service.get_company_by_cid(company_id, session)
        if not valid_company:
            raise InvalidToken()
        
        #checks if the invited is an existing user    
        user_exists = await auth_service.get_user_by_email(email, session)
        if not user_exists:
            # Response 1
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Sign Up</title>
                    <style>
                        * {
                            margin: 0;
                            padding: 0;
                            box-sizing: border-box;
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        }
            
                        body {
                            height: 100vh;
                            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: #fff;
                        }
            
                        .card {
                            background: rgba(255, 255, 255, 0.08);
                            backdrop-filter: blur(12px);
                            border-radius: 16px;
                            padding: 40px;
                            max-width: 420px;
                            width: 90%;
                            text-align: center;
                            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
                        }
            
                        h1 {
                            font-size: 28px;
                            margin-bottom: 10px;
                            font-weight: 600;
                        }
            
                        p {
                            font-size: 15px;
                            opacity: 0.9;
                            margin-bottom: 30px;
                            line-height: 1.6;
                        }
            
                        .btn {
                            display: inline-block;
                            padding: 14px 28px;
                            background: #00d4ff;
                            color: #000;
                            text-decoration: none;
                            font-weight: 600;
                            border-radius: 8px;
                            transition: transform 0.2s ease, box-shadow 0.2s ease;
                        }
            
                        .btn:hover {
                            transform: translateY(-2px);
                            box-shadow: 0 10px 25px rgba(0, 212, 255, 0.4);
                        }
            
                        .footer-text {
                            margin-top: 20px;
                            font-size: 13px;
                            opacity: 0.7;
                        }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>Create Your Account</h1>
                        <p>
                            Sign up today to streamline your experience, manage your activities,
                            and unlock full access to all features.
                        </p>
                        <a href=f"http://{Config.DOMAIN}/api/v1.0/auth/sign_up" class="btn">Get Started</a>
                        <div class="footer-text">
                            Secure • Fast • Simple
                        </div>
                    </div>
                </body>
                </html>
                """,
                status_code=status.HTTP_200_OK
            )
        
        confirm_link = f"http://{Config.DOMAIN}/api/v1.0/staffs/accept_request/{token}"
        # Response 2
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Company Info</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    }}
        
                    body {{
                        height: 100vh;
                        background: linear-gradient(135deg, #141e30, #243b55);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: #fff;
                    }}
        
                    .card {{
                        background: rgba(255, 255, 255, 0.08);
                        backdrop-filter: blur(14px);
                        border-radius: 18px;
                        padding: 40px;
                        max-width: 480px;
                        width: 92%;
                        box-shadow: 0 25px 50px rgba(0,0,0,0.4);
                        animation: fadeIn 0.6s ease-in-out;
                    }}
        
                    @keyframes fadeIn {{
                        from {{
                            opacity: 0;
                            transform: translateY(15px);
                        }}
                        to {{
                            opacity: 1;
                            transform: translateY(0);
                        }}
                    }}
        
                    h1 {{
                        font-size: 26px;
                        margin-bottom: 10px;
                        font-weight: 600;
                    }}
        
                    p {{
                        font-size: 15px;
                        opacity: 0.85;
                        margin-bottom: 25px;
                    }}
        
                    .info {{
                        background: rgba(0, 0, 0, 0.25);
                        border-radius: 12px;
                        padding: 20px;
                    }}
        
                    .row {{
                        display: flex;
                        justify-content: space-between;
                        padding: 12px 0;
                        border-bottom: 1px solid rgba(255,255,255,0.1);
                    }}
        
                    .row:last-child {{
                        border-bottom: none;
                    }}
        
                    .label {{
                        opacity: 0.7;
                        font-size: 14px;
                    }}
        
                    .value {{
                        font-weight: 600;
                        text-align: right;
                        max-width: 60%;
                        word-wrap: break-word;
                    }}
        
                    .actions {{
                        margin-top: 30px;
                        display: flex;
                        gap: 12px;
                    }}
        
                    .btn {{
                        flex: 1;
                        padding: 14px;
                        border-radius: 10px;
                        border: none;
                        cursor: pointer;
                        font-weight: 600;
                        transition: transform 0.2s ease, box-shadow 0.2s ease;
                    }}
        
                    .btn-primary {{
                        background: #00d4ff;
                        color: #000;
                    }}
        
                    .btn-secondary {{
                        background: rgba(255,255,255,0.15);
                        color: #fff;
                    }}
        
                    .btn:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 12px 25px rgba(0,0,0,0.35);
                    }}
        
                    .secure {{
                        margin-top: 18px;
                        font-size: 13px;
                        opacity: 0.6;
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Connect to Company</h1>
                    <p>Please confirm the company details below before proceeding.</p>
        
                    <div class="info">
                        <div class="row">
                            <span class="label">Company ID</span>
                            <span class="value">{company_id}</span>
                        </div>
                        <div class="row">
                            <span class="label">Company Name</span>
                            <span class="value">{valid_company.company_name}</span>
                        </div>
                        <div class="row">
                            <span class="label">Company Address</span>
                            <span class="value">{valid_company.address}</span>
                        </div>
                    </div>
        
                    <div class="actions">
                        <button class="btn btn-secondary">
                        <a href="https://mail.google.com"
                        target="_blank"
                        rel="noopener noreferrer">
                        Cancel
                        </a>
                        
                        </button>
                        <button class="btn btn-primary"><a href="{confirm_link}">Confirm & Continue</a></button>
                    </div>
        
                    <div class="secure">
                        Encrypted connection • Verified company
                    </div>
                </div>
            </body>
            </html>
            """,
            status_code=status.HTTP_200_OK
        )
    
    except Exception as e:
        raise e
    

@company_router.get('/get_companies')
async def get_all_companies(session: AsyncSession = Depends(get_session)):
    all_companies = await company_service.get_all_added_companies(session)
    return all_companies


@company_router.post('/adding_company')#, #response_model=ResponseCompanyModel)
async def add_your_company(request: Request, add_company: AddCompanyModel = Body(...), user_data: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)):
    
    
    uid = user_data['user']['user_uid']
    new_company = await company_service.adding_company(uid, add_company, session)
    
    return {
        'company':new_company,
    }


@company_router.post('/invite_staff/{company_id}')
async def invite_member(company_id: uuid.UUID, bg_tasks: BackgroundTasks, invite_data: CreateInviteModel = Body(...), user_data: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)):
    
    #gets the managers id
    manager_id = user_data['user']['user_uid']
    manager_email = user_data['user']['email']
    user = await auth_service.get_user_by_email(manager_email, session)
    if not user:
        UserNotFound()
    
    if user.status == 'active':
        created_invite = await company_service.invite_users(company_id, invite_data, session)
        
        
        invite_link = created_invite['url_token']
        company_name = created_invite['company_name']
        html_invite_body = await company_service.invite_email_html(invite_link, company_name)
        
        email = invite_data.email
        
        subject = f"You have been invited to join {created_invite['company_name']}"
        body = html_invite_body
        
        message = create_message(
            recipients = [email],
            subject = subject,
            body = body
        )
        bg_tasks.add_task(retry_email, message=message)
        
    return JSONResponse(
        content = {
            'message':'invite sent successfully'
        },
        status_code=status.HTTP_200_OK
    )


@company_router.delete('/delete_company/{company_id}', dependencies=[Depends(useradmin_session)])
async def delete_company_from_db(company_id: uuid.UUID, user_data: dict = Depends(AccessTokenBearer()), session: AsyncSession = Depends(get_session)):
    
    user_id = user_data['user']['user_uid']
    user_exists = await auth_service.get_user_by_uid(user_id, session)
    if not user_exists:
        raise UserNotFound()
    
    erase_company = await company_service.erase_company(company_id, session)

    if not erase_company:
        raise CompanyNotFound()

    return JSONResponse(
        content={
            'message':'company deleted successfully'
        },
        status_code=status.HTTP_204_NO_CONTENT
    )
