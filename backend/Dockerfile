ARG PYTHON_IMAGE=python:3.11-slim-bookworm
FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
COPY contracts/ /app/contracts/
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt \
    && python -m pip install --no-cache-dir --no-deps /app/contracts

COPY backend/ /app/backend/
RUN groupadd --system --gid 10001 testflow \
    && useradd --system --uid 10001 --gid testflow --home-dir /app testflow \
    && mkdir -p /app/media/private /app/staticfiles \
    && chown -R testflow:testflow /app/media /app/staticfiles
WORKDIR /app/backend
USER testflow

FROM base AS api
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "60", "--graceful-timeout", "30", "--access-logfile", "-"]

FROM base AS worker
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY infra/sandboxed_soffice.py /usr/local/bin/sandboxed-soffice
RUN chmod 755 /usr/local/bin/sandboxed-soffice
USER testflow
CMD ["celery", "-A", "config", "worker", "--loglevel=INFO", "--concurrency=2", "--max-tasks-per-child=50"]
