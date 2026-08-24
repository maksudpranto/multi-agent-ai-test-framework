from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


def _normalize_db_url(url: str) -> str:
    """SQLAlchemy 2.0 only accepts the ``postgresql://`` scheme, but hosts like
    Render/Heroku hand out ``postgres://``. Rewrite it so a copied-and-pasted
    DATABASE_URL just works."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


DB_URL = _normalize_db_url(settings.database_url)
_is_sqlite = DB_URL.startswith("sqlite")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Free-tier Postgres drops idle connections; check one is alive before use so
    # the first request after an idle spell doesn't fail on a stale connection.
    pool_pre_ping=not _is_sqlite,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
