import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.statements import Category
from app.schemas.categories import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category).where(
            or_(Category.user_id == user.id, Category.is_default == True)
        )
    )
    return result.scalars().all()


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    data: CategoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    category = Category(
        name=data.name,
        color=data.color,
        icon=data.icon,
        user_id=user.id,
        is_default=False,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    data: CategoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if category.is_default or category.user_id != user.id:
        raise HTTPException(status_code=403, detail="Não é possível editar esta categoria")

    if data.name is not None:
        category.name = data.name
    if data.color is not None:
        category.color = data.color if data.color != "" else None
    if data.icon is not None:
        category.icon = data.icon if data.icon != "" else None

    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.transactions))
        .where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if category.is_default or category.user_id != user.id:
        raise HTTPException(status_code=403, detail="Não é possível deletar esta categoria")

    # Move transactions to "Outros"
    if category.transactions:
        outros_result = await db.execute(
            select(Category).where(Category.name == "Outros", Category.is_default == True)
        )
        outros = outros_result.scalar_one()
        for tx in category.transactions:
            tx.category_id = outros.id

    await db.delete(category)
    await db.commit()
