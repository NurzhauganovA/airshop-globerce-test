# alembic/env.py

import sys
import os
from logging.config import fileConfig

from sqlalchemy import create_engine  # Added create_engine here

from alembic import context

# Add your app directory to the system path
# This is crucial for importing your models and config from outside the alembic folder
sys.path.append(os.getcwd())

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Import your SQLAlchemy Base and all models
from app.core.database import Base
from app.models.internal_model import *
from app.models.transaction_models import *
from app.models.category_models import *
from app.models.warehouse_models import *
from app.models.notification_models import *
from app.models.cms_models import *


# this is the metadata object for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    This is not recommended for this use case.
    """
    raise NotImplementedError("Offline mode is not supported for this project.")


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    This will connect to the database and use it for autogenerate.
    """
    # Use the DATABASE_URL environment variable to connect
    connectable = create_engine(os.environ.get("DATABASE_URL"))

    # Exclude tables from autogenerate
    def include_object(object, name, type_, reflected, compare_to):
        if type_ == "table" and name in {"celery_taskmeta", "celery_tasksetmeta"}:
            return False
        return True

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
