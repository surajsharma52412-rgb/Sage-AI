from pydantic import BaseModel
from datetime import datetime

class UserBase(BaseModel):
    email: str
    role: str = "user"

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class ApplicationBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: datetime
    status: str = "pending"

class ApplicationCreate(ApplicationBase):
    pass

class Application(ApplicationBase):
    id: int
    user_id: int
    application_date: datetime

    class Config:
        orm_mode = True

class StatusBase(BaseModel):
    status: str

class Status(StatusBase):
    id: int
    application_id: int
    updated_at: datetime

    class Config:
        orm_mode = True
