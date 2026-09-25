"""
Core Data Models and Schemas.
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class User:
    id: str
    email: str
    role: str = "user"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
