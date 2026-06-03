# backend/auth/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional

# --- Request shapes (what client sends) ---

class SignupRequest(BaseModel):
    email: EmailStr        # Pydantic validates it's a real email format
    password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    token: str             # The ID token from Google OAuth

# --- Response shapes (what server returns) ---

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    
    class Config:
        from_attributes = True  # Lets Pydantic read SQLAlchemy objects

TokenResponse.model_rebuild()  # needed because of forward reference above