from sqlalchemy.orm import Session
from .models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_data(db: Session):
    hashed_password = pwd_context.hash("password123")
    admin_user = User(email="admin@example.com", password_hash=hashed_password, role="admin")
    db.add(admin_user)
    db.commit()

if __name__ == "__main__":
    from .db import SessionLocal
    db = SessionLocal()
    seed_data(db)
    db.close()
