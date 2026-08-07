from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.auth import User
from app.schemas.auth import (
    EmailVerificationRequest,
    LoginRequest,
    ResendEmailVerificationResponse,
    TokenResponse,
    UpdateProfileRequest,
    UserCreate,
    UserResponse,
)
from app.services.email import EmailDeliveryError
from app.services.email_verification import (
    EmailVerificationCooldownError,
    EmailVerificationError,
    create_and_send_verification_code,
    verify_email_code,
)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["Auth"])

_COOKIE_MAX_AGE = settings.JWT_EXPIRATION_DAYS * 86400
_IS_PROD = settings.APP_ENV == "production"
# Cross-origin (frontend on pages.dev, backend on onrender.com) requires SameSite=None + Secure
_SAMESITE = "none" if _IS_PROD else "lax"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="token",
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=_IS_PROD,
        samesite=_SAMESITE,
        path="/",
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, data: UserCreate, response: Response, db: AsyncSession = Depends(get_db)):
    # Verifica se email já existe
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado",
        )

    # Cria usuário
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        auth_provider="email",
    )
    db.add(user)
    await db.flush()
    try:
        await create_and_send_verification_code(db, user)
    except EmailDeliveryError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nao foi possivel enviar o codigo de verificacao",
        ) from exc
    await db.commit()
    await db.refresh(user)

    # Gera token, seta cookie httpOnly e retorna
    token = create_access_token(user.id)
    _set_auth_cookie(response, token)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    # Busca usuário
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
        )

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
        )

    token = create_access_token(user.id)
    _set_auth_cookie(response, token)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(key="token", path="/", httponly=True)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.post("/verify-email", response_model=UserResponse)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    data: EmailVerificationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await verify_email_code(db, user, data.code)
    except EmailVerificationError as exc:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/resend-verification", response_model=ResendEmailVerificationResponse)
@limiter.limit("3/minute")
async def resend_email_verification(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.email_verified_at is not None:
        return ResendEmailVerificationResponse(message="Email ja verificado")

    try:
        await create_and_send_verification_code(db, user, enforce_cooldown=True)
    except EmailVerificationCooldownError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "verification_cooldown",
                "message": "Aguarde antes de solicitar um novo codigo",
                "resend_available_in_seconds": exc.retry_after_seconds,
            },
        ) from exc
    except EmailDeliveryError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nao foi possivel enviar o codigo de verificacao",
        ) from exc

    await db.commit()
    return ResendEmailVerificationResponse(message="Codigo reenviado")


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.name is not None:
        user.name = data.name

    if data.new_password is not None:
        if user.auth_provider != "email":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Troca de senha não disponível para login social",
            )
        if not data.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe a senha atual",
            )
        if not verify_password(data.current_password, user.password_hash or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Senha atual incorreta",
            )
        user.password_hash = hash_password(data.new_password)

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
