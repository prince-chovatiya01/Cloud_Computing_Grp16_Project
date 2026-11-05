"""
auth.py - Authentication blueprint with HMAC token generation.

POST /login accepts JSON {username, password} and returns a signed token.
Seeded test accounts share the password "password123".
"""
import hmac
import hashlib
import os
import time

from flask import Blueprint, jsonify, request

from . import db

bp = Blueprint("auth", __name__)

TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "dev-only-secret")


@bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    username = body.get("username", "")
    password = body.get("password", "")

    with db.connection() as conn:
        rows = db.query(conn, "SELECT pwhash FROM users WHERE username = %s", (username,))

    if not rows:
        return jsonify(error="invalid credentials"), 401

    expected = rows[0]["pwhash"]
    actual = db.hash_password(username, password)

    if not hmac.compare_digest(expected, actual):
        return jsonify(error="invalid credentials"), 401

    # Build a simple signed token: payload:signature
    expiry = int(time.time()) + 3600
    payload = f"{username}:{expiry}"
    sig = hmac.new(
        TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    return jsonify(token=f"{payload}:{sig}")
