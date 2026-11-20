from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    nickname: str
    created_at: datetime
    last_login_at: datetime | None = None


class UpdateProfileRequest(BaseModel):
    # Preserve the handling of unrelated fields while forbidding password explicitly.
    model_config = ConfigDict(json_schema_extra={"not": {"required": ["password"]}})

    nickname: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_password(cls, data: Any) -> Any:
        if isinstance(data, dict) and "password" in data:
            raise ValueError("Для смены пароля используйте POST /api/auth/me/password")
        return data


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
