import os

from flask import Flask

from . import db
from .routes import bp


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        # RAILWAY_DATABASE_PATH is what the existing Railway deployment sets.
        DATABASE_PATH=os.environ.get("DATABASE_PATH") or os.environ.get("RAILWAY_DATABASE_PATH", "portal.db"),
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    app.register_blueprint(bp)
    return app
