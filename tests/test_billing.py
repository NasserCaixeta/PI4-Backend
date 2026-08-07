from datetime import datetime, timezone
import uuid

import pytest

from app.models.auth import User
from app.models.payments import Subscription
from app.services.billing import upsert_subscription


async def _create_user(db, user_id):
    user = User(
        id=user_id,
        email=f"{user_id.hex}@example.com",
        auth_provider="email",
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.anyio
async def test_upsert_subscription_resets_usage_when_period_changes(db):
    user_id = uuid.uuid4()
    await _create_user(db, user_id)
    old_period = datetime(2026, 4, 1, tzinfo=timezone.utc)
    new_period = datetime(2026, 5, 1, tzinfo=timezone.utc)

    subscription = Subscription(
        user_id=user_id,
        stripe_customer_id="cus_old",
        stripe_subscription_id="sub_old",
        status="active",
        plan="super",
        analyses_used=7,
        current_period_start=old_period,
        current_period_end=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )
    db.add(subscription)
    await db.commit()

    updated = await upsert_subscription(
        db=db,
        user_id=user_id,
        stripe_customer_id="cus_old",
        stripe_subscription_id="sub_old",
        status_value="active",
        plan="super",
        current_period_start=new_period,
        current_period_end=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    assert updated.analyses_used == 0
    assert updated.current_period_start == new_period


@pytest.mark.anyio
async def test_upsert_subscription_keeps_usage_when_period_is_same(db):
    user_id = uuid.uuid4()
    await _create_user(db, user_id)
    period = datetime(2026, 4, 1, tzinfo=timezone.utc)

    subscription = Subscription(
        user_id=user_id,
        stripe_customer_id="cus_same",
        stripe_subscription_id="sub_same",
        status="active",
        plan="super",
        analyses_used=4,
        current_period_start=period,
        current_period_end=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )
    db.add(subscription)
    await db.commit()

    updated = await upsert_subscription(
        db=db,
        user_id=user_id,
        stripe_customer_id="cus_same",
        stripe_subscription_id="sub_same",
        status_value="active",
        plan="super",
        current_period_start=period,
        current_period_end=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )

    assert updated.analyses_used == 4
