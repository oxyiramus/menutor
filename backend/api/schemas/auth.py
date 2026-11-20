import re
from datetime import datetime

from pydantic import BaseModel, field_validator

# A dot-separated local part and domain labels without leading or trailing hyphens.
_EMAIL_ATOM = r"[\w!#$%&'*+/=?^`{|}~-]+"
_DOMAIN_LABEL = r"[^\W_](?:(?:[^\W_]|-)*[^\W_])?"
_EMAIL_PATTERN = re.compile(
    rf"{_EMAIL_ATOM}(?:\.{_EMAIL_ATOM})*@{_DOMAIN_LABEL}(?:\.{_DOMAIN_LABEL})*"
)


class RegisterRequest(BaseModel):
    email: str
    password: str
    nickname: str = ""

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        if not _EMAIL_PATTERN.fullmatch(email):
            raise ValueError("Введите корректный email")
        return email


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
    nickname: str | None = None
    password: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
