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
    && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY config ./config
COPY manage.py ./
# The development image carries the gates' tooling; the production image does not.
ARG INSTALL_DEV=true
# pip and setuptools are build tooling, not runtime dependencies: nothing in the app imports
# them, and `pip install .` builds in an isolated environment. Both are removed after the
# install, because G6's scan is otherwise fed by pip's own bundled bill of materials
# (`pip/_vendor/bom.cdx.json` declares setuptools 70.3.0, CVE-2025-47273, for a package this
# image does not contain). A runtime image has no use for a package installer.
RUN pip install --no-cache-dir --upgrade pip \
    && if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir ".[dev]"; \
    else pip install --no-cache-dir .; fi \
    && rm -rf /usr/local/lib/python3.12/site-packages/setuptools* \
              /usr/local/lib/python3.12/site-packages/_distutils_hack \
              /usr/local/lib/python3.12/site-packages/distutils-precedence.pth \
              /usr/local/lib/python3.12/site-packages/pip \
              /usr/local/lib/python3.12/site-packages/pip-* \
              /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12 \
    # The image must not carry either package back in: fail the build here instead of leaving
    # a scan finding that only shows up after the image is complete.
    && ! python -c 'import setuptools' > /dev/null 2>&1 \
    && ! python -c 'import pip' > /dev/null 2>&1

COPY . .

# Compiles the tracked Arabic catalogue on start; `.mo` files are never committed.
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

RUN useradd --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/media \
    && chown -R app:app /app /data

USER app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
