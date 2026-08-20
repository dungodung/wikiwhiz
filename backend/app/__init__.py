import os

from flask import Flask, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

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

    # On Toolforge (and any reverse-proxied deploy), the request actually
    # arrives from the ingress's own address -- without this,
    # request.remote_addr is the proxy's internal IP for every visitor,
    # which would make lib/page_views.py's geolocation resolve every single
    # page view to the same (wrong) country. x_for=1 trusts exactly one hop
    # of X-Forwarded-For, matching a single ingress/load balancer in front.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

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

        # Only the index.html-serving branch counts as "a page load" -- an
        # asset request (JS/CSS/images, handled above) isn't a visit on its
        # own, and this branch also catches an unmatched /api/* path (a
        # stray/probing request, not a real page view), which we skip too.
        if not path.startswith("api/"):
            from .lib.page_views import track_page_view_async

            track_page_view_async(request.remote_addr, request.headers.get("User-Agent", ""))

        return send_from_directory(static_dir, "index.html")

    return app
