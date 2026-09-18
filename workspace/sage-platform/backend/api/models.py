from pydantic import BaseModel
from typing import Optional

class UserLogin(BaseModel):
    email: str
    password: str

class AgentTask(BaseModel):
    id: str
    goal: str
    progress: float
