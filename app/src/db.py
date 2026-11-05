"""
db.py - Database abstraction supporting both PostgreSQL and SQLite.

Handles connection pooling for Postgres (via psycopg2 threaded pool),
falls back to file-based SQLite for local development.
Seeds 1000 movies and 100 users on init for a realistic catalogue.
"""
import hashlib
import os
import random
import sqlite3
import threading
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Database selection: Postgres when DATABASE_URL is set, else SQLite
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "")
_USE_PG = DATABASE_URL.startswith("postgres")

if _USE_PG:
    import psycopg2
    from psycopg2 import pool as pg_pool

_pool = None
_local = threading.local()

DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "8"))
SQLITE_PATH = os.environ.get("SQLITE_PATH", "app.db")

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _pg_dsn():
    return DATABASE_URL

def _get_pool():
    global _pool
    if _pool is None:
        _pool = pg_pool.ThreadedConnectionPool(
            1, DB_POOL_MAX, dsn=_pg_dsn()
        )
    return _pool

@contextmanager
def connection():
    if _USE_PG:
        p = _get_pool()
        conn = p.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            try:
                conn.reset()
            except Exception:
                p.putconn(conn, close=True)
            else:
                p.putconn(conn)
    else:
        conn = sqlite3.connect(SQLITE_PATH, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def query(conn, sql, params=()):
    """Execute a query and return rows as dicts."""
    if not _USE_PG:
        sql = sql.replace("%s", "?")
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    return rows


# ---------------------------------------------------------------------------
# Password hashing (demo only - SHA-256 of username:password)
# ---------------------------------------------------------------------------

def hash_password(username: str, password: str) -> str:
    return hashlib.sha256(f"{username}:{password}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
GENRES = [
    "Action", "Comedy", "Drama", "Horror", "Sci-Fi",
    "Romance", "Thriller", "Documentary", "Animation", "Fantasy",
]

def _generate_seed_data():
    rng = random.Random(42)
    movies = []
    for i in range(1, 1001):
        genre = GENRES[i % len(GENRES)]
        year = rng.randint(1990, 2025)
        rating = round(rng.uniform(1.0, 10.0), 1)
        movies.append((i, f"Movie_{i:04d}", genre, year, rating))

    users = []
    pw = hash_password("seed", "password123")
    for i in range(1, 101):
        users.append((f"user{i}", pw))
    return movies, users

SEED_MOVIES, SEED_USERS = _generate_seed_data()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init():
    """Create tables and seed data. Retries up to 30 times for Postgres."""
    import time

    for attempt in range(30):
        try:
            with connection() as conn:
                cur = conn.cursor()
                if _USE_PG:
                    cur.execute("SELECT pg_advisory_lock(12345)")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS movies (
                        id       INTEGER PRIMARY KEY,
                        title    TEXT    NOT NULL,
                        genre    TEXT    NOT NULL,
                        year     INTEGER NOT NULL,
                        rating   REAL    NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        pwhash   TEXT NOT NULL
                    )
                """)
                if _USE_PG:
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_movies_genre_rating
                        ON movies (genre, rating DESC)
                    """)

                for m in SEED_MOVIES:
                    if _USE_PG:
                        cur.execute(
                            "INSERT INTO movies (id, title, genre, year, rating) "
                            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", m
                        )
                    else:
                        cur.execute(
                            "INSERT OR IGNORE INTO movies (id, title, genre, year, rating) "
                            "VALUES (?,?,?,?,?)", m
                        )

                for u in SEED_USERS:
                    if _USE_PG:
                        cur.execute(
                            "INSERT INTO users (username, pwhash) "
                            "VALUES (%s,%s) ON CONFLICT DO NOTHING", u
                        )
                    else:
                        cur.execute(
                            "INSERT OR IGNORE INTO users (username, pwhash) "
                            "VALUES (?,?)", u
                        )

                if _USE_PG:
                    cur.execute("SELECT pg_advisory_unlock(12345)")
                cur.close()
                conn.commit()
            return
        except Exception as exc:
            if attempt < 29:
                time.sleep(2)
            else:
                raise RuntimeError(f"DB init failed after 30 attempts: {exc}")


def ping():
    """Health check - execute SELECT 1."""
    with connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
