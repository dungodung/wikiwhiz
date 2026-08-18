import os


def _db_uri() -> str:
    user = os.environ.get("DB_USER", "wikiwhiz")
    password = os.environ.get("DB_PASSWORD", "wikiwhiz")
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "wikiwhiz")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
    SQLALCHEMY_DATABASE_URI = _db_uri()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    WIKIWHIZ_OAUTH_CLIENT_ID = os.environ.get("WIKIWHIZ_OAUTH_CLIENT_ID", "")
    WIKIWHIZ_OAUTH_CLIENT_SECRET = os.environ.get("WIKIWHIZ_OAUTH_CLIENT_SECRET", "")
    WIKIWHIZ_OAUTH_REDIRECT_URI = os.environ.get("WIKIWHIZ_OAUTH_REDIRECT_URI", "")

    WIKIWHIZ_USER_AGENT = os.environ.get(
        "WIKIWHIZ_USER_AGENT", "WikiWhiz/0.1 (dev) requests"
    )

    DEGREES_LIVE_BFS_TIMEOUT_SEC = float(os.environ.get("DEGREES_LIVE_BFS_TIMEOUT_SEC", "4"))
    DEGREES_LIVE_BFS_NODE_CAP = int(os.environ.get("DEGREES_LIVE_BFS_NODE_CAP", "2000"))
    DEGREES_LIVE_BFS_DEPTH_CAP = int(os.environ.get("DEGREES_LIVE_BFS_DEPTH_CAP", "6"))

    LOW_POOL_THRESHOLD = int(os.environ.get("LOW_POOL_THRESHOLD", "3"))
    SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "25"))
    SMTP_DEBUG_LOG_ONLY = os.environ.get("SMTP_DEBUG_LOG_ONLY", "0") == "1"
    MAIL_FROM = os.environ.get("MAIL_FROM", "wikiwhiz@toolforge.org")
    MAINTAINER_EMAIL = os.environ.get("MAINTAINER_EMAIL", "")

    ANON_COOKIE_NAME = "wikiwhiz_anon"
    ANON_COOKIE_MAX_AGE_DAYS = 400


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URI", "sqlite:///:memory:")


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestConfig,
    "production": ProductionConfig,
}
