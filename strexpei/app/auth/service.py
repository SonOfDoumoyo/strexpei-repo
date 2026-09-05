from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from sqlalchemy.orm import selectinload
from ...config import Config
from .utils import generate_password_hash
from ..auth.redis import save_password_reset_otp
from .auth_schema import (
    SignUpModel,
    LoginModel,
    UserModel,
    UserUpdateModel
)
from fastapi import Request
from user_agents import parse
from ...config import Config
import uuid
from ..db.models import (
    User,
    Company,
    Staff,
    RequestJoin,
    Notification
)
from datetime import datetime, timedelta
from ...errors import(
    UserNotFound
)
from ..auth.redis import redis_client
from ..admin.admin_schema import AllUsersModel
import secrets

class AuthService:
    
    #function to get user by emsil from db
    async def get_user_by_email(self, email: str, session: AsyncSession):
        
        statement = select(User).where(User.email == email)
        result = await session.execute(statement)
        user =  result.scalars().first()
        
        return user
    
    
    #function to get user by uid   
    async def get_user_by_uid(self, uid: uuid.UUID, session: AsyncSession):
        statement = select(User).options(selectinload(User.staffs).selectinload(Staff.company), selectinload(User.staffs).selectinload(Staff.company).selectinload(Company.manager), selectinload(User.companies), selectinload(User.companies).selectinload(Company.request), selectinload(User.companies).selectinload(Company.request).selectinload(RequestJoin.creator), selectinload(User.staffs).selectinload(Staff.company).selectinload(Company.staffs), selectinload(User.request).selectinload(RequestJoin.company), selectinload(User.request).selectinload(RequestJoin.company).selectinload(Company.manager), selectinload(User.sent), selectinload(User.sent).selectinload(Notification.receiver), selectinload(User.received), selectinload(User.received).selectinload(Notification.receiver)).where(User.uid == uid)
        result = await session.execute(statement)
        user = result.unique().scalars().first()
        
        return user

      
    async def get_user_abstract(self, uid: uuid.UUID, session: AsyncSession):
        
        statement = select(User).where(User.uid == uid)
        result = await session.execute(statement)
        user = result.unique().scalars().first()
        
        return user
     
     
    #function to get user by uid from staff 
    async def get_staff_by_uid(self, uid: uuid.UUID, session: AsyncSession):
        
        statement = select(Staff).where(Staff.user_id == uid)
        result = await session.execute(statement)
        staff = result.scalars().first()
        
        return staff
        
        
    #checks if user exists
    async def user_exists(self, email: str, session: AsyncSession) -> bool:
        
        existing_user = await self.get_user_by_email(email, session)
        return existing_user is not None
        
    
    #function called for signup
    async  def create_account(self, signup_data: SignUpModel, session: AsyncSession):
        
        
        email = signup_data.email
        password = signup_data.password
        existing_user = await self.user_exists(email, session)
            
        if existing_user:
            return None
            
        try:
            signup_data_dict = signup_data.model_dump()
            signup_data_dict['password'] = generate_password_hash(signup_data_dict['password'])
            
            if email == Config.ADMIN_EMAIL and password == Config.ADMIN_PASSWORD:
                signup_data_dict['role'] = 'admin'
            
            new_user = User(
                **signup_data_dict
            )
            
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return UserModel.model_validate(new_user)
        
        except Exception as e:
            await session.rollback()
            raise e
            
            
    async def update_user(self, uid: uuid.UUID, user_data: dict, session: AsyncSession):
        existing_user = await self.get_user_abstract(uid, session)
        
            
        if not existing_user:
            return None
            
        try:
            allowed_fields = {'firstname', 'lastname', 'email', 'password', 'phone', 'role', 'verified', 'status', 'deleted_at', 'purge_at', 'received'}
                
            for k, v in user_data.items():
                if k in allowed_fields:
                    setattr(existing_user, k, v)
                    
            await session.commit()
            await session.refresh(existing_user)
                
            return existing_user
                
        except Exception as e:
            await session.rollback()
            raise e
        
    
    
    #function to update user details/creds
    async def update_credentials(self, uid: uuid.UUID, update_data: UserUpdateModel, session: AsyncSession):
        
        existing_user = await self.get_user_abstract(uid, session)
        
        if existing_user:
            try:
                update_data_dict = update_data.model_dump(exclude_unset=True)
                
                for k, v in update_data_dict.items():
                    setattr(existing_user, k, v)
                    
                await session.commit()
                await session.refresh(existing_user)
                
                return existing_user
                
            except Exception as e:
                await session.rollback()
                raise e
            
            
        return None
    
    
    #function to delete user
    async def purge_deleted_users(self, session: AsyncSession) -> bool:
        
        now = datetime.utcnow()
        staff = await session.execute(select(Staff).where(Staff.is_deleted == True, Staff.purge_at <= now))
        company = await session.execute(select(Company).where(Company.is_deleted == True, Company.purge_at <= now))
        user = await session.execute(select(User).where(User.status == "deleted", User.purge_at <= now))
        staff_to_purge = staff.scalars().all()
        company_to_purge = company.scalars().all()
        users_to_purge = user.scalars().all()
        
        try:
            if staff_to_purge:
                for staff in staff_to_purge:
                    await session.delete(staff)
                    
                await session.commit()
                
         
            if company_to_purge:
                for company in company_to_purge:
                    await session.delete(company)
                    
                await session.commit()
        
            if users_to_purge:
                for user in users_to_purge:
                    await session.delete(user)
                    
                await session.commit()
            return True

        except Exception as e:
            await session.rollback()
            raise e
    
    
    

    def get_device_info(self, request: Request):
        user_agent_str = request.headers.get("user-agent", "unknown")
        user_agent = parse(user_agent_str)
    
        device_info = {
            "is_mobile": user_agent.is_mobile,
            "is_tablet": user_agent.is_tablet,
            "is_pc": user_agent.is_pc,
            "os": user_agent.os.family,          # iOS, Android, Windows, etc.
            "os_version": user_agent.os.version_string,
            "device": user_agent.device.family,  # iPhone, iPad, Pixel, Galaxy S21, etc.
            "browser": user_agent.browser.family # Safari, Chrome, etc.
        }
    
        return device_info['device']
                
    
def verify_email_html(request: Request, otp: str, name: str) -> str:
    
    return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Verify Your Email</title>
        </head>
        <body style="margin:0; padding:0; background-color:#f5f7fa; font-family:Arial, Helvetica, sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa; padding:20px;">
            <tr>
              <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0"
                       style="max-width:600px; background:#ffffff; border-radius:8px; padding:30px;">
        
                  <!-- Header -->
                  <tr>
                    <td align="center" style="padding-bottom:20px;">
                      <h1 style="margin:0; color:#111827;">Welcome to Strexpei 🚀</h1>
                    </td>
                  </tr>
        
                  <!-- Body -->
                  <tr>
                    <td style="color:#374151; font-size:16px; line-height:1.6;">
                      <p>Hi {name},</p>
        
                      <p>
                        Use the code below to verify your
                        <strong>Strexpei</strong> account.
                      </p>
        
                      <p style="text-align:center; margin:30px 0;">
                        <p
                           style="
                             background-color:#2563eb;
                             color:#ffffff;
                             text-decoration:none;
                             padding:14px 28px;
                             border-radius:6px;
                             font-weight:bold;
                             display:inline-block;
                           ">
                          {otp}
                        </p>
                      </p>
        
                      <p>
                        This code will expire in <strong>5 minutes. Do not share it with anyone</strong>.
                        If you didn’t create a Strexpei account, you can safely ignore this email.
                      </p>
        
                      <p style="margin-top:30px;">
                        See you inside,<br />
                        <strong>— The Strexpei Team</strong>
                      </p>
                    </td>
                  </tr>
        
                  <!-- Footer -->
                  <tr>
                    <td align="center" style="padding-top:20px; font-size:12px; color:#9ca3af;">
                      © 2026 Strexpei. All rights reserved.
                    </td>
                  </tr>
        
                </table>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """
        
        
def account_verified_html(login_link: str) -> str:
    link= f"http://{Config.DOMAIN}/docs"
    return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Account Verified</title>
        </head>
        <body style="margin:0; padding:0; background-color:#f9fafb; font-family:Arial, Helvetica, sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0" style="padding:20px;">
            <tr>
              <td align="center">
                <table width="100%" cellpadding="0" cellspacing="0"
                       style="max-width:520px; background:#ffffff; border-radius:10px; padding:40px; text-align:center;">
        
                  <!-- Icon -->
                  <tr>
                    <td style="font-size:48px; padding-bottom:20px;">
                      ✅
                    </td>
                  </tr>
        
                  <!-- Title -->
                  <tr>
                    <td>
                      <h1 style="margin:0; color:#111827; font-size:26px;">
                        Email Verified Successfully
                      </h1>
                    </td>
                  </tr>
        
                  <!-- Message -->
                  <tr>
                    <td style="padding-top:15px; color:#374151; font-size:16px; line-height:1.6;">
                      <p style="margin:0;">
                        Your Strexpei account has been verified.<br />
                        You’re officially good to go.
                      </p>
                    </td>
                  </tr>
        
                  <!-- CTA -->
                  <tr>
                    <td style="padding-top:30px;">
                      <a href="{link}"
                         style="
                           background-color:#16a34a;
                           color:#ffffff;
                           text-decoration:none;
                           padding:14px 32px;
                           border-radius:8px;
                           font-weight:bold;
                           display:inline-block;
                           font-size:16px;
                         ">
                        Continue to Dashboard
                      </a>
                    </td>
                  </tr>
        
                  <!-- Footer -->
                  <tr>
                    <td style="padding-top:30px; font-size:13px; color:#9ca3af;">
                      Welcome to Strexpei 🚀
                    </td>
                  </tr>
        
                </table>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """
        
        
async def generate_otp():
    otp = str(secrets.randbelow(900000) + 100000)
    return otp


async def can_resend(user_id):
    cooldown_key = f"otp_resend_cooldown:{user_id}"
    resend_count_key = f"otp_resend_count:{user_id}"

    #check cooldown (30 sec between resends)
    if await redis_client.exists(cooldown_key):
        ttl = await redis_client.ttl(cooldown_key)
        return False, {"message":f"Please wait {ttl} seconds before resending", "seconds":ttl}
    
    #checks max resend attempts (e.g, max 3 per 10 mins)
    count = await redis_client.get(resend_count_key)
    if count and int(count) >= 3:
        return False, f"Max resend attempts reached. Try again in 10 minutes"
    
    return True, None

async def resend_otp(user_id, email):
    allowed, message = await can_resend(user_id)

    if not allowed:
        return {"success": False, "message": message}
    
    #Generate new OTP (invalidates old one)
    otp = await generate_otp()
    await save_password_reset_otp(user_email=email, otp=otp, expiry_seconds=300)

    #STore OTP with 5min expiry
    await redis_client.setex(f"otp:{user_id}", 300, otp)

    #set cooldown (30sec)
    await redis_client.setex(f"otp_resend_cooldown:{user_id}", 60, 1)

    #Increment resend counter (expires in 10 mins)
    await redis_client.incr(f"otp_resend_count:{user_id}")
    await redis_client.expire(f"otp_resend_count:{user_id}", 600)

    return otp

