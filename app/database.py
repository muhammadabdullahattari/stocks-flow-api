from app.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from collections.abc import Generator

DATABASE_URL = settings.DATABASE_URL

engine = create_engine(DATABASE_URL,pool_pre_ping=True,pool_size=5,max_overflow=5,pool_timeout=10)

SessionLocal = sessionmaker( bind = engine , autoflush = False , autocommit = False)
Base = declarative_base()


def get_db()-> Generator :
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
        
