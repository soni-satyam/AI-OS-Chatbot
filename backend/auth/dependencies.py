# backend/auth/dependencies.py
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .utils import decode_token

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Use this as a dependency on any protected route:
    
        @router.get("/protected")
        def my_route(user: User = Depends(get_current_user)):
            return {"message": f"Hello {user.email}"}
    
    FastAPI will automatically call this before your route function.
    If the token is missing/invalid, it raises 401 and your route never runs.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user