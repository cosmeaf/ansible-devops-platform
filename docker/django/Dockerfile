# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# PYTHONDONTWRITEBYTECODE keeps the image free of .pyc for a read-only-friendly
# filesystem; PYTHONUNBUFFERED makes container logs appear in real time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl is required by the container HEALTHCHECK below.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Dependencies are copied and installed first so that source edits do not
# invalidate the (slow) pip layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run unprivileged. /app stays root-owned and read-only to the app user;
# only the writable runtime directory is handed over.
# The workspace is created here so that the named volume mounted over it
# inherits this ownership on first use; a volume Docker creates itself lands
# root-owned and the unprivileged app cannot write a playbook to it.
RUN useradd --system --create-home --uid 10001 ansible \
 && mkdir -p /app/staticfiles /var/run/ansible /app/workspace/ansible \
 && chown -R ansible:ansible /app/staticfiles /var/run/ansible /app/workspace

USER ansible

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health/ || exit 1

# --access-logfile - sends request logs to stdout so `docker compose logs`
# shows them. Gunicorn forwards SIGTERM to workers for a clean stop.
CMD ["gunicorn", "core.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
