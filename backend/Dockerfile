# Task 3 (Dockerfile + custom image): the API service image.
#
# Three targets share one dependency layer:
#   base     installs the pinned requirements once
#   runtime  the image docker-compose.yml actually serves (non-root)
#   test     same code + requirements-dev.txt, runs the existing pytest suite
#
# Keep `--target runtime` out of the day-to-day path; `docker compose build` picks it
# from the compose file. Pin the interpreter to 3.11 to match .github/workflows/ci.yml.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

# Copied before the source so editing app code does not re-download pandas and numpy.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

# ---------------------------------------------------------------- runtime ----
FROM base AS runtime

ENV ENV=dev \
    STORAGE_BACKEND=local \
    STORAGE_ROOT=./storage \
    SERVERLESS=false

RUN useradd --create-home --uid 1001 appuser \
    && mkdir -p /app/backend/storage \
    && chown -R appuser:appuser /app/backend

USER appuser
EXPOSE 8000

# Uvicorn with one worker on purpose: the login rate limiter keeps its counters in
# process memory unless Redis is configured, so N workers would multiply the limit.
# Scale-out happens at the Auto Scaling Group instead, behind the load balancer.
HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# ------------------------------------------------------------------- test ----
FROM base AS test

RUN pip install --no-cache-dir -r requirements-dev.txt

COPY tests ./tests
ENV ENV=test DATABASE_URL="sqlite+pysqlite:///:memory:" SECRET_KEY=container-test-secret

CMD ["pytest", "-q", "--cov=app", "--cov-report=term-missing"]
