"""add team_game_features

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_game_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("is_home", sa.Boolean(), nullable=False),
        sa.Column("rest_days", sa.Integer()),
        sa.Column("games_played_prior", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rolling_win_pct", sa.Numeric(4, 3)),
        sa.Column("rolling_points_for_avg", sa.Numeric(6, 2)),
        sa.Column("rolling_points_against_avg", sa.Numeric(6, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("game_id", "team_id"),
    )


def downgrade() -> None:
    op.drop_table("team_game_features")
