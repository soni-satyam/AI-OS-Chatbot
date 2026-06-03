# backend/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os

from .database import get_db
from .models import User
from .schemas import SignupRequest, LoginRequest, GoogleAuthRequest, TokenResponse, UserResponse
from .utils import hash_password, verify_password, create_access_token, get_token_from_header

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


@router.post("/signup", response_model=TokenResponse)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    """
    SIGNUP FLOW:
    1. Check if email already exists
    2. Hash the password (NEVER store plain text)
    3. Save user to DB
    4. Create JWT and return it
    """
    # Step 1: Duplicate check
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Step 2 & 3: Hash password + save
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        name=data.name
    )
    db.add(user)
    db.commit()
    db.refresh(user)  # gets the auto-generated id back
    
    # Step 4: Issue JWT — "sub" (subject) = user identifier
    token = create_access_token({"sub": str(user.id), "email": user.email})
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    LOGIN FLOW:
    1. Find user by email
    2. Verify password against hash
    3. Return JWT
    
    WHY same error for wrong email AND wrong password?
    Security — don't tell attackers which one is wrong.
    """
    user = db.query(User).filter(User.email == data.email).first()
    
    # Deliberate: same error message whether email doesn't exist OR password wrong
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    token = create_access_token({"sub": str(user.id), "email": user.email})
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/google", response_model=TokenResponse)
def google_auth(data: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    GOOGLE AUTH FLOW:
    1. Frontend gets a Google ID token (after user clicks "Sign in with Google")
    2. We send that token to Google to verify it's real
    3. Google returns user info (email, name, google_id)
    4. We upsert (create or find) the user in our DB
    5. Return our own JWT
    
    WHY verify with Google? Anyone could send a fake token.
    Google's verify call checks the signature on their end.
    """
    try:
        # This call hits Google's servers to verify the token
        idinfo = id_token.verify_oauth2_token(
            data.token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
    
    google_id = idinfo["sub"]   # unique Google user ID
    email = idinfo["email"]
    name = idinfo.get("name")
    
    # Find existing user by google_id OR email (handles linking accounts)
    user = db.query(User).filter(
        (User.google_id == google_id) | (User.email == email)
    ).first()
    
    if not user:
        # First time Google login — create account automatically
        user = User(email=email, google_id=google_id, name=name)
        db.add(user)
    else:
        # Update google_id if they previously signed up with email
        if not user.google_id:
            user.google_id = google_id
    
    db.commit()
    db.refresh(user)
    
    token = create_access_token({"sub": str(user.id), "email": user.email})
    
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(db: Session = Depends(get_db), token: str = Depends(get_token_from_header)):
    """Protected route — returns current user info. Good for testing auth works."""
    from .utils import decode_token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


