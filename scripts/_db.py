"""Shared DB session helper for the standalone content-authoring scripts.

These scripts run outside the Flask app context (invoked directly by Claude
Code or cron), but reuse the canonical SQLAlchemy models from backend/app so
there's a single source of truth for the schema -- no hand-written SQL
duplicating column definitions.

Reads the same DB_* / .env configuration as the Flask app.
"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


def _db_uri() -> str:
    user = os.environ.get("DB_USER", "wikiwhiz")
    password = os.environ.get("DB_PASSWORD", "wikiwhiz")
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "wikiwhiz")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


_engine = None
_Session = None


def get_session():
    global _engine, _Session
    if _Session is None:
        _engine = create_engine(_db_uri(), pool_pre_ping=True)
        _Session = sessionmaker(bind=_engine)
    return _Session()


@contextmanager
def session_scope():
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
