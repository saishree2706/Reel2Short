"""SQLite database setup with SQLAlchemy."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables."""
    # Import models here to ensure they are registered with Base
    from .models import video_asset  # noqa: F401
    from .models import processing_job  # noqa: F401
    from .models import youtube_credential  # noqa: F401
    from .models import youtube_upload  # noqa: F401
    Base.metadata.create_all(bind=engine)
