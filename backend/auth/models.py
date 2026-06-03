# backend/auth/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    
    # nullable because Google users won't have a password
    hashed_password = Column(String, nullable=True)
    
    # nullable because email/password users won't have this
    google_id = Column(String, unique=True, nullable=True)
    
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # auto-set on creation
    created_at = Column(DateTime(timezone=True), server_default=func.now())