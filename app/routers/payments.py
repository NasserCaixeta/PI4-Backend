from __future__ import annotations

from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.payments import Subscription
from app.schemas.payments import BillingStatusResponse, CheckoutRequest, CheckoutResponse, PortalResponse
from app.services.billing import MASTER_PLAN, SUPER_PLAN, get_billing_status, plan_from_price_id, upsert_subscription

router = APIRouter(prefix="/payments", tags=["Payments"])


def _require_stripe_key() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe não configurado",
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _price_id_for_plan(plan: str) -> str:
    if plan == SUPER_PLAN and settings.STRIPE_SUPER_PRICE_ID:
        return settings.STRIPE_SUPER_PRICE_ID
    if plan == MASTER_PLAN and settings.STRIPE_MASTER_PRICE_ID:
        return settings.STRIPE_MASTER_PRICE_ID
    raise HTTPException(status_code=400, detail="Plano inválido ou não configurado")


def _timestamp_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


@router.get("/me", response_model=BillingStatusResponse)
async def get_my_billing(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_billing_status(db, user)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    data: CheckoutRequest,
    user: User = Depends(get_current_user),
):
    _require_stripe_key()
    price_id = _price_id_for_plan(data.plan)

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=user.email,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/dashboard?checkout=success",
        cancel_url=f"{settings.FRONTEND_URL}/dashboard?checkout=cancel",
        metadata={"user_id": str(user.id), "plan": data.plan},
        subscription_data={"metadata": {"user_id": str(user.id), "plan": data.plan}},
    )
    return CheckoutResponse(checkout_url=session.url)


@router.post("/portal", response_model=PortalResponse)
async def create_billing_portal(
    user: User = Depends(get_current_user),
):
    _require_stripe_key()
    if not user.subscription or not user.subscription.stripe_customer_id:
        raise HTTPException(status_code=404, detail="Cliente Stripe não encontrado")

    session = stripe.billing_portal.Session.create(
        customer=user.subscription.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/dashboard",
    )
    return PortalResponse(portal_url=session.url)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook Stripe não configurado")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Webhook inválido")

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        user_id = obj.get("metadata", {}).get("user_id")
        subscription_id = obj.get("subscription")
        customer_id = obj.get("customer")
        plan = obj.get("metadata", {}).get("plan", SUPER_PLAN)
        if user_id and subscription_id:
            await upsert_subscription(
                db=db,
                user_id=user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                status_value="active",
                plan=plan,
                current_period_start=None,
                current_period_end=None,
            )
            await db.commit()

    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        subscription_id = obj.get("id")
        metadata = obj.get("metadata", {})
        user_id = metadata.get("user_id")
        items = obj.get("items", {}).get("data", [])
        price_id = items[0].get("price", {}).get("id") if items else None
        plan = metadata.get("plan") or plan_from_price_id(price_id)
        status_value = obj.get("status", "canceled")
        if event_type == "customer.subscription.deleted":
            status_value = "canceled"

        if not user_id and subscription_id:
            result = await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
            )
            existing = result.scalar_one_or_none()
            user_id = existing.user_id if existing else None

        if user_id:
            await upsert_subscription(
                db=db,
                user_id=user_id,
                stripe_customer_id=obj.get("customer"),
                stripe_subscription_id=subscription_id,
                status_value=status_value,
                plan=plan,
                current_period_start=_timestamp_to_datetime(obj.get("current_period_start")),
                current_period_end=_timestamp_to_datetime(obj.get("current_period_end")),
            )
            await db.commit()

    return {"received": True}
