from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime
import uuid
from typing import List, Optional


class AllCompanyModel(BaseModel):
    cid: uuid.UUID
    manager_id: uuid.UUID 
    company_name: str
    position: str
    updated_at: datetime 
    created_at: datetime
    
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
    accountname: str
    accountnumber: str 
    bankname: str
    bankcode: str 
    pay_receipts: List[str]
    updated_at: datetime 
    created_at: datetime
    
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
    
    model_config= ConfigDict(
        from_attributes=True
    )
    

class ListUsersModel(BaseModel):
    users: List[AllUsersModel]