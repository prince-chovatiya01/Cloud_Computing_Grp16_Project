"""
catalogue.py - Movie catalogue blueprint with circuit-breaker integration.

Routes:
  GET /movies        - paginated movie list, optional genre filter
  GET /movies/<id>   - single movie lookup
  GET /              - home page with trending + recommendations
"""
import os

from flask import Blueprint, jsonify, request

from . import db

bp = Blueprint("catalogue", __name__)

SERVICE = os.environ.get("SERVICE", "monolith")
BREAKER = os.environ.get("BREAKER", "on")
RECS_URL = os.environ.get("RECS_URL", "http://127.0.0.1:5002")

BREAKER_FAIL_MAX = int(os.environ.get("BREAKER_FAIL_MAX", "5"))
BREAKER_RESET_S = int(os.environ.get("BREAKER_RESET_S", "10"))
RECS_TIMEOUT = float(os.environ.get("RECS_TIMEOUT", "0.25"))

_breaker = None

if SERVICE != "monolith" and BREAKER == "on":
    try:
        import pybreaker
        _breaker = pybreaker.CircuitBreaker(
            fail_max=BREAKER_FAIL_MAX,
            reset_timeout=BREAKER_RESET_S,
        )
    except ImportError:
        pass


class RecommendationsUnavailable(Exception):
    pass


def _recs_for_user(user):
    """Fetch recommendations - in-process for monolith, HTTP for services."""
    if SERVICE == "monolith":
        from . import recommendations
        return recommendations.compute(user), "personal"

    import requests

    def _call():
        timeout = 5.0 if BREAKER != "on" else RECS_TIMEOUT
        r = requests.get(f"{RECS_URL}/recommendations/{user}", timeout=timeout)
        r.raise_for_status()
        return r.json().get("items", [])

    if _breaker:
        try:
            items = _breaker.call(_call)
            return items, "personal"
        except Exception:
            from . import recommendations
            return recommendations.popular(), "fallback"
    else:
        try:
            items = _call()
            return items, "personal"
        except Exception as exc:
            raise RecommendationsUnavailable(str(exc))


@bp.route("/movies")
def list_movies():
    page = int(request.args.get("page", 1))
    per_page = 20
    genre = request.args.get("genre")
    offset = (page - 1) * per_page

    with db.connection() as conn:
        if genre:
            rows = db.query(
                conn,
                "SELECT * FROM movies WHERE genre = %s ORDER BY rating DESC LIMIT %s OFFSET %s",
                (genre, per_page, offset),
            )
        else:
            rows = db.query(
                conn,
                "SELECT * FROM movies ORDER BY rating DESC LIMIT %s OFFSET %s",
                (per_page, offset),
            )
    return jsonify(page=page, count=len(rows), items=rows)


@bp.route("/movies/<int:movie_id>")
def get_movie(movie_id):
    with db.connection() as conn:
        rows = db.query(conn, "SELECT * FROM movies WHERE id = %s", (movie_id,))
    if not rows:
        return jsonify(error="not found"), 404
    return jsonify(rows[0])


@bp.route("/")
def home():
    user = request.args.get("user", "user1")
    with db.connection() as conn:
        trending = db.query(
            conn, "SELECT * FROM movies ORDER BY rating DESC LIMIT 10"
        )

    recs, source = _recs_for_user(user)

    resp = jsonify(trending=trending, recommendations=recs)
    resp.headers["X-Recs-Source"] = source
    return resp


@bp.errorhandler(RecommendationsUnavailable)
def handle_recs_unavailable(exc):
    return jsonify(error="recommendations service unavailable", detail=str(exc)), 502
