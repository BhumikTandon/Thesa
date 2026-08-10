"""initial schema

Revision ID: 7bb0511e4cc8
Revises:
Create Date: 2026-08-09 17:17:18.921995

Creates (or no-ops if present) every table defined on SQLAlchemy metadata.
RLS policies and grants are applied separately by backend.db.bootstrap.
"""

from typing import Sequence, Union

from alembic import op

from backend.models import Base

revision: str = "7bb0511e4cc8"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
