"""
Import every model module here so that Base.metadata.create_all()
(used in dev/tests) and Alembic's autogenerate (used in production
migrations) both see the complete set of tables.
"""

from app.db.models.core import (  # noqa: F401
    Sport, League, Team, Game, Player, TeamGameStats, PlayerGameStats,
    InjuryReport, TeamGameFeatures, IngestionLog,
)
