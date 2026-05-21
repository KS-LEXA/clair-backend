from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.config import settings
from app.db.session import Base  # noqa: F401

# 모든 모델 import — autogenerate가 테이블을 인식하려면 필수
import app.models.user  # noqa: F401
import app.models.social_account  # noqa: F401
import app.models.contract  # noqa: F401
import app.models.analysis  # noqa: F401
import app.models.chat  # noqa: F401
import app.models.notification  # noqa: F401
import app.models.password_reset  # noqa: F401
import app.models.email_verification  # noqa: F401
import app.models.contract_share  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# .env 기반 DB URL 동적 주입
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
