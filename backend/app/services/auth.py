from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    TokenExpiredError,
    TokenInvalidError,
    UnauthorizedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginRequest,
    NewAccessTokenResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse


class AuthService:
    """Service handling authentication business logic."""

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self.db = db
        self.redis = redis
        self.user_repo = UserRepository(db)

    async def register(self, dto: RegisterRequest) -> UserResponse:
        """Register a new user account with default MEMBER role."""
        if await self.user_repo.is_email_taken(dto.email):
            raise ConflictError("Email already registered.", code="EMAIL_ALREADY_EXISTS")

        hashed_pw = hash_password(dto.password)
        user = await self.user_repo.create(
            email=dto.email,
            full_name=dto.full_name,
            hashed_password=hashed_pw,
            role=UserRole.MEMBER,
            is_active=True,
        )

        return UserResponse.model_validate(user)

    async def login(self, dto: LoginRequest) -> TokenResponse:
        """Authenticate user by email and password, issuing access and refresh tokens."""
        user = await self.user_repo.get_by_email(dto.email)
        if not user or not verify_password(dto.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password.", code="INVALID_CREDENTIALS")

        if not user.is_active:
            raise UnauthorizedError("User account is inactive.", code="ACCOUNT_INACTIVE")

        access_token = create_access_token(subject=str(user.id), role=user.role.value)
        refresh_token = create_refresh_token(subject=str(user.id))

        user_response = UserResponse.model_validate(user)
        expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in_seconds,
            user=user_response,
        )

    async def refresh(self, dto: RefreshTokenRequest) -> NewAccessTokenResponse:
        """Issue a new access token using a valid refresh token."""
        try:
            payload = decode_token(dto.refresh_token)
        except (TokenExpiredError, TokenInvalidError) as e:
            raise UnauthorizedError(
                "Invalid or expired refresh token.", code="REFRESH_TOKEN_INVALID"
            ) from e

        if payload.get("type") != "refresh":
            raise UnauthorizedError(
                "Invalid token type. Refresh token required.", code="REFRESH_TOKEN_INVALID"
            )

        jti = payload.get("jti")
        if jti:
            is_blacklisted = await self.redis.get(f"token:blacklist:{jti}")
            if is_blacklisted:
                raise UnauthorizedError(
                    "Refresh token has been revoked.", code="REFRESH_TOKEN_INVALID"
                )

        sub = payload.get("sub")
        if not sub:
            raise UnauthorizedError(
                "Invalid refresh token payload.", code="REFRESH_TOKEN_INVALID"
            )

        try:
            user_id = UUID(sub)
        except ValueError as e:
            raise UnauthorizedError(
                "Invalid user ID in refresh token.", code="REFRESH_TOKEN_INVALID"
            ) from e

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User is invalid or inactive.", code="REFRESH_TOKEN_INVALID")

        new_access_token = create_access_token(subject=str(user.id), role=user.role.value)
        expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return NewAccessTokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=expires_in_seconds,
        )

    async def logout(
        self,
        current_user: User,
        current_access_token: str | None,
        refresh_token: str,
    ) -> None:
        """Revoke refresh token and current access token by adding JTIs to Redis blacklist."""
        try:
            r_payload = decode_token(refresh_token)
        except Exception as e:
            raise UnauthorizedError("Invalid refresh token.", code="REFRESH_TOKEN_INVALID") from e

        if r_payload.get("type") != "refresh":
            raise UnauthorizedError(
                "Invalid token type. Refresh token required.", code="REFRESH_TOKEN_INVALID"
            )

        r_jti = r_payload.get("jti")
        r_exp = r_payload.get("exp")
        now_ts = int(datetime.now(UTC).timestamp())

        if r_jti and r_exp:
            r_ttl = int(r_exp) - now_ts
            if r_ttl > 0:
                await self.redis.setex(f"token:blacklist:{r_jti}", r_ttl, "1")

        if current_access_token:
            try:
                a_payload = decode_token(current_access_token)
                a_jti = a_payload.get("jti")
                a_exp = a_payload.get("exp")
                if a_jti and a_exp:
                    a_ttl = int(a_exp) - now_ts
                    if a_ttl > 0:
                        await self.redis.setex(f"token:blacklist:{a_jti}", a_ttl, "1")
            except Exception:
                pass
