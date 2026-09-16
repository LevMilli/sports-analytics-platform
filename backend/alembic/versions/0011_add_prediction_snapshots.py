"""add prediction_snapshots table

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prediction_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("model_name", sa.String(length=50), nullable=False),
        sa.Column("win_probability", sa.Numeric(5, 4), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("prediction_snapshots")
