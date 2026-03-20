from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from sqlalchemy.orm import selectinload
from ...config import Config
from ..auth.utils import generate_password_hash
from ..auth.auth_schema import (
    SignUpModel,
    LoginModel,
    UserModel,
    UserUpdateModel
)
from ..auth.service import AuthService
from ..company.service import CompanyService
from fastapi import Request
from user_agents import parse
from ...config import Config
import uuid
from .staff_schema import StaffModel, GetAllStaffModel, UpdateAccountDetModel, JoinRequestStaffModel
from ..db.models import (
    User,
    Company,
    Staff,
    RequestJoin,
    Notification
)
from datetime import datetime, timedelta, timezone
from ...errors import(
    UserNotFound
)
import secrets


auth_service = AuthService()
company_service = CompanyService()

EXPIRY = datetime.now(timezone.utc) + timedelta(hours=72)

class StaffService:
    
        
    async def get_staff_by_uid(self, user_id: uuid.UUID, session: AsyncSession):
        
        statement = select(Staff).where(Staff.user_id == user_id)
        result = await session.execute(statement)
        staff = result.scalars().first()
        return staff
    
    async def get_staff_by_uid_and_cid(self, user_id: uuid.UUID, cid: uuid.UUID, session: AsyncSession):
        
        statement = select(Staff).where(Staff.user_id == user_id, Staff.company_id == cid )
        result = await session.execute(statement)
        staff = result.scalars().first()
        return staff
    
    async def get_all_user_companies(self, uid: UUID, session: AsyncSession):
        stmt = await session.execute(select(Staff).where(Staff.user_id == uid))
        result = stmt.scalars().all()

        return result
    

    async def get_all_staffs(self, session: AsyncSession):

        statement = await session.execute(select(Staff).options(selectinload(Staff.user), selectinload(Staff.company).selectinload(Company.manager)))
        all_staffs = statement.scalars().all()


        return all_staffs


    async def get_manager_by_company(self, cid: uuid.UUID, session: AsyncSession):

        statement = select(Company).options(selectinload(Company.manager)).where(Company.cid == cid)
        result = await session.execute(statement)
        valid_company = result.scalars().first()

        return valid_company.manager.email, valid_company
    
    async def get_staff_by_sid(self, sid: uuid.UUID, session: AsyncSession):
        statement = select(Staff).where(Staff.sid == sid)
        result = await session.execute(statement)
        staff = result.scalars().first()
        return staff
    
    async def get_staffs_by_cid(self, cid: uuid.UUID, session:AsyncSession):

        stmt = select(Staff).where(Staff.company_id == cid)

        response = await session.execute(stmt)
        result = response.scalars().all()

        return result
    
    async def delete_staff(self, cid: uuid.UUID, sid: uuid.UUID, session: AsyncSession):

        try:

            stmt = select(Staff).where(Staff.company_id == cid, Staff.sid == sid)
            staff = (await session.execute(stmt)).scalars().first()

            await session.delete(staff)
            await session.commit()

            return {'message': 'staff erased successfully'}

        except Exception as e:

            await session.rollback()
            print(e)


    async def update_company_staff(self, staff: Staff, staff_update_dict: dict, session: AsyncSession):

        try:

            allowed_overwrites = ['accountname', 'accountnumber', 'bankname', 'bankcode', 'salary', 'recipient_code', 'sub_account']

            for k,v in staff_update_dict.items():
                if k in allowed_overwrites:
                    setattr(staff, k, v)

            await session.commit()
            await session.refresh(staff)

            return staff


        except Exception as e:
            await session.rollback()
            raise e
        
    
    async def new_request_details(self,token: str, request_details: JoinRequestStaffModel, user_id: uuid.UUID, session: AsyncSession):
        try:

            valid_user = await auth_service.get_user_abstract(uid=user_id, session=session)
            valid_company = await company_service.get_company_by_cid(cid=request_details.company_id, session=session)
            request_data = request_details.model_dump()
            request_data['token'] = token
            request_data['expires_at'] = EXPIRY

            new_req_table = RequestJoin(
                **request_data
            )

            new_req_table.created_by = valid_user.uid
            new_req_table.created_at = datetime.now(timezone.utc)
            new_req_table.creator = valid_user
            new_req_table.company = valid_company
            
            session.add(new_req_table)
            await session.commit()
            await session.refresh(new_req_table)

            company_admin = await auth_service.get_user_abstract(uid=valid_company.manager_id, session=session)

            notify = {
                "title":"New Staff Join Request",
                "message":f"{valid_user.firstname} - I'm a staff member of this company and would like to be added as a {new_req_table.position}",
                "sender_id":valid_user.uid,
                "receiver_id": company_admin.uid,
            }

            new_notification = Notification(
                **notify
            )

            new_notification.sender = valid_user
            new_notification.receiver = company_admin

            #await auth_service.update_user(uid=company_admin.uid, user_data={'received':new_notification}, session=session)

            session.add(new_notification)
            await session.commit()
            await session.refresh(new_notification)

            return True

        except Exception as e:
            await session.rollback()
            raise e
        

    async def get_user_request(self, token: str, session: AsyncSession):

        statement = select(RequestJoin).where(RequestJoin.token == token)
        response = await session.execute(statement)

        result = response.scalars().first()

        return result


    async def update_request_detail(self, token: str, update_details:dict, session: AsyncSession):
        try:

            request = await self.get_user_request(token=token, session=session)

            if not request:
                return False
            
            if request.expires_at >= datetime.now(timezone.utc):
                
                update_request = {
                    'revoked':True,
                    'revoked_at':datetime.now(timezone.utc)
                }
                for k,v in update_request.items():
                    setattr(request, k, v)
                
                await session.commit()
                await session.refresh(request)
                return None
            
            allowed_updates = ['status']

            for k, v in update_details.items():
                if k in allowed_updates:
                    setattr(request, k, v)

            await session.commit()
            await session.refresh(request)

            return True

        except Exception as e:
            await session.rollback()
            raise e
        
    async def add_staff_to_company(self, user_details: UserModel, cid: uuid.UUID, role: str, session: AsyncSession):
        try:
            
            user_data = user_details.model_dump()
            staff_data = {
                'company_id':cid,
                'user_id':user_details.uid,
                'firstname':user_details.firstname,
                'lastname':user_details.lastname,
                'position':role
            }

            existing_staff = await self.get_staff_by_uid(user_id=staff_data['user_id'], session=session)
            if existing_staff:
                return None

            user = await auth_service.get_user_by_uid(staff_data['user_id'], session)
            email, company = await self.get_manager_by_company(cid=cid, session=session)

            new_staff = Staff(
                **staff_data
            )

            new_staff.user = user
            new_staff.company = company

            session.add(new_staff)
            await session.commit()
            await session.refresh(new_staff)

            return StaffModel.model_validate(new_staff)

        except Exception as e:
            await session.rollback()
            raise e



    async def request_email(self, details: dict, token: str):
        
        staff_name = details['staff_name']
        company_name = details['company_name']
        staff_role = details['staff_role']
        accept_url = f"http://{Config.DOMAIN}/api/v1.0/staffs/accept_request/{token}"
        decline_url = f"http://{Config.DOMAIN}/api/v1.0/staff/reject_request/{token}"

        return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Request to Join {staff_name}</title>
            </head>
            <body style="margin:0; padding:0; font-family: Arial, sans-serif; background-color:#f4f6f8;">
                
                <table width="100%" cellpadding="0" cellspacing="0" style="padding: 40px 0;">
                    <tr>
                        <td align="center">

                            <table width="500" cellpadding="0" cellspacing="0" style="background:#ffffff; padding:30px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                                
                                <tr>
                                    <td style="font-size:18px; font-weight:bold; color:#333333; padding-bottom:15px;">
                                        Join Request via Strexpei
                                    </td>
                                </tr>

                                <tr>
                                    <td style="font-size:14px; color:#555555; line-height:1.6;">
                                        Dear {company_name} Admin,
                                        <br><br>
                                        {staff_name}, currently serving as {staff_role} in your organization, has submitted a request to join <strong>{company_name}</strong> on <strong>Strexpei</strong>.
                                        <br><br>
                                        Strexpei is a bulk one-time payment platform designed to help managers efficiently process staff payments.
                                        <br><br>
                                        Kindly review and take appropriate action below.
                                        <br><br>
                                    </td>
                                </tr>

                                <!-- Buttons -->
                                <tr>
                                    <td align="center" style="padding: 20px 0;">

                                        <!-- Accept Button -->
                                        <table cellpadding="0" cellspacing="0" style="display:inline-block; margin-right:10px;">
                                            <tr>
                                                <td align="center" bgcolor="#2563EB" style="border-radius:6px;">
                                                    <a href="{accept_url}" 
                                                    style="display:inline-block; padding:12px 24px; font-size:14px; color:#ffffff; text-decoration:none; font-weight:bold;">
                                                        Accept Request
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>

                                        <!-- Decline Button -->
                                        <table cellpadding="0" cellspacing="0" style="display:inline-block;">
                                            <tr>
                                                <td align="center" bgcolor="#DC2626" style="border-radius:6px;">
                                                    <a href="{decline_url}" 
                                                    style="display:inline-block; padding:12px 24px; font-size:14px; color:#ffffff; text-decoration:none; font-weight:bold;">
                                                        Decline
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>

                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-top:20px; font-size:12px; color:#888888;">
                                        This request was generated through Strexpei.
                                    </td>
                                </tr>

                            </table>

                        </td>
                    </tr>
                </table>

            </body>
            </html>


        """