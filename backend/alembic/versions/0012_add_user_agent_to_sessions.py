"""add user_agent to sessions

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("user_agent", sa.String(length=255)))


def downgrade() -> None:
    op.drop_column("sessions", "user_agent")
