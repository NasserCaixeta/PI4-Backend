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
from app.schemas.auth import LoginRequest, TokenResponse, UpdateProfileRequest, UserCreate, UserResponse

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
