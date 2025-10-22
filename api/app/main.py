"""
Körjournal API v2 - Improved version with:
- Bcrypt password hashing
- Rate limiting
- Proper logging
- Lifespan management
- Configurable SSL verification
- Better security
"""
import os, json, asyncio, logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List

import httpx
from fastapi import FastAPI, Depends, Query, Response, HTTPException, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .db import SessionLocal, engine, get_db
from .models import (
    Base, Trip, Vehicle, Place, OdometerSnapshot, TripTemplate, Setting,
    User, HASetting, APIToken
)
from .pdf import render_journal_pdf
from .security import sign_jwt, verify_jwt, hash_password, verify_password
from .security import verify_token as verify_pat, hash_token as hash_pat, gen_plain_api_token, is_expired

# ===== Logging Setup =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Configuration =====
ENV_HA_FORCE_DOMAIN = os.getenv("HA_FORCE_DOMAIN", "kia_uvo")
ENV_HA_FORCE_SERVICE = os.getenv("HA_FORCE_SERVICE", "force_update")
ENV_HA_FORCE_DATA = os.getenv("HA_FORCE_DATA")
HA_VERIFY_SSL = os.getenv("HA_VERIFY_SSL", "true").lower() == "true"

COOKIE_NAME = "session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")

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

# ===== Helper Functions =====
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> User:
    """
    Ordning:
    1) Authorization: Bearer <token> där <token> först testas som JWT; om ogiltig testas som PAT
    2) Cookie-baserad JWT (fallback)
    """
    # 1) Authorization header
    if creds and creds.scheme.lower() == "bearer":
        token = creds.credentials
        ok, payload = verify_jwt(token)
        if ok:
            username = payload.get("sub")
            u = db.query(User).filter(User.username == username).first()
            if not u:
                raise HTTPException(401, "User not found")
            return u
        # prova som PAT
        # Vi lagrar endast hash i DB -> vi måste iterera eller hitta via indexerat prefix.
        # För att undvika fullskan: lagra t.ex. de första 10 tecknen som 'lookup_key' om du vill.
        # En enkel approach: hämta alla aktiva tokens för snabb POC (ok för få användare).
        pats = db.query(APIToken).filter(APIToken.revoked == False).all()
        for pat in pats:
            if verify_pat(token, pat.token_hash):
                if is_expired(pat.expires_at):
                    raise HTTPException(401, "API token expired")
                u = db.query(User).filter(User.id == pat.user_id).first()
                if not u:
                    raise HTTPException(401, "User not found")
                # scopes kan du validera här om du vill
                return u
        raise HTTPException(401, "Invalid Authorization token")

    # 2) Cookie
    cookie_token = request.cookies.get(COOKIE_NAME)
    if not cookie_token:
        raise HTTPException(401, "Not authenticated")
    ok, payload = verify_jwt(cookie_token)
    if not ok:
        raise HTTPException(401, "Invalid session")
    username = payload.get("sub")
    u = db.query(User).filter(User.username == username).first()
    if not u:
        raise HTTPException(401, "User not found")
    return u


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Dependency to verify admin privileges."""
    if not user.is_admin:
        raise HTTPException(403, "Admin privileges required")
    return user

def get_ha_config(db: Session, user: User):
    """Get per-user HA settings with ENV fallback."""
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()

    base = h.base_url if h and h.base_url else os.getenv("HA_BASE_URL")
    token = h.token if h and h.token else os.getenv("HA_TOKEN")
    entity = h.odometer_entity if h and h.odometer_entity else os.getenv("HA_ODOMETER_ENTITY")

    domain = h.force_domain if h and h.force_domain else ENV_HA_FORCE_DOMAIN
    service = h.force_service if h and h.force_service else ENV_HA_FORCE_SERVICE

    data_json = None
    raw = h.force_data_json if h and h.force_data_json else ENV_HA_FORCE_DATA
    if raw:
        try:
            data_json = json.loads(raw)
        except Exception:
            data_json = None
    return base, token, entity, domain, service, data_json

def ensure_no_overlap(db: Session, user_id: int, vehicle_id: int, start: datetime, end: Optional[datetime], exclude_id: Optional[int] = None):
    """Ensure no overlapping trips for the same user/vehicle."""
    q = db.query(Trip).filter(Trip.user_id == user_id, Trip.vehicle_id == vehicle_id)
    if exclude_id:
        q = q.filter(Trip.id != exclude_id)
    if end is None:
        q = q.filter(Trip.ended_at.is_(None) | and_(Trip.started_at <= start, Trip.ended_at > start))
    else:
        q = q.filter(
            or_(
                and_(Trip.started_at <= start, Trip.ended_at > start),
                and_(Trip.started_at < end, Trip.ended_at >= end),
                and_(Trip.started_at >= start, Trip.ended_at <= end),
                and_(Trip.ended_at.is_(None), Trip.started_at <= end),
            )
        )
    if db.query(q.exists()).scalar():
        raise HTTPException(status_code=400, detail="Overlapping/active trip for the same vehicle")

def odo_delta_distance(start_odo: Optional[float], end_odo: Optional[float]) -> Optional[float]:
    """Calculate distance from odometer readings."""
    if start_odo is None or end_odo is None:
        return None
    d = end_odo - start_odo
    if d < 0:
        return None
    return round(d, 1)
    # ===== Protected Router =====
protected = APIRouter(dependencies=[Depends(get_current_user)])
# ===== Bearer Token =======

class CreateTokenIn(BaseModel):
    name: str
    scope: Optional[str] = "full"
    expires_days: Optional[int] = None  # None = aldrig (rekommenderas ej)

class TokenOut(BaseModel):
    id: int
    name: str
    scope: str
    created_at: datetime
    expires_at: Optional[datetime]
    revoked: bool

    class Config:
        from_attributes = True


@protected.post("/auth/tokens", response_model=TokenOut)
def create_token(payload: CreateTokenIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import timedelta, datetime
    plain = gen_plain_api_token()
    hashed = hash_pat(plain)
    expires_at = datetime.utcnow() + timedelta(days=payload.expires_days) if payload.expires_days else None
    t = APIToken(
        user_id=user.id,
        name=payload.name,
        token_hash=hashed,
        scope=payload.scope or "full",
        expires_at=expires_at,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    # Viktigt: returnera plaintext-token bara en gång (i header) så den inte skrivs i loggar
    return JSONResponse(
        content=TokenOut.model_validate(t).model_dump(),
        headers={"X-Plain-API-Token": plain}
    )

@protected.get("/auth/tokens", response_model=List[TokenOut])
def list_tokens(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tokens = db.query(APIToken).filter(APIToken.user_id == user.id).order_by(APIToken.created_at.desc()).all()
    return [TokenOut.model_validate(t) for t in tokens]

@protected.delete("/auth/tokens/{token_id}")
def revoke_token(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(APIToken).filter(APIToken.id == token_id, APIToken.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Token not found")
    t.revoked = True
    db.commit()
    return {"status": "revoked"}



# ===== Pydantic Models =====
class LoginIn(BaseModel):
    username: str
    password: str

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

class TripIn(BaseModel):
    vehicle_reg: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    start_odometer_km: Optional[float] = None
    end_odometer_km: Optional[float] = None
    distance_km: Optional[float] = None
    purpose: Optional[str] = None
    business: bool = True
    driver_name: Optional[str] = None
    start_address: Optional[str] = None
    end_address: Optional[str] = None

class TripOut(BaseModel):
    id: int
    vehicle_reg: str
    started_at: datetime
    ended_at: Optional[datetime]
    distance_km: Optional[float]
    start_odometer_km: Optional[float]
    end_odometer_km: Optional[float]
    purpose: Optional[str]
    business: bool
    driver_name: Optional[str] = None
    start_address: Optional[str] = None
    end_address: Optional[str] = None

    class Config:
        from_attributes = True

class StartTripIn(BaseModel):
    vehicle_reg: str
    started_at: Optional[datetime] = None
    start_odometer_km: Optional[float] = None
    purpose: Optional[str] = None
    business: bool = True
    driver_name: Optional[str] = None
    start_address: Optional[str] = None
    end_address: Optional[str] = None

class FinishTripIn(BaseModel):
    vehicle_reg: Optional[str] = None
    trip_id: Optional[int] = None
    ended_at: Optional[datetime] = None
    end_odometer_km: Optional[float] = None
    distance_km: Optional[float] = None
    purpose: Optional[str] = None
    business: Optional[bool] = None
    driver_name: Optional[str] = None
    end_address: Optional[str] = None

class TemplateIn(BaseModel):
    name: str
    default_purpose: Optional[str] = None
    business: bool = True
    default_distance_km: Optional[float] = None
    default_vehicle_reg: Optional[str] = None
    default_driver_name: Optional[str] = None
    default_start_address: Optional[str] = None
    default_end_address: Optional[str] = None

class TemplateOut(BaseModel):
    id: int
    name: str
    default_purpose: Optional[str]
    business: bool
    default_distance_km: Optional[float]
    default_vehicle_reg: Optional[str]
    default_driver_name: Optional[str]
    default_start_address: Optional[str]
    default_end_address: Optional[str]

    class Config:
        from_attributes = True

class HAPollIn(BaseModel):
    vehicle_reg: str
    entity_id: Optional[str] = None
    at: Optional[datetime] = None

class SettingsOut(BaseModel):
    ha_base_url: Optional[str] = None
    ha_odometer_entity: Optional[str] = None
    ha_token_set: bool = False
    force_domain: Optional[str] = None
    force_service: Optional[str] = None
    force_data_json: Optional[dict] = None

class SettingsIn(BaseModel):
    ha_base_url: Optional[str] = None
    ha_odometer_entity: Optional[str] = None
    ha_token: Optional[str] = None
    force_domain: Optional[str] = None
    force_service: Optional[str] = None
    force_data_json: Optional[dict] = None

class UserOut(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

class CreateUserIn(BaseModel):
    username: str
    password: str

# ===== Open Routes (No Auth) =====
@app.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    """Login endpoint with rate limiting."""
    logger.info(f"Login attempt for user: {payload.username}")
    u = db.query(User).filter(User.username == payload.username).first()

    if not u or not verify_password(payload.password, u.password_hash):
        logger.warning(f"Failed login attempt for user: {payload.username}")
        raise HTTPException(401, "Fel användarnamn eller lösenord")

    token = sign_jwt({"sub": u.username})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/"
    )
    logger.info(f"Successful login for user: {payload.username}")
    return {"ok": True, "user": {"username": u.username}}
# valfritt
class LoginOut(BaseModel):
    ok: bool
    user: dict
    access_token: str  # JWT

@app.post("/auth/token", response_model=LoginOut)
@limiter.limit("5/minute")
async def login_token(request: Request, payload: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == payload.username).first()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(401, "Fel användarnamn eller lösenord")
    token = sign_jwt({"sub": u.username})
    return {"ok": True, "user": {"username": u.username}, "access_token": token}
@app.post("/auth/logout")
def logout(response: Response):
    """Logout endpoint."""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}

@app.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return {"username": user.username}

@app.post("/auth/change-password")
def change_password(
    payload: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password endpoint."""
    if not verify_password(payload.current_password, user.password_hash):
        logger.warning(f"Failed password change attempt for user: {user.username}")
        raise HTTPException(400, "Fel nuvarande lösenord")

    if not payload.new_password or len(payload.new_password) < 8:
        raise HTTPException(400, "Nytt lösenord måste vara minst 8 tecken")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    logger.info(f"Password changed for user: {user.username}")
    return {"ok": True}

# ===== Admin User Management =====
@app.post("/admin/users", response_model=UserOut)
def create_user(
    payload: CreateUserIn,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin endpoint to create a new user."""
    if not payload.username or not payload.password:
        raise HTTPException(400, "Användarnamn och lösenord krävs")

    if len(payload.password) < 8:
        raise HTTPException(400, "Lösenord måste vara minst 8 tecken")

    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(400, "Användaren finns redan")

    new_user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"Admin {admin.username} created new user: {new_user.username}")
    return UserOut(id=new_user.id, username=new_user.username)

@app.get("/admin/users", response_model=List[UserOut])
def list_users(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin endpoint to list all users."""
    users = db.query(User).order_by(User.username).all()
    return [UserOut(id=u.id, username=u.username) for u in users]

@app.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin endpoint to delete a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Användare hittades inte")

    if user.is_admin:
        raise HTTPException(400, "Kan inte ta bort admin-användare")

    if user.id == admin.id:
        raise HTTPException(400, "Kan inte ta bort sig själv")

    db.delete(user)
    db.commit()
    logger.info(f"Admin {admin.username} deleted user: {user.username}")
    return {"status": "deleted"}

@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse({"status": "db_error", "error": str(e)}, status_code=500)



# ----- Settings (per user) -----
@protected.get("/settings", response_model=SettingsOut)
def get_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user-specific HA settings."""
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()
    return SettingsOut(
        ha_base_url=h.base_url if h else None,
        ha_odometer_entity=h.odometer_entity if h else None,
        ha_token_set=bool(h and h.token),
        force_domain=h.force_domain if h else None,
        force_service=h.force_service if h else None,
        force_data_json=json.loads(h.force_data_json) if h and h.force_data_json else None,
    )

@protected.put("/settings", response_model=SettingsOut)
def put_settings(payload: SettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update user-specific HA settings."""
    h = db.query(HASetting).filter(HASetting.user_id == user.id).first()
    if not h:
        h = HASetting(user_id=user.id)
        db.add(h)
    if payload.ha_base_url is not None: h.base_url = payload.ha_base_url or None
    if payload.ha_odometer_entity is not None: h.odometer_entity = payload.ha_odometer_entity or None
    if payload.force_domain is not None: h.force_domain = payload.force_domain or None
    if payload.force_service is not None: h.force_service = payload.force_service or None
    if payload.force_data_json is not None: h.force_data_json = json.dumps(payload.force_data_json) if payload.force_data_json else None
    if payload.ha_token is not None and payload.ha_token.strip():
        h.token = payload.ha_token.strip()
    h.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(h)
    logger.info(f"Settings updated for user: {user.username}")
    return get_settings(user, db)

# ----- HA integration (per user) -----
@protected.post("/integrations/home-assistant/poll")
async def ha_poll(payload: HAPollIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Poll Home Assistant for odometer value."""
    base, token, entity, *_ = get_ha_config(db, user)
    if not (base and token and (entity or payload.entity_id)):
        raise HTTPException(400, "HA Base/Token/Entity not configured")
    eid = payload.entity_id or entity
    url = f"{base}/api/states/{eid}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=10, verify=HA_VERIFY_SSL) as client:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            logger.error(f"HA poll failed: {r.status_code} - {r.text}")
            raise HTTPException(r.status_code, f"HA states fetch failed: {r.text}")
        data = r.json()
        try:
            value_km = float(data.get("state"))
        except Exception:
            raise HTTPException(500, f"Could not parse odometer state: {data.get('state')}")
        at = datetime.utcnow()
    logger.info(f"HA poll successful for user {user.username}: {value_km} km")
    return {"status": "ok", "value_km": value_km, "entity": eid, "at": at.isoformat()}

@protected.post("/integrations/home-assistant/force-update-and-poll")
async def ha_force_update_and_poll(
    payload: HAPollIn,
    wait_seconds: int = 15,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Force Home Assistant update then poll for odometer value."""
    base, token, entity, domain, service, data_json = get_ha_config(db, user)
    if not (base and token):
        raise HTTPException(400, "HA Base/Token not configured")
    svc_url = f"{base}/api/services/{domain}/{service}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20, verify=HA_VERIFY_SSL) as client:
        s = await client.post(svc_url, headers=headers, json=data_json or {})
        if s.status_code not in (200, 201):
            logger.error(f"HA force update failed: {s.status_code} - {s.text}")
            raise HTTPException(s.status_code, f"HA service call failed: {s.text}")

    logger.info(f"HA force update triggered for user {user.username}, waiting {wait_seconds}s...")
    await asyncio.sleep(wait_seconds)
    return await ha_poll(payload, user, db)

# ----- Trips -----
@protected.post("/trips/start", response_model=TripOut)
def start_trip(payload: StartTripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Start a new trip."""
    veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh)
        db.flush()

    existing = db.query(Trip).filter(Trip.user_id == user.id, Trip.vehicle_id == veh.id, Trip.ended_at.is_(None)).first()
    if existing:
        raise HTTPException(400, "Det finns redan en pågående resa för detta fordon")

    started_at = payload.started_at or datetime.utcnow()
    ensure_no_overlap(db, user.id, veh.id, started_at, None)

    trip = Trip(
        user_id=user.id,
        vehicle_id=veh.id,
        started_at=started_at,
        ended_at=None,
        start_odometer_km=payload.start_odometer_km,
        purpose=payload.purpose,
        business=payload.business,
        driver_name=payload.driver_name,
        start_address=payload.start_address,
        end_address=payload.end_address,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    logger.info(f"Trip started: ID={trip.id}, User={user.username}, Vehicle={veh.reg_no}")

    return TripOut(
        id=trip.id, vehicle_reg=veh.reg_no, started_at=trip.started_at, ended_at=None,
        distance_km=None, start_odometer_km=trip.start_odometer_km, end_odometer_km=None,
        purpose=trip.purpose, business=trip.business,
        driver_name=trip.driver_name, start_address=trip.start_address, end_address=trip.end_address
    )

@protected.post("/trips/finish", response_model=TripOut)
def finish_trip(payload: FinishTripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Finish an active trip."""
    t: Optional[Trip] = None
    if payload.trip_id:
        t = db.query(Trip).filter(Trip.id == payload.trip_id, Trip.user_id == user.id).first()
        if not t:
            raise HTTPException(404, "Trip not found")
        if t.ended_at is not None:
            raise HTTPException(400, "Trip already finished")
    else:
        if not payload.vehicle_reg:
            raise HTTPException(400, "vehicle_reg eller trip_id krävs")
        veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
        if not veh:
            raise HTTPException(404, "Vehicle not found")
        t = db.query(Trip).filter(Trip.user_id == user.id, Trip.vehicle_id == veh.id, Trip.ended_at.is_(None)).order_by(Trip.started_at.desc()).first()
        if not t:
            raise HTTPException(404, "Ingen pågående resa att avsluta")

    ended_at = payload.ended_at or datetime.utcnow()
    ensure_no_overlap(db, user.id, t.vehicle_id, t.started_at, ended_at, exclude_id=t.id)

    t.ended_at = ended_at
    if payload.end_odometer_km is not None:
        t.end_odometer_km = payload.end_odometer_km
    if payload.purpose is not None:
        t.purpose = payload.purpose
    if payload.business is not None:
        t.business = payload.business
    if payload.driver_name is not None and not t.driver_name:
        t.driver_name = payload.driver_name
    if payload.end_address is not None:
        t.end_address = payload.end_address

    km = payload.distance_km
    if km is None:
        km = odo_delta_distance(t.start_odometer_km, t.end_odometer_km)
    t.distance_km = km if km is not None else t.distance_km
    t.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(t)
    veh = db.query(Vehicle).get(t.vehicle_id)
    logger.info(f"Trip finished: ID={t.id}, User={user.username}, Distance={t.distance_km}km")

    return TripOut(
        id=t.id, vehicle_reg=veh.reg_no, started_at=t.started_at, ended_at=t.ended_at,
        distance_km=t.distance_km, start_odometer_km=t.start_odometer_km, end_odometer_km=t.end_odometer_km,
        purpose=t.purpose, business=t.business,
        driver_name=t.driver_name, start_address=t.start_address, end_address=t.end_address
    )

@protected.post("/trips", response_model=TripOut)
def create_trip(payload: TripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a complete trip."""
    veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh)
        db.flush()

    if payload.ended_at is not None and payload.ended_at <= payload.started_at:
        raise HTTPException(400, "ended_at must be after started_at")

    ensure_no_overlap(db, user.id, veh.id, payload.started_at, payload.ended_at)

    dist_km = payload.distance_km
    if dist_km is None and (payload.ended_at is not None):
        dist_km = odo_delta_distance(payload.start_odometer_km, payload.end_odometer_km)

    trip = Trip(
        user_id=user.id,
        vehicle_id=veh.id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        start_odometer_km=payload.start_odometer_km,
        end_odometer_km=payload.end_odometer_km,
        distance_km=dist_km,
        purpose=payload.purpose,
        business=payload.business,
        driver_name=payload.driver_name,
        start_address=payload.start_address,
        end_address=payload.end_address,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    logger.info(f"Trip created: ID={trip.id}, User={user.username}")

    return TripOut(
        id=trip.id, vehicle_reg=veh.reg_no,
        started_at=trip.started_at, ended_at=trip.ended_at,
        distance_km=trip.distance_km,
        start_odometer_km=trip.start_odometer_km,
        end_odometer_km=trip.end_odometer_km,
        purpose=trip.purpose, business=trip.business,
        driver_name=trip.driver_name, start_address=trip.start_address, end_address=trip.end_address
    )

@protected.put("/trips/{trip_id}", response_model=TripOut)
def update_trip(trip_id: int, payload: TripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update an existing trip."""
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")

    veh = db.query(Vehicle).filter(Vehicle.reg_no == payload.vehicle_reg).first()
    if not veh:
        veh = Vehicle(reg_no=payload.vehicle_reg)
        db.add(veh)
        db.flush()

    if payload.ended_at is not None and payload.ended_at <= payload.started_at:
        raise HTTPException(400, "ended_at must be after started_at")

    ensure_no_overlap(db, user.id, veh.id, payload.started_at, payload.ended_at, exclude_id=trip.id)

    dist_km = payload.distance_km
    if dist_km is None and (payload.ended_at is not None):
        dist_km = odo_delta_distance(payload.start_odometer_km, payload.end_odometer_km)

    trip.user_id = user.id
    trip.vehicle_id = veh.id
    trip.started_at = payload.started_at
    trip.ended_at = payload.ended_at
    trip.start_odometer_km = payload.start_odometer_km
    trip.end_odometer_km = payload.end_odometer_km
    trip.distance_km = dist_km if dist_km is not None else trip.distance_km
    trip.purpose = payload.purpose
    trip.business = payload.business
    trip.driver_name = payload.driver_name
    trip.start_address = payload.start_address
    trip.end_address = payload.end_address
    trip.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(trip)
    logger.info(f"Trip updated: ID={trip.id}, User={user.username}")

    return TripOut(
        id=trip.id,
        vehicle_reg=veh.reg_no,
        started_at=trip.started_at,
        ended_at=trip.ended_at,
        distance_km=trip.distance_km,
        start_odometer_km=trip.start_odometer_km,
        end_odometer_km=trip.end_odometer_km,
        purpose=trip.purpose,
        business=trip.business,
        driver_name=trip.driver_name, start_address=trip.start_address, end_address=trip.end_address
    )

@protected.delete("/trips/{trip_id}")
def delete_trip(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a trip."""
    t = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Trip not found")
    db.delete(t)
    db.commit()
    logger.info(f"Trip deleted: ID={trip_id}, User={user.username}")
    return {"status": "deleted"}

@protected.get("/trips", response_model=None)
def list_trips(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    include_active: bool = Query(True),
):
    """List all trips for current user."""
    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.user_id == user.id)
    if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
    if not include_active:
        q = q.filter(Trip.ended_at.isnot(None))

    res = []
    for t, v in q.order_by(Trip.started_at.desc()).limit(500).all():
        res.append({
            "id": t.id,
            "vehicle_reg": v.reg_no,
            "started_at": t.started_at,
            "ended_at": t.ended_at,
            "distance_km": t.distance_km,
            "start_odometer_km": t.start_odometer_km,
            "end_odometer_km": t.end_odometer_km,
            "purpose": t.purpose,
            "business": t.business,
            "driver_name": t.driver_name,
            "start_address": t.start_address,
            "end_address": t.end_address,
        })

    payload = jsonable_encoder(res)
    response = JSONResponse(content=payload)
    response.headers["Cache-Control"] = "no-store"
    return response

# ----- Templates (per user) -----
@protected.get("/templates", response_model=List[TemplateOut])
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all templates for current user."""
    tpls = db.query(TripTemplate).filter(TripTemplate.user_id == user.id).order_by(TripTemplate.name.asc()).all()
    out = []
    for t in tpls:
        out.append(TemplateOut(
            id=t.id,
            name=t.name,
            default_purpose=t.default_purpose,
            business=t.business,
            default_distance_km=t.default_distance_km,
            default_vehicle_reg=t.default_vehicle_reg,
            default_driver_name=t.default_driver_name,
            default_start_address=t.default_start_address,
            default_end_address=t.default_end_address,
        ))
    return out

@protected.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new template."""
    exists = db.query(TripTemplate).filter(TripTemplate.user_id == user.id, TripTemplate.name == payload.name).first()
    if exists:
        raise HTTPException(400, "En mall med detta namn finns redan")
    t = TripTemplate(
        user_id=user.id,
        name=payload.name,
        default_purpose=payload.default_purpose,
        business=payload.business,
        default_distance_km=payload.default_distance_km,
        default_vehicle_reg=payload.default_vehicle_reg,
        default_driver_name=payload.default_driver_name,
        default_start_address=payload.default_start_address,
        default_end_address=payload.default_end_address,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    logger.info(f"Template created: {t.name}, User={user.username}")
    return TemplateOut(
        id=t.id, name=t.name, default_purpose=t.default_purpose,
        business=t.business, default_distance_km=t.default_distance_km,
        default_vehicle_reg=t.default_vehicle_reg,
        default_driver_name=t.default_driver_name,
        default_start_address=t.default_start_address,
        default_end_address=t.default_end_address
    )

@protected.put("/templates/{tpl_id}", response_model=TemplateOut)
def update_template(tpl_id: int, payload: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update an existing template."""
    t = db.query(TripTemplate).filter(TripTemplate.id == tpl_id, TripTemplate.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Template not found")

    if payload.name and payload.name != t.name:
        exists = db.query(TripTemplate).filter(TripTemplate.user_id == user.id, TripTemplate.name == payload.name).first()
        if exists:
            raise HTTPException(400, "En mall med detta namn finns redan")

    t.name = payload.name
    t.default_purpose = payload.default_purpose
    t.business = payload.business
    t.default_distance_km = payload.default_distance_km
    t.default_vehicle_reg = payload.default_vehicle_reg
    t.default_driver_name = payload.default_driver_name
    t.default_start_address = payload.default_start_address
    t.default_end_address = payload.default_end_address
    t.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(t)
    logger.info(f"Template updated: {t.name}, User={user.username}")
    return TemplateOut(
        id=t.id,
        name=t.name,
        default_purpose=t.default_purpose,
        business=t.business,
        default_distance_km=t.default_distance_km,
        default_vehicle_reg=t.default_vehicle_reg,
        default_driver_name=t.default_driver_name,
        default_start_address=t.default_start_address,
        default_end_address=t.default_end_address,
    )

@protected.delete("/templates/{tpl_id}")
def delete_template(tpl_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a template."""
    t = db.query(TripTemplate).filter(TripTemplate.id == tpl_id, TripTemplate.user_id == user.id).first()
    if not t:
        raise HTTPException(404, "Template not found")
    db.delete(t)
    db.commit()
    logger.info(f"Template deleted: ID={tpl_id}, User={user.username}")
    return {"status": "deleted"}

# ----- Exports (per user) -----
@protected.get("/exports/journal.csv")
def export_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    """Export trips as CSV."""
    import csv
    from io import StringIO

    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.user_id == user.id)
    if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
    if year:
        q = q.filter(Trip.started_at >= datetime(year, 1, 1), Trip.started_at < datetime(year + 1, 1, 1))
    q = q.filter(Trip.ended_at.isnot(None))

    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "År", "Regnr", "Datum", "Startadress", "Slutadress",
        "Start mätarställning", "Slut mätarställning", "Antal km", "Ärende/Syfte", "Förare", "Tjänst/Privat"
    ])

    for t, v in q.order_by(Trip.started_at.asc()).all():
        datum = t.started_at.strftime('%Y-%m-%d') if t.started_at else ""
        writer.writerow([
            t.started_at.year if t.started_at else "",
            v.reg_no, datum,
            t.start_address or "",
            t.end_address or "",
            t.start_odometer_km or "", t.end_odometer_km or "",
            t.distance_km or "",
            t.purpose or "",
            t.driver_name or "",
            "Tjänst" if t.business else "Privat",
        ])

    csv_bytes = output.getvalue().encode('utf-8-sig')
    logger.info(f"CSV export for user: {user.username}")
    return Response(content=csv_bytes, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=korjournal.csv"})

@protected.get("/exports/journal.pdf")
def export_pdf_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    """Export trips as PDF."""
    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.user_id == user.id)
    if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
    if year:
        q = q.filter(Trip.started_at >= datetime(year, 1, 1), Trip.started_at < datetime(year + 1, 1, 1))
    q = q.filter(Trip.ended_at.isnot(None))

    rows = []
    for t, v in q.order_by(Trip.started_at.asc()).all():
        rows.append({
            "datum": t.started_at.strftime('%Y-%m-%d') if t.started_at else "",
            "start_odo": t.start_odometer_km or "",
            "end_odo": t.end_odometer_km or "",
            "km": t.distance_km or "",
            "start_adress": t.start_address or "",
            "slut_adress": t.end_address or "",
            "syfte": t.purpose or "",
            "tjanst": t.business,
        })

    pdf_bytes = render_journal_pdf(rows)
    logger.info(f"PDF export for user: {user.username}")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=korjournal.pdf"})

# Register protected routes
app.include_router(protected)
