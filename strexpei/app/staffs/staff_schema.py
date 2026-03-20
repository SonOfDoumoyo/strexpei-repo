from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime
import uuid
from typing import List, Optional
from ..auth.auth_schema import UserModel
from ..company.company_schema import CompanyModel



class AddStaffDataModel(BaseModel):
    firstname: str 
    lastname: str 
    accountname: str
    accountnumber: str 
    bankname: str
    
    model_config = ConfigDict(from_attributes=True)


class JoinRequestStaffModel(BaseModel):
    company_name: str
    company_id: uuid.UUID
    position: str
    company_email: str

    model_config = ConfigDict(from_attributes=True)


class RequestStaffModel(BaseModel):
    request_id: uuid.UUID 
    company_id: uuid.UUID 
    company_name: str 
    position: str 
    company_email: str
    status: str
    token: str 
    expires_at: datetime
    revoked: bool
    revoked_at: datetime | None = None
    created_at: datetime 
    created_by: uuid.UUID
    creator: Optional[UserModel]
    company: Optional[CompanyModel]

    model_config = ConfigDict(from_attributes=True)

class AbstractRequestStaffModel(BaseModel):
    request_id: uuid.UUID 
    company_id: uuid.UUID 
    company_name: str 
    position: str 
    company_email: str
    status: str
    token: str 
    expires_at: datetime
    revoked: bool
    revoked_at: datetime | None = None
    created_at: datetime 
    created_by: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

class StaffAbstractModel(BaseModel):
    sid: uuid.UUID
    firstname: str 
    lastname: str
    salary: str
    position: str
    accountname: str | None = None
    accountnumber: str | None = None
    bankname: str | None = None
    bankcode: str | None = None
    valid_account: bool | None = None
    updated_at: datetime 
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DisplayToManagerModel(BaseModel):
    staffs: List[StaffAbstractModel]

    model_config = ConfigDict(from_attributes=True)


class UpdateAccountDetModel(BaseModel):
    accountname: str | None = None
    accountnumber: str | None = None
    bankname: str | None = None
    bankcode: str | None = None


class SalaryUpdateModel(BaseModel):
    salary: str | None = None

class StaffModel(BaseModel):
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
    valid_account: bool | None  = None
    pay_receipts: List[str] 
    updated_at: datetime 
    created_at: datetime
    is_deleted: bool 
    deleted_at: datetime | None = None
    purge_at: datetime | None = None
    user: Optional[UserModel]
    company: Optional[CompanyModel]

    model_config = ConfigDict(from_attributes=True)

class GetAllStaffModel(BaseModel):
    staffs: List[StaffModel]
