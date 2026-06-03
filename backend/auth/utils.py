# backend/auth/utils.py
from fastapi import HTTPException, Header
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os

# bcrypt is the hashing algorithm — industry standard
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# CHANGE THIS in production! Store in .env file
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"              # HMAC-SHA256 — fast and secure for JWTs
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def hash_password(password: str) -> str:
    """Turn plain password → bcrypt hash. One-way: can't reverse it."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if plain password matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT token.
    
    JWT structure: header.payload.signature
    - header: algorithm info
    - payload: your data (user_id, expiry) — NOT encrypted, just signed
    - signature: header+payload signed with SECRET_KEY
    
    Anyone can READ the payload, but can't FAKE the signature without SECRET_KEY.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT. Returns None if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
    
# Reusable dependency to extract JWT from Authorization header
def get_token_from_header(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ")[1]