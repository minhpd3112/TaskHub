from pydantic import BaseModel, Field, field_validator
from pydantic.networks import EmailStr

from app.schemas.user import UserResponse


class RegisterRequest(BaseModel):
    """Payload for user registration."""

    email: EmailStr = Field(..., max_length=255, description="Unique email address")
    full_name: str = Field(..., min_length=1, max_length=100, description="Full name")
    password: str = Field(..., min_length=8, max_length=128, description="Account password")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Full name cannot be empty or whitespace only.")
        return stripped

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(not c.isalnum() for c in v):
            raise ValueError("Password must contain at least one special character.")
        return v


class LoginRequest(BaseModel):
    """Payload for user login."""

    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Payload for refreshing access token."""

    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Response payload for successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
    user: UserResponse


class NewAccessTokenResponse(BaseModel):
    """Response payload for successful token refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
