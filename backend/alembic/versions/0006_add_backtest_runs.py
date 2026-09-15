"""add backtest_runs

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("model_name", sa.String(length=50), nullable=False),
        sa.Column("games_evaluated", sa.Integer(), nullable=False),
        sa.Column("accuracy", sa.Numeric(5, 4)),
        sa.Column("brier_score", sa.Numeric(6, 5)),
        sa.Column("log_loss", sa.Numeric(7, 5)),
        sa.Column("run_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("backtest_runs")
