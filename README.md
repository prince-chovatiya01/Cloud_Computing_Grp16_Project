# Mini-Netflix: Migrate, Then Break It on Purpose
### IT457 Cloud Computing — Group 16

**Team:** Prince Chovatiya · Ayush Patel · Rishit Raj Jain

A small, reproducible cloud proof-of-concept demonstrating:
- Local Docker-based application with PostgreSQL
- Lift-and-shift deployment to AWS EC2
- Modernization with RDS, ALB and Auto Scaling
- Controlled chaos engineering experiments
- Measurable comparison of latency, errors, recovery time and cost

---

## Project structure

```
.
├── app/
│   ├── main.py              # FastAPI app factory + lifespan
│   ├── config.py            # env-based settings (pydantic-settings)
│   ├── database.py          # async SQLAlchemy engine
│   ├── models.py            # ORM: media, recommendations
│   ├── seed.py              # idempotent 15-item dataset
│   ├── middleware.py        # X-Process-Time-Ms + structured logs
│   └── routers/
│       ├── health.py        # GET /health
│       ├── catalog.py       # GET /catalog
│       └── recommendations.py  # GET /recommendations (resilience-aware)
├── tests/
│   ├── conftest.py          # SQLite in-memory fixtures (no Docker needed)
│   ├── test_health.py
│   ├── test_catalog.py
│   └── test_recommendations.py
├── infra/                   # Phase 2: Terraform for EC2/RDS/ALB
├── docker-compose.yml
├── Dockerfile               # two-stage, non-root user
├── requirements.txt
├── pytest.ini
└── .env.example
```

---

## Quick start (local — Docker Compose)

```bash
# 1. Copy and optionally edit environment variables
cp .env.example .env

# 2. Start PostgreSQL + API (first run builds the image)
docker compose up --build

# 3. Verify
curl http://localhost:8000/health
curl http://localhost:8000/catalog
curl http://localhost:8000/recommendations
curl http://localhost:8000/docs   # interactive OpenAPI UI
```

The app seeds 15 media items and 15 recommendation scores on every startup (idempotent).

---

## Running tests (no Docker needed)

```bash
# Install dependencies (once)
pip install -r requirements.txt aiosqlite

# Run all tests
pytest
```

Tests use SQLite in-memory — no PostgreSQL container required.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + DB ping (includes `db_latency_ms`) |
| GET | `/catalog` | Media catalogue (`?genre=Drama`, `?limit=10`) |
| GET | `/recommendations` | Resilience-aware recommendations |
| GET | `/docs` | Interactive OpenAPI documentation |

### Resilience behaviour (`/recommendations`)

| Condition | Behaviour | `source` field |
|-----------|-----------|----------------|
| Normal | Recommendations from DB | `recommendations` |
| Query exceeds timeout | Top-rated catalogue items | `fallback_top_rated` |
| Complete DB failure | Static hard-coded list | `fallback_static` |

The `source` and `fallback_reason` fields in every response let you observe degradation in dashboards.

---

## Fault injection (local experiments only)

Enable in `.env`:
```
ENABLE_FAULT_INJECTION=true
```

Then use query params:
```bash
# Simulate a 2-second recommendation delay → triggers fallback
curl "http://localhost:8000/recommendations?simulate_delay=2000"

# Simulate a complete failure → returns static fallback
curl "http://localhost:8000/recommendations?simulate_failure=true"
```

> **Security:** These params return HTTP 403 when `ENABLE_FAULT_INJECTION` is `false` (the default).
> Never enable this flag in a public deployment.

---

## Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...localhost...` | Full SQLAlchemy async URL |
| `APP_ENV` | `development` | Environment label |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `ENABLE_FAULT_INJECTION` | `false` | Enable fault-injection query params |
| `RECOMMENDATION_TIMEOUT_MS` | `500` | Timeout before fallback activates |

---

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| **M1** | Local app — Docker Compose, 3 endpoints, seed, tests | ✅ Complete |
| **M2** | AWS lift-and-shift — EC2, RDS, ALB, Auto Scaling (Terraform) | ⏳ Next |
| **M3** | Chaos experiments + latency/cost comparison report | ⏳ Phase 3 |

---

## Security notes

- No credentials are hardcoded anywhere in the application.
- `.env` is in `.gitignore` — only `.env.example` is committed.
- The Docker image runs as a non-root user (`appuser`).
- PostgreSQL is not exposed publicly in the Compose setup (port binding is for local dev only).
- AWS RDS will be in a private subnet (no public endpoint) — Terraform handles this in Phase 2.