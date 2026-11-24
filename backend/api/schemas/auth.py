import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.domain.services.password_policy import (
    MAX_PASSWORD_BYTES,
    MIN_NEW_PASSWORD_CHARACTERS,
)

_PASSWORD_SIZE = f"Не более {MAX_PASSWORD_BYTES} байт в UTF-8"
_NEW_PASSWORD_SIZE = (
    f"Не менее {MIN_NEW_PASSWORD_CHARACTERS} символов. {_PASSWORD_SIZE}"
)

# A dot-separated local part and domain labels without leading or trailing hyphens.
_EMAIL_ATOM = r"[\w!#$%&'*+/=?^`{|}~-]+"
_DOMAIN_LABEL = r"[^\W_](?:(?:[^\W_]|-)*[^\W_])?"
_EMAIL_PATTERN = re.compile(
    rf"{_EMAIL_ATOM}(?:\.{_EMAIL_ATOM})*@{_DOMAIN_LABEL}(?:\.{_DOMAIN_LABEL})*"
)


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(repr=False, description=_NEW_PASSWORD_SIZE)
    nickname: str = ""

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        if not _EMAIL_PATTERN.fullmatch(email):
            raise ValueError("Введите корректный email")
        return email


class LoginRequest(BaseModel):
    email: str
    password: str = Field(repr=False, description=_PASSWORD_SIZE)


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
    current_password: str = Field(repr=False, description=_PASSWORD_SIZE)
    new_password: str = Field(repr=False, description=_NEW_PASSWORD_SIZE)
