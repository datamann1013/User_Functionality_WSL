from __future__ import with_statement
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# Anchor the import to the module root (the directory that contains the
# `core_memory` package and `alembic/`), which is the parent of this env.py's
# directory. This is CWD-independent: works in Docker (/app) and from a checkout
# (projects/RuneCore_Memory/).
import sys
_MODULE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MODULE_ROOT not in sys.path:
    sys.path.insert(0, _MODULE_ROOT)
from core_memory.db import Base
target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
