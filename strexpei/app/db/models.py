from sqlmodel import Field, SQLModel, Relationship
from typing import Any, List, Optional
from sqlalchemy import String, Column, ForeignKey
import sqlalchemy.dialects.postgresql as pg
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from datetime import datetime
import uuid
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship as sa_relationship



class User(SQLModel, table=True):
    __tablename__='users'
    uid: uuid.UUID = Field(sa_column=Column(pg.UUID(as_uuid=True), nullable=False, primary_key=True), default_factory=uuid.uuid4)
    email: str = Field(sa_column=Column(String, unique=True, nullable=False))
    firstname: str = Field(sa_column=Column(String, nullable=False))
    lastname: str = Field(sa_column=Column(String, nullable=False))
    phone: str = Field(sa_column=Column(String, nullable=True))
    password: str = Field(sa_column=Column(String, nullable=False), exclude=True)
    verified: bool = Field(default=False)
    status: str = Field(sa_column=Column(pg.VARCHAR, nullable=False, server_default='pending'))
    role: str = Field(sa_column=Column(pg.VARCHAR, nullable=False, server_default='user'))
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    deleted_at: datetime | None = Field(default=None)
    purge_at: datetime | None = Field(default=None)
    companies: List["Company"] = Relationship(back_populates='manager', sa_relationship_kwargs = {'lazy':'selectin','cascade':'all, delete-orphan'})
    staffs: List["Staff"] = Relationship(back_populates='user', sa_relationship_kwargs = {'lazy':'selectin'})
    request: List["RequestJoin"] = Relationship(back_populates='creator', sa_relationship_kwargs = {'lazy':'selectin'})
    sent: List["Notification"] = Relationship( sa_relationship=sa_relationship("Notification", back_populates='sender', lazy='selectin', foreign_keys="[Notification.sender_id]"))
    received: List["Notification"] = Relationship( sa_relationship=sa_relationship("Notification", back_populates='receiver', lazy='selectin', foreign_keys="[Notification.receiver_id]"))
    
    def __repr__(self):
        return f'<User {self.email}>'


class Banned(SQLModel, table=True):
    __tablename__='banned'
    bid: uuid.UUID = Field(sa_column=Column(pg.UUID(as_uuid=True), nullable=False, primary_key=True), default_factory=uuid.uuid4)
    user_id: uuid.UUID = Field(default=None, foreign_key='users.uid')
    email: str | None = Field(default=None)
    reason: str | None  = Field(default=None)
    severity: int | None = Field(default=None)
    issued_by: uuid.UUID | None = Field(default=None)
    banned_at: datetime | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)
    is_active: str | None = Field(default=None)
    
    def __repr__(self):
        return f'<Banned {self.user_id}>'
    
    
class Company(SQLModel, table=True):
    __tablename__='companies'
    cid: uuid.UUID = Field(sa_column=Column(pg.UUID(as_uuid=True), nullable=False, primary_key=True), default_factory=uuid.uuid4)
    manager_id: uuid.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey("users.uid", ondelete="CASCADE"), nullable=False))
    company_name: str = Field(sa_column=Column(String, nullable=False))
    address: str = Field(sa_column=Column(String, nullable=False))
    totalPayout: str = Field(sa_column=Column(String), default="0")
    position: str = Field(sa_column=Column(String, nullable=False), default='manager')
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None)
    purge_at: datetime | None = Field(default=None)
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    manager: Optional[User] = Relationship(back_populates='companies')
    staffs: List["Staff"] = Relationship(back_populates='company', sa_relationship_kwargs = {'lazy':'selectin', 'cascade':'all, delete-orphan', 'passive_deletes':True})
    request: List["RequestJoin"] = Relationship(back_populates='company', sa_relationship_kwargs= {'lazy': 'selectin', 'cascade':'all, delete-orphan', 'passive_deletes':True})
    
    def __repr__(self):
        return f'<Company {self.company_name}>'
    

class Staff(SQLModel, table=True):
    __tablename__='staffs'
    sid: uuid.UUID = Field(sa_column=Column(pg.UUID(as_uuid=True), nullable=False, primary_key=True), default_factory=uuid.uuid4)
    company_id: uuid.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey("companies.cid", ondelete="CASCADE"), nullable=False))
    user_id: uuid.UUID = Field(nullable=False, foreign_key='users.uid')
    firstname: str = Field(sa_column=Column(String, nullable=False))
    lastname: str = Field(sa_column=Column(String, nullable=False))
    salary: str = Field(sa_column=Column(String, nullable=False), default='0.00')
    position: str = Field(sa_column=Column(String, nullable=False), default='staff')
    accountname: str | None = Field(sa_column=Column(String, nullable=True), default=None)
    accountnumber: str | None = Field(sa_column=Column(String, nullable=True), default=None)
    bankname: str | None = Field(sa_column=Column(String, nullable=True), default=None)
    bankcode: str | None = Field(sa_column=Column(String, nullable=True), default=None)
    recipient_code: str | None = Field(sa_column=Column(String, nullable=True, unique=True), default = None)
    sub_account: str | None = Field(sa_column=Column(String, nullable=True), default=None)
    valid_account: bool | None = Field(default=False)
    pay_receipts: List[str] = Field(sa_column=Column(ARRAY(String), nullable=False), default_factory=list)
    updated_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None)
    purge_at: datetime | None = Field(default=None)
    user: Optional[User] = Relationship(back_populates='staffs')
    company: Optional[Company] = Relationship(back_populates='staffs')
    
    def __repr__(self):
        return f'<Staff {self.accountname}>'
        
        
class Invite(SQLModel, table=True):
    __tablename__='invites'
    invite_id: uuid.UUID = Field(sa_column=Column(pg.UUID(as_uuid=True), nullable=False, primary_key=True), default_factory=uuid.uuid4)
    company_id: uuid.UUID = Field(pg.UUID(as_uuid=True), nullable=False, foreign_key='companies.cid', ondelete="CASCADE")
    email: str = Field(sa_column=Column(String, nullable=False))
    role: str = Field(sa_column=Column(String, nullable=False))
    token: str = Field(sa_column=Column(String, nullable=False))
    expires_at: datetime | None = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), default=None))
    used: bool = Field(default=False)
    used_at: datetime | None = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), default=None))
    revoked: bool = Field(default=False)
    revoked_at: datetime | None = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), default=None))
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    created_by: uuid.UUID = Field(default=None, foreign_key='users.uid')

class RequestJoin(SQLModel, table=True):
    __tablename__='requests'
    request_id: uuid.UUID = Field(sa_column=Column(pg.UUID(as_uuid=True), nullable=False, primary_key=True), default_factory=uuid.uuid4)
    company_id: uuid.UUID = Field(pg.UUID(as_uuid=True), nullable=False, foreign_key='companies.cid', ondelete="CASCADE")
    company_name: str = Field(sa_column=Column(String, nullable=False))
    position: str = Field(sa_column=Column(String, nullable=False))
    company_email: str = Field(sa_column=Column(String, nullable=False))
    status: str = Field(sa_column=Column(pg.VARCHAR, nullable=False, server_default="pending"))
    token: str = Field(sa_column=Column(String, nullable=False))
    expires_at: datetime | None = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), default=None))
    revoked: bool = Field(default=False)
    revoked_at: datetime | None = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), default=None))
    created_at: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    created_by: uuid.UUID = Field(default=None, foreign_key='users.uid')
    firstname: str = Field(sa_column=Column(String, nullable=True), default="null")
    lastname: str = Field(sa_column=Column(String, nullable=True), default="null")
    creator: Optional[User] = Relationship(back_populates='request')
    company: Optional[Company] = Relationship(back_populates='request')

class Notification(SQLModel, table=True):
    __tablename__='notifications'
    nid: uuid.UUID = Field(sa_column=Column(pg.UUID(as_uuid=True), nullable=False, primary_key=True), default_factory=uuid.uuid4)
    title: str = Field(sa_column=Column(String, nullable=False))
    message: str = Field(sa_column=Column(String, nullable=False))
    timestamp: datetime = Field(sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()))
    isRead: bool = Field(default=False)
    sender_id: uuid.UUID = Field(default=None, foreign_key='users.uid')
    receiver_id: uuid.UUID = Field(default=None, foreign_key='users.uid')
    sender: Optional[User] = Relationship( sa_relationship=sa_relationship("User", back_populates='sent', foreign_keys="[Notification.sender_id]"))
    receiver: Optional[User] = Relationship( sa_relationship=sa_relationship("User", back_populates='received', foreign_keys="[Notification.receiver_id]"))