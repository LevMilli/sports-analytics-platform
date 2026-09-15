"""add profile fields and deactivation to users

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=150)))
    op.add_column("users", sa.Column("phone", sa.String(length=30)))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("users", "is_active")
    op.drop_column("users", "phone")
    op.drop_column("users", "full_name")
