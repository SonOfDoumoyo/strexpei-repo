from pydantic import BaseModel, Field, ConfigDict, EmailStr
from ..company.company_schema import CompanyModel
from ..staffs.staff_schema import StaffAbstractModel, RequestStaffModel, AbstractRequestStaffModel
from datetime import datetime
import uuid
from typing import List, Optional
from ..auth.auth_schema import NotificationModel


class AllCompanyModel(BaseModel):
    cid: uuid.UUID
    manager_id: uuid.UUID 
    company_name: str
    position: str
    address: str
    updated_at: datetime 
    created_at: datetime
    staffs: List[StaffAbstractModel]
    request: List[AbstractRequestStaffModel]
    
    model_config= ConfigDict(
        from_attributes=True
    )
    

class AllStaffsModel(BaseModel):
    
    sid: uuid.UUID 
    company_id: uuid.UUID
    user_id: uuid.UUID 
    firstname: str 
    lastname: str
    salary: str 
    position: str
    accountname: str | None = None
    accountnumber: str | None = None
    bankname: str | None = None
    bankcode: str | None = None
    pay_receipts: List[str]
    updated_at: datetime 
    created_at: datetime
    company: Optional[CompanyModel]
    
    model_config= ConfigDict(
        from_attributes=True
    )
    
    
class AllUsersModel(BaseModel):
    uid: uuid.UUID
    email: str
    firstname: str
    lastname: str
    phone: str
    password: str 
    verified: bool 
    role: str
    status: str
    updated_at: datetime 
    created_at: datetime 
    deleted_at: datetime | None
    purge_at: datetime | None
    companies: List[AllCompanyModel]
    staffs: List[AllStaffsModel]
    request: List[RequestStaffModel]
    sent: List[NotificationModel]
    received: List[NotificationModel]
    
    model_config= ConfigDict(
        from_attributes=True
    )
    

class ListUsersModel(BaseModel):
    users: List[AllUsersModel]