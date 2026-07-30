import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import TokenExpiredError, TokenInvalidError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using bcrypt."""
    return str(pwd_context.hash(plain_password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a bcrypt hash."""
    return bool(pwd_context.verify(plain_password, hashed_password))


def create_access_token(subject: str, role: str = "MEMBER", jti: str | None = None) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "jti": jti or uuid.uuid4().hex,
        "type": "access",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, jti: str | None = None) -> str:
    """Create a signed JWT refresh token."""
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": jti or uuid.uuid4().hex,
        "type": "refresh",
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired.") from e
    except jwt.PyJWTError as e:
        raise TokenInvalidError("Invalid token.") from e
