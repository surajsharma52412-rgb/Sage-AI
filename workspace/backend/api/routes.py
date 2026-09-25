from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from .models import UserLogin
from ..database.db import get_db
from ..database.models import User
from sqlalchemy.orm import Session
from passlib.context import CryptContext

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.post("/api/auth/login")
async def login(form_OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    # Generate JWT token here
    return {"access_token": "token", "token_type": "bearer"}
