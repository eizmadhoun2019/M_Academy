FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg/ffprobe are required by the media pipeline (docs/background-jobs.md); curl is used
# by the container health checks. The base image lags Debian's security fixes, so the
# packages it already ships are upgraded in the same layer: G6's image scan only reports
# findings that have a fix, and a stale base is the usual source of them.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY config ./config
COPY manage.py ./
# The development image carries the gates' tooling; the production image does not.
ARG INSTALL_DEV=true
# pip itself is not a project dependency, so `pip-audit` never sees it; trivy does.
RUN pip install --no-cache-dir --upgrade pip \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir ".[dev]"; \
    else pip install --no-cache-dir .; fi

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/media \
    && chown -R app:app /app /data

USER app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
