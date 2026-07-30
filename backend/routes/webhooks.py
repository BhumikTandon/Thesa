"""JIT funding webhook receiver.

Security order (DOCUMENTATION.md §9):
1. Read raw body
2. HMAC + timestamp verification (constant-time) — before JSON parse / DB
3. Replay protection via webhook_events.event_id uniqueness
4. Resolve card via SECURITY DEFINER, set tenant context, run Card Teller
5. Fail closed: any unexpected error → decline

The issuer today is a local stub that POSTs the same signed payload shape
Marqeta will use later.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.config import get_settings
from backend.db.session import get_session_factory
from backend.models import (
    AuthDecision,
    AuthorizationDecision,
    IssuedCard,
    Transaction,
    WebhookEvent,
)
from backend.schemas import JitWebhookIn, JitWebhookResponse
from backend.services.card_teller import evaluate_authorization
from backend.services.webhook_security import verify_signature
from pydantic import ValidationError

router = APIRouter(prefix="/webhooks")


@router.post("/jit", response_model=None)
async def jit_funding(request: Request) -> JitWebhookResponse | JSONResponse:
    """Handle a JIT authorization request from the (stub) card issuer."""
    settings = get_settings()
    body = await request.body()
    timestamp = request.headers.get("X-Thesa-Timestamp", "")
    signature = request.headers.get("X-Thesa-Signature", "")

    sig_error = verify_signature(
        secret=settings.webhook_hmac_secret,
        timestamp=timestamp,
        body=body,
        provided=signature,
        skew_seconds=settings.webhook_timestamp_skew_seconds,
    )
    if sig_error:
        return JSONResponse(
            status_code=401, content={"detail": f"Webhook rejected: {sig_error}"}
        )

    try:
        payload = json.loads(body)
        event = JitWebhookIn.model_validate(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})
    except ValidationError as exc:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid payload", "errors": exc.errors()},
        )

    event_id = event.event_id
    external_token = event.external_token
    merchant_name = event.merchant_name
    amount_cents = event.amount_cents

    factory = get_session_factory(settings)

    # Replay: prior completed event returns the same decision.
    async with factory() as session:
        existing = (
            await session.execute(
                select(WebhookEvent).where(WebhookEvent.event_id == event_id)
            )
        ).scalar_one_or_none()
        if existing is not None and existing.decision:
            return JitWebhookResponse(
                decision=AuthDecision(existing.decision),
                reason=existing.reason or "replay",
            )

        resolved = (
            await session.execute(
                text(
                    "SELECT card_id, company_id FROM resolve_issued_card(:token)"
                ),
                {"token": external_token},
            )
        ).mappings().first()

    if resolved is None:
        async with factory() as session:
            try:
                session.add(
                    WebhookEvent(
                        event_id=event_id,
                        decision=AuthDecision.DECLINED.value,
                        reason="unknown_card",
                    )
                )
                await session.commit()
            except IntegrityError:
                await session.rollback()
                prior = await _prior_decision(factory, event_id)
                if prior:
                    return prior
        return JitWebhookResponse(
            decision=AuthDecision.DECLINED, reason="unknown_card"
        )

    try:
        return await _decide_and_record(
            factory=factory,
            company_id=resolved["company_id"],
            card_id=resolved["card_id"],
            event_id=event_id,
            merchant_name=merchant_name,
            amount_cents=amount_cents,
        )
    except Exception:
        # Fail closed — never approve when the decision path errors.
        async with factory() as session:
            try:
                session.add(
                    WebhookEvent(
                        event_id=event_id,
                        decision=AuthDecision.DECLINED.value,
                        reason="teller_error",
                    )
                )
                await session.commit()
            except IntegrityError:
                await session.rollback()
                prior = await _prior_decision(factory, event_id)
                if prior:
                    return prior
        return JitWebhookResponse(
            decision=AuthDecision.DECLINED, reason="teller_error"
        )


async def _prior_decision(factory, event_id: str) -> JitWebhookResponse | None:
    async with factory() as session:
        prior = (
            await session.execute(
                select(WebhookEvent).where(WebhookEvent.event_id == event_id)
            )
        ).scalar_one_or_none()
        if prior and prior.decision:
            return JitWebhookResponse(
                decision=AuthDecision(prior.decision),
                reason=prior.reason or "replay",
            )
    return None


async def _decide_and_record(
    *,
    factory,
    company_id: uuid.UUID,
    card_id: uuid.UUID,
    event_id: str,
    merchant_name: str,
    amount_cents: int,
) -> JitWebhookResponse:
    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": str(company_id)},
        )
        await session.execute(
            text("SELECT set_config('app.current_user', :user_id, true)"),
            {"user_id": "webhook:jit"},
        )

        # Claim the event_id first so concurrent workers cannot double-spend.
        try:
            session.add(WebhookEvent(event_id=event_id))
            await session.flush()
        except IntegrityError:
            await session.rollback()
            prior = await _prior_decision(factory, event_id)
            if prior:
                return prior
            return JitWebhookResponse(
                decision=AuthDecision.DECLINED, reason="event_race"
            )

        card = (
            await session.execute(select(IssuedCard).where(IssuedCard.id == card_id))
        ).scalar_one_or_none()
        if card is None:
            event = (
                await session.execute(
                    select(WebhookEvent).where(WebhookEvent.event_id == event_id)
                )
            ).scalar_one()
            event.decision = AuthDecision.DECLINED.value
            event.reason = "unknown_card"
            await session.commit()
            return JitWebhookResponse(
                decision=AuthDecision.DECLINED, reason="unknown_card"
            )

        teller = await evaluate_authorization(
            session,
            card=card,
            merchant_name=merchant_name,
            amount_cents=amount_cents,
        )

        session.add(
            AuthorizationDecision(
                company_id=company_id,
                issued_card_id=card.id,
                event_id=event_id,
                merchant_name=merchant_name,
                category=teller.category,
                amount_cents=amount_cents,
                decision=teller.decision.value,
                reason=teller.reason,
            )
        )

        if teller.decision == AuthDecision.APPROVED:
            session.add(
                Transaction(
                    company_id=company_id,
                    user_id=card.user_id,
                    issued_card_id=card.id,
                    budget_id=card.budget_id,
                    merchant_name=merchant_name,
                    category=teller.category,
                    amount_cents=amount_cents,
                    occurred_on=date.today(),
                )
            )

        event = (
            await session.execute(
                select(WebhookEvent).where(WebhookEvent.event_id == event_id)
            )
        ).scalar_one()
        event.decision = teller.decision.value
        event.reason = teller.reason
        await session.commit()

        return JitWebhookResponse(
            decision=teller.decision, reason=teller.reason
        )
