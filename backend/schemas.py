"""Pydantic request/response schemas.

Zero-trust posture: request models reject unknown fields (`extra="forbid"`),
bound every string and number, and use integer cents for money. Reward
percentages are exact decimals capped at 10.00 (%).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models import InviteStatus, Role, RoutingStatus, SpendCategory


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Onboarding / identity
# ---------------------------------------------------------------------------


class OnboardingRequest(StrictModel):
    company_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OnboardingResponse(BaseModel):
    company_id: uuid.UUID
    user_id: uuid.UUID
    role: Role


class MeResponse(BaseModel):
    user_id: uuid.UUID
    company_id: uuid.UUID
    clerk_user_id: str
    role: Role


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class InviteCreate(StrictModel):
    email: str = Field(max_length=320, pattern=_EMAIL_PATTERN)
    role: Role

    @field_validator("email")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        return value.lower()


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Role
    status: InviteStatus
    created_at: datetime


class MemberOut(BaseModel):
    id: uuid.UUID
    email: str | None
    role: Role
    created_at: datetime


# ---------------------------------------------------------------------------
# Card portfolio
# ---------------------------------------------------------------------------


class RewardRuleIn(StrictModel):
    category: SpendCategory
    reward_pct: Decimal = Field(gt=0, le=Decimal("10.00"), decimal_places=2)


class PortfolioCardCreate(StrictModel):
    label: str = Field(min_length=1, max_length=100)
    issuer: str = Field(min_length=1, max_length=100)
    last4: str = Field(pattern=r"^\d{4}$")
    default_reward_pct: Decimal = Field(
        default=Decimal("1.00"), ge=0, le=Decimal("10.00"), decimal_places=2
    )
    rules: list[RewardRuleIn] = Field(default_factory=list, max_length=len(SpendCategory))


class PortfolioCardUpdate(StrictModel):
    active: bool


class RewardRuleOut(BaseModel):
    id: uuid.UUID
    category: SpendCategory
    reward_pct: Decimal


class PortfolioCardOut(BaseModel):
    id: uuid.UUID
    label: str
    issuer: str
    last4: str
    default_reward_pct: Decimal
    active: bool
    rules: list[RewardRuleOut]
    created_at: datetime


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

_MAX_CENTS = 10_000_000_00  # $10M sanity cap on any single limit or amount


class BudgetCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    category: SpendCategory | None = None
    limit_cents: int = Field(gt=0, le=_MAX_CENTS)


class BudgetUpdate(StrictModel):
    limit_cents: int | None = Field(default=None, gt=0, le=_MAX_CENTS)
    active: bool | None = None


class BudgetOut(BaseModel):
    id: uuid.UUID
    name: str
    category: SpendCategory | None
    limit_cents: int
    active: bool
    spent_cents_this_month: int
    remaining_cents: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Per diems
# ---------------------------------------------------------------------------


class PerDiemCreate(StrictModel):
    user_id: uuid.UUID
    daily_limit_cents: int = Field(gt=0, le=_MAX_CENTS)


class PerDiemOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    daily_limit_cents: int
    active: bool
    created_at: datetime


class PerDiemStatus(BaseModel):
    daily_limit_cents: int
    spent_today_cents: int
    remaining_today_cents: int


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class TransactionCreate(StrictModel):
    merchant_name: str = Field(min_length=1, max_length=200)
    amount_cents: int = Field(gt=0, le=_MAX_CENTS)
    occurred_on: date
    category: SpendCategory | None = None  # classified from merchant if omitted
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    portfolio_card_id: uuid.UUID | None = None
    budget_id: uuid.UUID | None = None


class TransactionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    portfolio_card_id: uuid.UUID | None
    budget_id: uuid.UUID | None
    merchant_name: str
    category: SpendCategory
    amount_cents: int
    currency: str
    occurred_on: date
    created_at: datetime


# ---------------------------------------------------------------------------
# Reward Router
# ---------------------------------------------------------------------------


class RecommendationOut(BaseModel):
    vendor_name: str
    category: SpendCategory
    est_monthly_spend_cents: int
    current_card_id: uuid.UUID | None
    current_reward_pct: Decimal
    recommended_card_id: uuid.UUID
    recommended_card_label: str
    recommended_reward_pct: Decimal
    est_monthly_uplift_cents: int


class RoutingDecisionCreate(StrictModel):
    """Accept or dismiss a recommendation.

    Only the vendor and target card are trusted from the client; spend and
    uplift figures are recomputed server-side from transaction history.
    """

    vendor_name: str = Field(min_length=1, max_length=200)
    recommended_card_id: uuid.UUID
    status: RoutingStatus = RoutingStatus.ACCEPTED


class RoutingDecisionOut(BaseModel):
    id: uuid.UUID
    vendor_name: str
    category: SpendCategory
    recommended_card_id: uuid.UUID
    previous_card_id: uuid.UUID | None
    status: RoutingStatus
    est_monthly_spend_cents: int
    est_monthly_uplift_cents: int
    created_at: datetime


class RewardsLedgerOut(BaseModel):
    accepted_decisions: int
    est_monthly_uplift_cents: int
    est_annual_uplift_cents: int
