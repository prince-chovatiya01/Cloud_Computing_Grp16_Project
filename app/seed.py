"""
seed.py — idempotent seed runner for the Mini-Netflix media catalogue.

Running this multiple times is safe: it uses INSERT … ON CONFLICT DO NOTHING.
Can be invoked directly:  python -m app.seed
Or called from the application lifespan on startup (in development only).
"""
import asyncio
import logging

from sqlalchemy import text

from app.database import AsyncSessionLocal, engine, Base

logger = logging.getLogger(__name__)

# ── Seed data ────────────────────────────────────────────────────────────────
MEDIA_ROWS = [
    (1,  "Stranger Things",        "Sci-Fi / Horror",  2016, 8.7, "Kids uncover supernatural mysteries in 1980s Indiana."),
    (2,  "Breaking Bad",           "Drama / Crime",    2008, 9.5, "A chemistry teacher turns drug lord after a cancer diagnosis."),
    (3,  "The Crown",              "Drama / History",  2016, 8.6, "Chronicles the reign of Queen Elizabeth II."),
    (4,  "Dark",                   "Sci-Fi / Thriller",2017, 8.8, "A time-travel conspiracy unfolds across four German families."),
    (5,  "Money Heist",            "Crime / Thriller", 2017, 8.2, "Criminals execute an elaborate robbery on the Spanish Mint."),
    (6,  "Squid Game",             "Drama / Thriller", 2021, 8.0, "Debt-ridden contestants compete in deadly childhood games."),
    (7,  "Ozark",                  "Crime / Drama",    2017, 8.4, "A financial advisor launders money for a Mexican cartel."),
    (8,  "The Witcher",            "Fantasy / Action", 2019, 8.2, "A mutated monster-hunter navigates a morally complex world."),
    (9,  "Black Mirror",           "Sci-Fi / Anthology",2011,8.8, "Anthology series exploring dark futures shaped by technology."),
    (10, "House of Cards",         "Drama / Politics", 2013, 8.7, "A ruthless politician schemes his way to the presidency."),
    (11, "Narcos",                 "Crime / Biography",2015, 8.8, "The true story of the rise and fall of Pablo Escobar."),
    (12, "Mindhunter",             "Crime / Drama",    2017, 8.6, "FBI agents interview serial killers to solve cold cases."),
    (13, "Altered Carbon",         "Sci-Fi / Noir",    2018, 8.0, "In a future where consciousness is transferable, a soldier investigates a murder."),
    (14, "Peaky Blinders",         "Crime / Drama",    2013, 8.8, "A gangster family rises to power in 1920s Birmingham."),
    (15, "The Last Kingdom",       "Action / History", 2015, 8.5, "A Saxon warrior fights for his homeland against Viking invasions."),
]

RECOMMENDATION_ROWS = [
    # (media_id, score)  — higher score = stronger recommendation
    (2,  0.98),
    (4,  0.96),
    (9,  0.95),
    (11, 0.94),
    (14, 0.93),
    (12, 0.91),
    (1,  0.90),
    (3,  0.87),
    (7,  0.85),
    (6,  0.83),
    (10, 0.81),
    (5,  0.79),
    (15, 0.77),
    (8,  0.74),
    (13, 0.71),
]


async def run_seed() -> None:
    """Create tables (if absent) and insert seed rows idempotently."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for row in MEDIA_ROWS:
            await session.execute(
                text(
                    "INSERT INTO media (id, title, genre, release_year, rating, description) "
                    "VALUES (:id, :title, :genre, :release_year, :rating, :description) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": row[0], "title": row[1], "genre": row[2],
                    "release_year": row[3], "rating": row[4], "description": row[5],
                },
            )

        for media_id, score in RECOMMENDATION_ROWS:
            await session.execute(
                text(
                    "INSERT INTO recommendations (media_id, score) "
                    "VALUES (:media_id, :score) "
                    "ON CONFLICT (media_id) DO NOTHING"
                ),
                {"media_id": media_id, "score": score},
            )

        await session.commit()

    logger.info("Seed complete: %d media items, %d recommendations.", len(MEDIA_ROWS), len(RECOMMENDATION_ROWS))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_seed())
