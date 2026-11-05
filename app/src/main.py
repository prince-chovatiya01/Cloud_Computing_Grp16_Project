"""
main.py - Flask application factory for Mini-Netflix.

The SERVICE environment variable selects which blueprints the process serves:
  monolith       - catalogue + recommendations + auth together
  catalogue      - catalogue blueprint only
  recommendations - recommendations blueprint only
  auth           - auth blueprint only
"""
import os
import socket

from flask import Flask, jsonify

from . import db


def create_app(service=None):
    service = service or os.environ.get("SERVICE", "monolith")
    valid = {"monolith", "catalogue", "recommendations", "auth"}
    if service not in valid:
        raise ValueError(f"Unknown SERVICE={service!r}, expected one of {valid}")

    app = Flask(__name__)
    app.json.sort_keys = False

    instance_id = os.environ.get("INSTANCE_ID", socket.gethostname())

    db.init()

    # Register blueprints based on service mode
    if service in ("monolith", "catalogue"):
        from .catalogue import bp as catalogue_bp
        app.register_blueprint(catalogue_bp)
    if service in ("monolith", "recommendations"):
        from .recommendations import bp as recommendations_bp
        app.register_blueprint(recommendations_bp)
    if service in ("monolith", "auth"):
        from .auth import bp as auth_bp
        app.register_blueprint(auth_bp)

    @app.route("/health")
    def health():
        try:
            db.ping()
            return jsonify(status="ok", service=service, instance=instance_id)
        except Exception as exc:
            return jsonify(
                status="db-error", service=service,
                instance=instance_id, detail=str(exc)
            ), 503

    @app.after_request
    def add_served_by(response):
        response.headers["X-Served-By"] = f"{instance_id}/{service}"
        return response

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Dev server only - containers should use gunicorn
    create_app().run(host="0.0.0.0", port=port, threaded=True)
