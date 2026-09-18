import jwt
from datetime import datetime, timedelta

SECRET_KEY = "sage_secret_key_change_in_prod"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
