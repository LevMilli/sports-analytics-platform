"""add injury_reports

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "injury_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("report_date", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("source", sa.String(length=100)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_injury_player_date", "injury_reports", ["player_id", "report_date"])


def downgrade() -> None:
    op.drop_index("idx_injury_player_date", table_name="injury_reports")
    op.drop_table("injury_reports")
