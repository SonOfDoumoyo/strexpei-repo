from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime
from enum import Enum


class SignUpModel(BaseModel):
    firstname: str = Field(max_length=25)
    lastname: str = Field(max_length=25)
    email: EmailStr
    phone: str = Field(min_length=11, max_length=11, default="0xxxxxxxxxx")
    password: str = Field(min_length=6, max_length=15)
    
    model_config= ConfigDict(
        from_attributes=True
    )

class UserUpdateModel(BaseModel):
    firstname: str = Field(max_length=25, default=None)
    lastname: str = Field(max_length=25, default=None)
    email: EmailStr
    phone: str = Field(min_length=11, default=None)
    password: str = Field(min_length=6, max_length=15, default=None)
    

class UserModel(BaseModel):
    firstname: str
    lastname: str
    email: EmailStr
    phone: str
    verified: bool
    role: str
    updated_at: datetime
    created_at: datetime
    
    model_config= ConfigDict(
        from_attributes=True
    )
    

class LoginModel(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=15)
    
    
class PasswordResetModel(BaseModel):
    otp: str = Field(max_length=6, min_length=6)
    email: EmailStr
    password: str = Field(min_length=6, max_length=15, default=None)
    confirm_password: str = Field(min_length=6, max_length=15, default=None)
    
class StatusModel(str, Enum):
    active = 'active'
    suspended = 'suspended'
    banned = 'banned'
    pending = 'pending'
    deleted = "deleted"