"""
Alembic environment script.

Why this is different from the stock template:
- The DB URL comes from app.config.settings instead of alembic.ini, so
  there's exactly one place (the .env file) that knows the real
  connection string.
- target_metadata points at our actual Base.metadata, and we import
  app.db.models.core so every model in that file is registered on Base
  before Alembic looks at it -- otherwise autogenerate would see an
  empty metadata object and think every table needs to be dropped.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the `app` package importable when Alembic is run from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402
from app.db.models import core  # noqa: E402,F401  (registers models on Base)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override whatever (blank) sqlalchemy.url is in alembic.ini with the
# real one from application settings.
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade --sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection -- the normal path."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
