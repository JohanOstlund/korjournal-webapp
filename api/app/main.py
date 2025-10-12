"""
Körjournal API v2 - Refactored version with modular structure
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .db import SessionLocal, engine, get_db
from .models import Base, User
from .security import hash_password
from .routes import auth, admin, trips, settings, ha_integration, exports, templates

# ===== Logging Setup =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Startup/Shutdown =====
def ensure_admin(db: Session):
    """Ensure admin user exists."""
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")

    if not username or not password:
        logger.warning("ADMIN_USERNAME or ADMIN_PASSWORD not set. Skipping admin creation.")
        return

    if len(password) < 8:
        logger.error("ADMIN_PASSWORD must be at least 8 characters!")
        raise ValueError("ADMIN_PASSWORD too short")

    u = db.query(User).filter(User.username == username).first()
    if not u:
        logger.info(f"Creating admin user: {username}")
        u = User(username=username, password_hash=hash_password(password), is_admin=True)
        db.add(u)
        db.commit()
        logger.info("Admin user created successfully")
    else:
        if not u.is_admin:
            logger.info(f"Upgrading user '{username}' to admin")
            u.is_admin = True
            db.commit()
        logger.info(f"Admin user '{username}' already exists")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("Starting up Körjournal API...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_admin(db)
    finally:
        db.close()
    logger.info("Startup complete")
    yield
    # Shutdown
    logger.info("Shutting down...")

# ===== FastAPI App =====
app = FastAPI(
    title="Körjournal API",
    description="API för körjournal med autentisering och per-user data",
    version="2.0.0",
    lifespan=lifespan
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Health Check =====
@app.get("/health")
def health():
    """Health check endpoint."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "db_error", "error": str(e)}, status_code=500)
    finally:
        db.close()

# ===== Include Routers =====
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(trips.router)
app.include_router(settings.router)
app.include_router(ha_integration.router)
app.include_router(exports.router)
app.include_router(templates.router)
