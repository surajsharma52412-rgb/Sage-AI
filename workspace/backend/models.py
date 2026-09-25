from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

@dataclass
class User:
    id: int
    email: str
    role: str = "user"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

@dataclass
class Application:
    id: int
    user_id: int
    first_name: str
    last_name: str
    date_of_birth: str
    application_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"

@dataclass
class Status:
    id: int
    application_id: int
    status: str
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
