from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime
import uuid
from typing import List, Optional
from ..auth.auth_schema import UserModel


class UserEditModel(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    email: EmailStr | None = None
    phone: str | None = Field(min_length=11, max_length=11, default=None)

    