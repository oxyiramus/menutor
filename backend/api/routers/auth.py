from collections.abc import Callable, Coroutine
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from backend.api.auth import get_current_user
from backend.api.deps import get_container
from backend.api.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from backend.application.use_cases.auth import (
    ChangePasswordData,
    LoginData,
    RegisterData,
    UpdateProfileData,
)
from backend.composition_root import ApplicationContainer
from backend.domain.entities.user import User
from backend.domain.exceptions import AuthenticationError


class AuthRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[None, None, Response]]:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # Even a missing field can put the entire body in the error input.
                details = [
                    {key: error[key] for key in ("type", "loc", "msg")}
                    for error in exc.errors()
                ]
                return JSONResponse(status_code=422, content={"detail": details})

        return handle


router = APIRouter(prefix="/auth", tags=["auth"], route_class=AuthRoute)


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(
    *,
    body: RegisterRequest,
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> UserResponse:
    user = container.register_user.execute(
        RegisterData(
            email=body.email,
            password=body.password,
            nickname=body.nickname,
        )
    )
    return UserResponse(
        id=int(user.id),
        email=user.email,
        nickname=user.nickname,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    *,
    body: LoginRequest,
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> TokenResponse:
    pair = container.login_user.execute(
        LoginData(email=body.email, password=body.password)
    )
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    *,
    body: RefreshRequest,
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> TokenResponse:
    pair = container.refresh_access_token.execute(body.refresh_token)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    *,
    body: RefreshRequest,
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> None:
    container.logout_user.execute(body.refresh_token)


@router.get("/me", response_model=UserResponse)
def get_me(*, user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(
        id=int(user.id),
        email=user.email,
        nickname=user.nickname,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    *,
    body: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> None:
    try:
        container.change_password.execute(
            user,
            ChangePasswordData(
                current_password=body.current_password,
                new_password=body.new_password,
            ),
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.patch("/me", response_model=UserResponse)
def update_me(
    *,
    body: UpdateProfileRequest,
    user: Annotated[User, Depends(get_current_user)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> UserResponse:
    updated = container.update_profile.execute(
        user, UpdateProfileData(nickname=body.nickname)
    )
    return UserResponse(
        id=int(updated.id),
        email=updated.email,
        nickname=updated.nickname,
        created_at=updated.created_at,
        last_login_at=updated.last_login_at,
    )
