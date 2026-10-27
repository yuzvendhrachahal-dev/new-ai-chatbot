from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
import jwt
from fastapi import HTTPException, status, Header, Query
from app.core.config import settings

# Initialize Argon2id PasswordHasher
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16
)

def hash_password(password: str) -> str:
    """
    Hashes a password using Argon2id.
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    return _hasher.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against an Argon2id hash.
    """
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, Exception):
        return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a signed JWT access token for an agent.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    Raises HTTPException(401) on failure.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent session token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_agent(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Dependency to protect agent endpoints.
    Accepts Bearer token in Authorization header or 'token' query param (for EventSource SSE).
    """
    auth_token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            auth_token = parts[1]
        elif len(parts) == 1:
            auth_token = parts[0]
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent authentication required. Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth_token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing agent identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate agent exists and is active in database
    from app.core.database import get_agents_collection
    agents_col = get_agents_collection()
    agent = agents_col.find_one({"username": username})

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent account not found or has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not agent.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account has been deactivated.",
        )

    # Return safe metadata (NEVER expose password_hash)
    return {
        "username": agent["username"],
        "display_name": agent.get("display_name", username),
        "role": agent.get("role", "advisor"),
        "is_active": agent.get("is_active", True),
    }
