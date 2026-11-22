FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg/ffprobe are required by the media pipeline (docs/background-jobs.md); curl is used
# by the container health checks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY config ./config
COPY manage.py ./
# The development image carries the gates' tooling; the production image does not.
ARG INSTALL_DEV=true
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir ".[dev]"; \
    else pip install --no-cache-dir .; fi

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/media \
    && chown -R app:app /app /data

USER app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
