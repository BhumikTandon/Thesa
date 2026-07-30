"""SQLAlchemy ORM models for all tenant-scoped tables.

Conventions:
- Every tenant-scoped table carries a `company_id` column so PostgreSQL RLS
  policies can filter on `current_setting('app.current_tenant')` directly.
- Monetary values are stored as integer cents, never floats.
- Reward multipliers are percent-back values (e.g. 1.50 = 1.5% back) stored
  as exact decimals.
- RLS policies, audit triggers, and auth functions live in `backend/db/rls.sql`
  and are applied by `backend/db/bootstrap.py` after table creation.
"""

import enum
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Role(str, enum.Enum):
    OWNER = "owner"
    OFFICE_MANAGER = "office_manager"
    CREW_LEAD = "crew_lead"


class SpendCategory(str, enum.Enum):
    FUEL = "fuel"
    LODGING = "lodging"
    MATERIALS = "materials"
    FOOD = "food"
    TRAVEL = "travel"
    OTHER = "other"


class RoutingStatus(str, enum.Enum):
    RECOMMENDED = "recommended"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


class InviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


class IssuedCardStatus(str, enum.Enum):
    REQUESTED = "requested"
    ACTIVE = "active"
    FROZEN = "frozen"
    CANCELED = "canceled"


class AuthDecision(str, enum.Enum):
    APPROVED = "approved"
    DECLINED = "declined"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("clerk_user_id", name="uq_users_clerk_user_id"),
        CheckConstraint(
            "role IN ('owner', 'office_manager', 'crew_lead')",
            name="ck_users_role",
        ),
        Index("ix_users_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    clerk_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Invite(Base):
    """An invitation for an employee to join a company.

    Emails are stored lowercased. At most one pending invite per
    (company, email); joining matches the authenticated user's verified Clerk
    email against pending invites via the SECURITY DEFINER `accept_invite`
    function.
    """

    __tablename__ = "invites"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'office_manager', 'crew_lead')",
            name="ck_invites_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked')",
            name="ck_invites_status",
        ),
        Index(
            "uq_invites_pending_email",
            "company_id",
            "email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_invites_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class PortfolioCard(Base):
    """An existing corporate card in the company's wallet.

    Input to the Reward Router: Thesa never issues these, it routes spend
    across them. `default_reward_pct` is the percent-back earned on spend
    that matches no category rule.
    """

    __tablename__ = "portfolio_cards"
    __table_args__ = (
        CheckConstraint("char_length(last4) = 4", name="ck_portfolio_cards_last4"),
        Index("ix_portfolio_cards_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    issuer: Mapped[str] = mapped_column(String(100), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    default_reward_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("1.00")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created_at()


class RewardRule(Base):
    """Category-specific percent-back for a portfolio card (e.g. fuel → 4%)."""

    __tablename__ = "reward_rules"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_card_id", "category", name="uq_reward_rules_card_category"
        ),
        CheckConstraint(
            "category IN ('fuel', 'lodging', 'materials', 'food', 'travel', 'other')",
            name="ck_reward_rules_category",
        ),
        Index("ix_reward_rules_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    portfolio_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio_cards.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    reward_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Budget(Base):
    """A monthly spending envelope, typically per job site or department."""

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("limit_cents > 0", name="ck_budgets_limit_positive"),
        Index("ix_budgets_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(20))
    limit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created_at()


class PerDiem(Base):
    """A daily allowance for a field employee."""

    __tablename__ = "per_diems"
    __table_args__ = (
        CheckConstraint("daily_limit_cents > 0", name="ck_per_diems_limit_positive"),
        UniqueConstraint("user_id", name="uq_per_diems_user"),
        Index("ix_per_diems_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    daily_limit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created_at()


class Transaction(Base):
    """A purchase record. Manual entry or written by an approved JIT auth."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_transactions_amount_positive"),
        Index("ix_transactions_company_id", "company_id"),
        Index("ix_transactions_company_occurred", "company_id", "occurred_on"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    portfolio_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio_cards.id")
    )
    issued_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issued_cards.id")
    )
    budget_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budgets.id")
    )
    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'USD'")
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class SpendPolicy(Base):
    """Company-wide spend rule evaluated by the Card Teller.

    Any matching deny wins (fail closed). `denied_categories` is a JSON array
    of category strings; empty means no category denials from this row.
    """

    __tablename__ = "spend_policies"
    __table_args__ = (
        CheckConstraint(
            "max_transaction_cents IS NULL OR max_transaction_cents > 0",
            name="ck_spend_policies_max_positive",
        ),
        Index("ix_spend_policies_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    denied_categories: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    max_transaction_cents: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created_at()


class IssuedCard(Base):
    """A Thesa-issued virtual card scoped to a vendor/category/budget.

    Never stores a PAN — only the issuer's network token (`external_token`)
    and last4. Today the issuer is a local stub; Marqeta swaps in later
    behind the same interface.
    """

    __tablename__ = "issued_cards"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'active', 'frozen', 'canceled')",
            name="ck_issued_cards_status",
        ),
        CheckConstraint(
            "char_length(last4) = 4", name="ck_issued_cards_last4"
        ),
        CheckConstraint(
            "single_tx_limit_cents IS NULL OR single_tx_limit_cents > 0",
            name="ck_issued_cards_limit_positive",
        ),
        UniqueConstraint(
            "external_token", name="uq_issued_cards_external_token"
        ),
        Index("ix_issued_cards_company_id", "company_id"),
        Index("ix_issued_cards_external_token", "external_token"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    budget_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budgets.id")
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    # Opaque issuer reference (network token / stub id). Never a PAN.
    external_token: Mapped[str] = mapped_column(String(128), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    # Optional scopes: null means unrestricted on that axis.
    scoped_vendor: Mapped[str | None] = mapped_column(String(200))
    scoped_category: Mapped[str | None] = mapped_column(String(20))
    single_tx_limit_cents: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class AuthorizationDecision(Base):
    """Outcome of one Card Teller evaluation on a JIT authorization request."""

    __tablename__ = "authorization_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'declined')",
            name="ck_authorization_decisions_decision",
        ),
        CheckConstraint(
            "amount_cents > 0", name="ck_authorization_decisions_amount_positive"
        ),
        UniqueConstraint(
            "event_id", name="uq_authorization_decisions_event_id"
        ),
        Index("ix_authorization_decisions_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    issued_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issued_cards.id"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    merchant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class WebhookEvent(Base):
    """Idempotency store for JIT webhook event IDs (replay protection).

    Not tenant-scoped: events arrive before tenant context is known. Holds
    only the event id and outcome — never the raw payload.
    """

    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    decision: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = _created_at()


class RoutingDecision(Base):
    """A Reward Router recommendation and its lifecycle.

    Accepted decisions form the rewards ledger: `est_monthly_uplift_cents`
    is the value Thesa created, the basis for take-rate billing.
    """

    __tablename__ = "routing_decisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('recommended', 'accepted', 'dismissed')",
            name="ck_routing_decisions_status",
        ),
        Index("ix_routing_decisions_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    vendor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio_cards.id"), nullable=False
    )
    previous_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolio_cards.id")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'recommended'")
    )
    est_monthly_spend_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    est_monthly_uplift_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = _created_at()


class AuditLog(Base):
    """Immutable audit trail, written exclusively by database triggers.

    The application role has INSERT-only grants (no UPDATE/DELETE); rows are
    inserted by the `audit_row_change` trigger function in rls.sql, never by
    application code.
    """

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_company_id", "company_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(Text)
    old_data: Mapped[dict | None] = mapped_column(JSONB)
    new_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created_at()
