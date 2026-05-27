from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from ...config import Config
from ..auth.utils import generate_password_hash, create_access_token, create_url_safe_token
from ..auth.service import AuthService
from ..auth.auth_schema import (
    SignUpModel,
    LoginModel,
    UserModel,
    UserUpdateModel
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from fastapi import Request
from user_agents import parse
from ...config import Config
import uuid
from ..db.models import (
    User,
    Company,
    Staff,
    Invite
)
from ..staffs.staff_schema import DisplayToManagerModel
import secrets
import string
from datetime import datetime, timedelta, timezone
from ...errors import(
    UserNotFound
)
from .company_schema import AddCompanyModel, CompanyModel, ResponseCompanyModel, CreateInviteModel, InviteModel, UpdateCompanyModel
import secrets


auth_service = AuthService()
EXPIRY = datetime.now(timezone.utc) + timedelta(hours=48)

class CompanyService:
    
    async def generate_invite_code(self, chars, length=14):
        """Creates a random referral code but at the moment not necessary"""
        characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ23456789"+chars
        return ''.join(secrets.choice(characters) for _ in range(length))

    
    async def get_company_by_cid(self, cid: uuid.UUID, session: AsyncSession):
        
        statement = select(Company).where(Company.cid == cid)
        result = await session.execute(statement)
        company = result.scalars().first()
    
        return company
        
        
    async def get_company_by_uid(self, uid: uuid.UUID, session: AsyncSession):
        statement = (select(Company).where(Company.manager_id == uid).options(selectinload(Company.manager)))
        result = await session.execute(statement)
        companies = result.scalars().all()
        return companies
    

    #async def get_company_email(self, cid: uuid.UUID, session: AsyncSession):
        #statement = select(Company).where(Company.manager.email == )
    
    
    async def total_Payout(self, cid: uuid.UUID, session: AsyncSession):
        existing_company = await self.get_company_by_cid(cid, session)

        if not existing_company:
            return None
        
        statement = select(Staff).where(Staff.company_id == cid)
        result = await session.execute(statement)
        all_staffs = result.scalars().all()

        total_salary = 0

        for staff in all_staffs:
            total_salary += staff.salary

        salary_dict = {"totalPayout":str(total_salary)}

        for k, v in salary_dict.items():
            setattr(existing_company, k, v)

        await session.commit()
        await session.refresh(existing_company)

        return True

    
    async def update_company(self, cid: uuid.UUID, user_data: UpdateCompanyModel, session: AsyncSession):
        existing_company = await self.get_company_by_cid(cid, session)
        
            
        if not existing_company:
            return None
        
        user_data_dict = user_data.model_dump(exclude_none=True, exclude_unset=True)
        try:
            allowed_fields = {'is_deleted', 'deleted_at', 'purge_at', 'positon', 'company_name', 'address'}
                
            for k, v in user_data_dict.items():
                if k in allowed_fields:
                    setattr(existing_company, k, v)
                    
            await session.commit()
            await session.refresh(existing_company)
                
            return existing_company
                
        except Exception as e:
            await session.rollback()
            raise e
        
    
    async def adding_company(self,manager_id: uuid.UUID, company_data: AddCompanyModel, session:AsyncSession):
        try:
            result = await session.execute(select(User).where(User.uid == manager_id))
            manager = result.scalars().first()
            
            company_data_dict = company_data.model_dump()
            new_company = Company(
                **company_data_dict
            )
            new_company.position = 'Manager'
            new_company.manager_id = manager_id
            new_company.manager = manager
            
            session.add(new_company)
            await session.commit()
            await session.refresh(new_company)
            valid_response = CompanyModel.model_validate(new_company)
            return valid_response.model_dump()
            
        
        except Exception as e:
            await session.rollback()
            raise e
            
    
    async def get_all_added_companies(self, session: AsyncSession):
        result = await session.execute(select(Company))
        company = result.scalars().all()
        return company

    
    async def get_a_company_staffs(self, manager_id: uuid.UUID, session:AsyncSession):
        stmt = await session.execute(select(Staff).join(Staff.company).where(Company.manager_id == manager_id))
        result = stmt.scalars().all()

        return result
        
    
    async def invite_users(self, cid: uuid.UUID, invite_info: CreateInviteModel, session: AsyncSession):
        """creates and adds the invite to database"""
        try:
            invite_info_dict = invite_info.model_dump()
            invite_info_dict['expires_at'] = EXPIRY
            company = await self.get_company_by_cid(cid=cid, session=session)
            staff_email = invite_info.email

            staff_detail = await auth_service.get_user_by_email(staff_email, session)
            

            url_token = create_url_safe_token(
                data = {
                        'email': invite_info.email,
                        'position': invite_info.role,
                        'company_id': str(company.cid),
                        'user_id':str(staff_detail.uid)
                }
            )

            
            invite_info_dict['token'] = url_token
            new_invite = Invite(
                **invite_info_dict
            )
            
            new_invite.company_id = company.cid
            new_invite.created_by = company.manager_id
            new_invite.created_at = datetime.now(timezone.utc)
            company_name = company.company_name
            
            session.add(new_invite)
            await session.commit()
            await session.refresh(new_invite)
            valid_invite_response = InviteModel.model_validate(new_invite)
            return {
                    'invite_response':valid_invite_response.model_dump(),
                    'url_token':url_token,
                    'company_name':company_name
                }

    
        except Exception as e:
            await session.rollback()
            raise e
        
            
    async def get_invite_with_token(self, token: str, session:AsyncSession):
        
        try:
            invite_result = await session.execute(select(Invite).where(Invite.token == token))
            
            invite_data = invite_result.scalars().first()
            now = datetime.now(timezone.utc)
            expiry_date = invite_data.expires_at
            
            if expiry_date <= now:
                
                update_invite = {
                    'revoked':True,
                    'revoked_at':datetime.now(timezone.utc)
                }
                for k,v in update_invite.items():
                    setattr(invite_data, k, v)
                
                await session.commit()
                await session.refresh(invite_data)
                return None
            
            update_invite = {
                'used_at': datetime.now(timezone.utc)
            }
            for k,v in update_invite.items():
                    setattr(invite_data, k, v)
                    
            await session.commit()
            await session.refresh(invite_data)
            
            return True
                
                    
        except Exception as e:
            await session.rollback()
            raise e
            
            
    async def update_invite(self, invite_id: uuid.UUID, update_data: dict, session: AsyncSession):
        try:
            pass
            
        except Exception as e:
            await session.rollback()
            raise e
        

    async def erase_company(self, cid: uuid.UUID, session: AsyncSession):
        try:
            #deleting the company data
            company = await self.get_company_by_cid(cid, session)
            if not company:
                return None
            
            await session.delete(company)
            await session.commit()
            return {'message':'succcessfully erased'}
            

        except Exception as e:
            await session.rollback()
            raise e
            
            
    async def invite_email_html(self, invite_link: str, company_name: str) -> str:
        
        
        #link to accept invite
        accept_link = f"http://{Config.DOMAIN}/api/v1.0/company/valid_invite/{invite_link}"
        
        
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
                          <h1 style="margin:0; color:#111827;">You've been invited to join {company_name}</h1>
                        </td>
                      </tr>
            
                      <!-- Body -->
                      <tr>
                        <td style="color:#374151; font-size:16px; line-height:1.6;">
                          <p>Hi,</p>
            
                          <p>
                            You've been invited to join <strong> {company_name} </strong> on Strexpei
                          </p>
                          <p>
                          Click the button below to accept the invitation and get access to the organization
                          </p>
            
                          <p style="text-align:center; margin:30px 0;">
                            <a href="{accept_link}"
                               style="
                                 background-color:#2563eb;
                                 color:#ffffff;
                                 text-decoration:none;
                                 padding:14px 28px;
                                 border-radius:6px;
                                 font-weight:bold;
                                 display:inline-block;
                               ">
                              Accept Invite
                            </a>
                          </p>
                          
                          
            
                          <p>
                            This invitation will expire in <strong>48 hours</strong>.
                            If you weren't expecting this, you can safely ignore this email.
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