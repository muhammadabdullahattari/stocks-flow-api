from app.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from collections.abc import Generator

DATABASE_URL = settings.DATABASE_URL

# Sized for 100 VUs on 2 vCPUs (t3.small)
engine = create_engine(
    DATABASE_URL,
    pool_size=15,            # Keep 15 connections warm per worker
    max_overflow=15,         # Allow bursting up to 30 connections per worker
    pool_timeout=25.0,       # Wait up to 25s before timing out under burst
    pool_recycle=1800,       # Recycle connections every 30 mins to avoid stale drops
    pool_pre_ping=True       # Verify connection health before checkout
)

# Slow query logger (>150ms) to identify database-side bottlenecks during load testing
import time
import logging
from sqlalchemy import event

sql_logger = logging.getLogger("sqlalchemy.slow_query")

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info["query_start_time"] = time.perf_counter()

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start_time = conn.info.get("query_start_time")
    if start_time:
        duration_ms = (time.perf_counter() - start_time) * 1000
        if duration_ms > 150:
            sql_logger.warning("SLOW QUERY (%.2f ms): %s", duration_ms, statement[:200])

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

        
        
