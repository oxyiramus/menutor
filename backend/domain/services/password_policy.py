from backend.domain.exceptions import DomainError

MIN_NEW_PASSWORD_CHARACTERS = 12
MAX_PASSWORD_BYTES = 72


def validate_password_size(password: str) -> None:
    try:
        size = len(password.encode("utf-8"))
    except UnicodeEncodeError:
        raise DomainError("Пароль должен быть в кодировке UTF-8") from None
    if size > MAX_PASSWORD_BYTES:
        raise DomainError(
            f"Пароль должен занимать не более {MAX_PASSWORD_BYTES} байт в UTF-8"
        )


def validate_new_password(password: str) -> None:
    validate_password_size(password)
    if len(password) < MIN_NEW_PASSWORD_CHARACTERS:
        raise DomainError(
            f"Пароль должен содержать не менее {MIN_NEW_PASSWORD_CHARACTERS} символов"
        )
