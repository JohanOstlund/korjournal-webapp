import os, time, hmac, hashlib, base64, json
from typing import Optional, Tuple
import bcrypt

# Fail if SECRET_KEY not set in production
SECRET = os.getenv("SECRET_KEY")
if not SECRET:
    if os.getenv("ENV", "development") == "production":
        raise RuntimeError("SECRET_KEY must be set in production!")
    SECRET = "dev-secret-change-me"

EXP_MIN = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES","1440"))  # 24 hours default

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _unb64(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def sign_jwt(payload: dict, exp_min: Optional[int]=None) -> str:
    header = {"alg":"HS256","typ":"JWT"}
    payload = {**payload, "exp": int(time.time()) + 60*(exp_min or EXP_MIN)}
    h = _b64(json.dumps(header).encode())
    p = _b64(json.dumps(payload).encode())
    msg = f"{h}.{p}".encode()
    sig = hmac.new(SECRET.encode(), msg, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64(sig)}"

def verify_jwt(token: str) -> Tuple[bool, Optional[dict]]:
    try:
        h, p, s = token.split(".")
        msg = f"{h}.{p}".encode()
        sig = _unb64(s)
        good = hmac.compare_digest(hmac.new(SECRET.encode(), msg, hashlib.sha256).digest(), sig)
        if not good: return False, None
        payload = json.loads(_unb64(p))
        if int(time.time()) >= int(payload.get("exp",0)): return False, None
        return True, payload
    except Exception:
        return False, None

# ===== Password Hashing with bcrypt =====
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False
