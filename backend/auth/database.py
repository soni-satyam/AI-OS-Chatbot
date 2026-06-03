# backend/auth/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite file will be created at backend/auth.db
SQLALCHEMY_DATABASE_URL = "sqlite:///./auth.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for SQLite only
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency: use this in route functions to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db       # yield = FastAPI will inject this, then close after request
    finally:
        db.close()