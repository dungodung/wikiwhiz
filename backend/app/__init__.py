import os

from flask import Flask, send_from_directory

from .config import CONFIG_BY_NAME
from .extensions import db, migrate


def create_app(config_name: str = "production") -> Flask:
    # static_folder=None disables Flask's automatic static route: with
    # static_url_path="" that route would match "/<path:filename>", the same
    # shape as our own catch-all below, and (being registered first) would
    # win the match and 404 on client-side routes like /stats instead of
    # falling through to the SPA index.html. We serve everything through the
    # catch-all explicitly instead.
    app = Flask(__name__, static_folder=None)
    app.config.from_object(CONFIG_BY_NAME.get(config_name, CONFIG_BY_NAME["production"]))
    static_dir = os.path.join(app.root_path, "static")

    db.init_app(app)
    migrate.init_app(app, db, directory="backend/migrations")

    from . import models  # noqa: F401 registers models with SQLAlchemy metadata

    from .blueprints.admin.routes import admin_bp
    from .blueprints.auth.routes import auth_bp
    from .blueprints.game.routes import game_bp
    from .blueprints.info.routes import info_bp
    from .blueprints.stats.routes import stats_bp

    app.register_blueprint(game_bp, url_prefix="/api/game")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(stats_bp, url_prefix="/api/stats")
    app.register_blueprint(info_bp, url_prefix="/api/info")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        if path and os.path.exists(os.path.join(static_dir, path)):
            return send_from_directory(static_dir, path)
        return send_from_directory(static_dir, "index.html")

    return app
