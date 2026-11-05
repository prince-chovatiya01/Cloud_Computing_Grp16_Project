"""
recommendations.py - Recommendation blueprint with fault-injection hooks.

Routes:
  GET  /recommendations/<user>  - personalised top-10 by genre affinity
  GET  /admin/fault             - view current fault settings
  POST /admin/fault             - set fault parameters (latency_ms, error_rate)
  DELETE /admin/fault           - clear fault settings

Fault injection is gated behind FAULTS_ENABLED=1 for chaos experiment E3.
"""
import json
import os
import random
import time
import zlib

from flask import Blueprint, jsonify, request

from . import db

bp = Blueprint("recommendations", __name__)

FAULTS_ENABLED = os.environ.get("FAULTS_ENABLED", "0") == "1"
FAULT_FILE = os.environ.get("FAULT_FILE", "/tmp/fault.json")


def _load_faults():
    try:
        with open(FAULT_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _apply_fault_hook():
    """Inject latency and errors based on shared fault config."""
    if not FAULTS_ENABLED:
        return None
    faults = _load_faults()
    latency_ms = faults.get("latency_ms", 0)
    error_rate = faults.get("error_rate", 0.0)
    if latency_ms > 0:
        time.sleep(latency_ms / 1000.0)
    if error_rate > 0 and random.random() < error_rate:
        return jsonify(error="injected fault"), 500
    return None


def compute(user):
    """In-process recommendation: pick top-10 movies from user's favourite genre."""
    genre_idx = zlib.crc32(user.encode()) % len(db.GENRES)
    fav_genre = db.GENRES[genre_idx]
    with db.connection() as conn:
        rows = db.query(
            conn,
            "SELECT * FROM movies WHERE genre = %s ORDER BY rating DESC LIMIT 10",
            (fav_genre,),
        )
    return rows


def popular():
    """Fallback: top-10 movies by rating across all genres."""
    with db.connection() as conn:
        return db.query(conn, "SELECT * FROM movies ORDER BY rating DESC LIMIT 10")


@bp.route("/recommendations/<user>")
def get_recommendations(user):
    fault_resp = _apply_fault_hook()
    if fault_resp is not None:
        return fault_resp
    items = compute(user)
    return jsonify(user=user, count=len(items), items=items)


@bp.route("/admin/fault", methods=["GET", "POST", "DELETE"])
def admin_fault():
    if not FAULTS_ENABLED:
        return jsonify(error="fault injection disabled"), 404

    if request.method == "GET":
        return jsonify(_load_faults())

    if request.method == "DELETE":
        try:
            os.remove(FAULT_FILE)
        except FileNotFoundError:
            pass
        return jsonify(status="cleared")

    # POST
    data = request.get_json(silent=True) or {}
    with open(FAULT_FILE, "w") as f:
        json.dump(data, f)
    return jsonify(status="set", faults=data)
