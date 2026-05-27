from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime
import uuid
from typing import List, Optional
from ..auth.auth_schema import UserModel


class AddCompanyModel(BaseModel):
    company_name: str = Field(..., min_length=1)
    address: str = Field(...,min_length=1)
    position: str = Field(default="Manager", min_length=1)
    
    model_config = ConfigDict(from_attributes=True)
    

class ManagerModel(BaseModel):
    firstname: str
    lastname: str
    email: EmailStr
    phone: str
    role: str

class StaffAbstractModel(BaseModel):
    sid: uuid.UUID
    firstname: str 
    lastname: str
    salary: str
    position: str
    accountname: str | None 
    accountnumber: str | None 
    bankname: str | None 
    bankcode: str | None
    valid_account: bool | None
    updated_at: datetime 
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CompanyModel(BaseModel):
    cid: uuid.UUID 
    manager_id: uuid.UUID
    company_name: str
    address: str
    position: str
    updated_at: datetime 
    is_deleted: bool 
    deleted_at: Optional[datetime] = None
    purge_at: Optional[datetime] = None 
    created_at: datetime
    manager: Optional[UserModel] 
    staffs: List[StaffAbstractModel]
    
    model_config = ConfigDict(from_attributes=True)
    
    
class ResponseCompanyModel(BaseModel):
    company: List[CompanyModel]

    model_config = ConfigDict(from_attributes=True)
    

class CreateInviteModel(BaseModel):
    
    email: EmailStr 
    role: str

class UpdateCompanyModel(BaseModel):
    position: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
    
    
class InviteModel(BaseModel):
    
    invite_id: uuid.UUID 
    company_id: uuid.UUID
    email: EmailStr
    role: str 
    token: str 
    expires_at: datetime
    used: bool
    used_at: Optional[datetime] = None
    revoked: bool
    revoked_at: Optional[datetime] = None
    created_at: datetime
    created_by: uuid.UUID
    
    model_config = ConfigDict(from_attributes=True)
