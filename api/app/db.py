import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

# Sätt via env, t.ex.:
# mysql+pymysql://USER:PASS@NAS-IP:3306/korjournal?charset=utf8mb4
DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback till SQLite (lokal) om env saknas
if not DATABASE_URL:
    os.makedirs("/app/data", exist_ok=True)
    DATABASE_URL = "sqlite:////app/data/app.db"

is_mysql = DATABASE_URL.startswith("mysql+")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_pre_ping=True,
    pool_size=10 if is_mysql else 5,
    max_overflow=10 if is_mysql else 5,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()