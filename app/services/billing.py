from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.auth import FreeUsage, User
from app.models.payments import Subscription

FREE_PLAN = "free"
SUPER_PLAN = "super"
MASTER_PLAN = "master"
ACTIVE_STATUS = "active"
VALID_PAID_PLANS = {SUPER_PLAN, MASTER_PLAN}


def get_plan_limit(plan: str) -> int | None:
    if plan == SUPER_PLAN:
        return settings.SUPER_ANALYSES_LIMIT
    if plan == MASTER_PLAN:
        return None
    return settings.FREE_ANALYSES_LIMIT


def is_active_paid_subscription(subscription: Subscription | None) -> bool:
    return bool(subscription and subscription.status == ACTIVE_STATUS and subscription.plan in VALID_PAID_PLANS)


def get_effective_plan(subscription: Subscription | None) -> str:
    if is_active_paid_subscription(subscription):
        return subscription.plan
    return FREE_PLAN


async def get_or_create_free_usage(db: AsyncSession, user: User, lock: bool = False) -> FreeUsage:
    query = select(FreeUsage).where(FreeUsage.user_id == user.id)
    if lock:
        query = query.with_for_update()
    result = await db.execute(query)
    free_usage = result.scalar_one_or_none()
    if free_usage is None:
        free_usage = FreeUsage(user_id=user.id, analyses_used=0)
        db.add(free_usage)
        await db.flush()
    return free_usage


async def get_billing_status(db: AsyncSession, user: User) -> dict:
    plan = get_effective_plan(user.subscription)
    limit = get_plan_limit(plan)

    if plan == FREE_PLAN:
        free_usage = await get_or_create_free_usage(db, user)
        analyses_used = free_usage.analyses_used
        current_period_end = None
        subscription_status = FREE_PLAN
    else:
        analyses_used = user.subscription.analyses_used
        current_period_end = user.subscription.current_period_end
        subscription_status = user.subscription.status

    remaining = None if limit is None else max(limit - analyses_used, 0)
    return {
        "plan": plan,
        "status": subscription_status,
        "analyses_used": analyses_used,
        "analyses_limit": limit,
        "analyses_remaining": remaining,
        "current_period_end": current_period_end,
    }


async def consume_analysis_or_raise(db: AsyncSession, user: User) -> None:
    plan = get_effective_plan(user.subscription)

    if plan == MASTER_PLAN:
        return

    if plan == SUPER_PLAN:
        # Lock the subscription row to prevent concurrent bypass
        locked_result = await db.execute(
            select(Subscription).where(Subscription.user_id == user.id).with_for_update()
        )
        subscription = locked_result.scalar_one_or_none()
        if subscription is None or subscription.analyses_used >= settings.SUPER_ANALYSES_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Limite de análises do plano Super atingido",
            )
        subscription.analyses_used += 1
        return

    free_usage = await get_or_create_free_usage(db, user, lock=True)
    if free_usage.analyses_used >= settings.FREE_ANALYSES_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Limite de análises gratuitas atingido",
        )
    free_usage.analyses_used += 1


def plan_from_price_id(price_id: str | None) -> str:
    if price_id and price_id == settings.STRIPE_SUPER_PRICE_ID:
        return SUPER_PLAN
    if price_id and price_id == settings.STRIPE_MASTER_PRICE_ID:
        return MASTER_PLAN
    return FREE_PLAN


async def upsert_subscription(
    db: AsyncSession,
    user_id,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
    status_value: str,
    plan: str,
    current_period_start: datetime | None,
    current_period_end: datetime | None,
) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    subscription = result.scalar_one_or_none()

    if subscription is None:
        subscription = Subscription(user_id=user_id, status=status_value)
        db.add(subscription)

    subscription.stripe_customer_id = stripe_customer_id or subscription.stripe_customer_id
    subscription.stripe_subscription_id = stripe_subscription_id or subscription.stripe_subscription_id
    subscription.status = status_value
    subscription.plan = plan
    subscription.current_period_start = current_period_start
    subscription.current_period_end = current_period_end

    if current_period_start and subscription.current_period_start != current_period_start:
        subscription.analyses_used = 0

    return subscription
