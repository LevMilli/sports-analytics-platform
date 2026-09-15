"""add elo_rating and elo_win_prob to team_game_features

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("team_game_features", sa.Column("elo_rating", sa.Numeric(7, 2)))
    op.add_column("team_game_features", sa.Column("elo_win_prob", sa.Numeric(5, 4)))


def downgrade() -> None:
    op.drop_column("team_game_features", "elo_win_prob")
    op.drop_column("team_game_features", "elo_rating")
