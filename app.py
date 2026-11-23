"""InterviewIQ - application factory.  Run with:  python app.py   (or: flask --app app run)"""
from __future__ import annotations

import logging
import secrets

from flask import Flask, jsonify, render_template, request, session

from config import Config
from db import close_db, init_db


def create_app(overrides: dict | None = None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    Config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)

    from routes.api import bp as api_bp
    from routes.web import bp as web_bp
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.before_request
    def csrf_protect():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not sent or not secrets.compare_digest(sent, session["csrf"]):
                if request.path.startswith("/api/"):
                    return jsonify(error="Your session expired. Refresh the page and try again."), 400
                return render_template("error.html", code=400, message="Security token missing or expired. Go back, refresh and retry."), 400

    @app.context_processor
    def inject_globals():
        from services import llm
        return {"csrf_token": session.get("csrf", ""), "llm_on": llm.is_available()}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self)")
        return resp

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found."), 404
        return render_template("error.html", code=404, message="We couldn't find that page."), 404

    @app.errorhandler(413)
    def too_large(_e):
        if request.path.startswith("/api/"):
            return jsonify(error="The upload is too large."), 413
        return render_template("error.html", code=413, message="That upload is too large."), 413

    @app.errorhandler(500)
    def server_error(_e):
        logging.getLogger("interviewiq").exception("Unhandled error")
        if request.path.startswith("/api/"):
            return jsonify(error="Something went wrong on our side. Your saved answers are safe; please retry."), 500
        return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500

    return app


if __name__ == "__main__":
    import os
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
