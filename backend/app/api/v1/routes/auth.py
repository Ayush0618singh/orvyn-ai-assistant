from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    email = request.email.lower().strip()

    existing_result = await db.execute(
        select(User).where(
            User.email == email
        )
    )

    existing_user = (
        existing_result.scalar_one_or_none()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An account with this email already exists."
            ),
        )

    user = User(
        email=email,
        password_hash=hash_password(
            request.password
        ),
    )

    db.add(user)

    await db.commit()
    await db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    email = request.email.lower().strip()

    result = await db.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one_or_none()

    if not user or not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    token = create_access_token(
        subject=user.id
    )

    response.set_cookie(
        key=settings.access_token_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=(
            settings.access_token_expire_minutes
            * 60
        ),
        path="/",
    )

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(
            user
        ),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    response: Response,
) -> Response:
    response.delete_cookie(
        key=settings.access_token_cookie_name,
        path="/",
    )

    response.status_code = (
        status.HTTP_204_NO_CONTENT
    )

    return response


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(
        get_current_user
    ),
) -> User:
    return current_user