FROM python:3.13 AS base

# Install uv
# https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


FROM base AS development

# uv sync is handled by postCreateCommand: building the venv here would lead it
# to be overwritten by the mount. This means the uv sync is not part of the
# Dockerfile and, thus, not cached. But it's fine as long as it's not too long.


FROM base AS prod

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock .python-version ./

RUN uv sync
ENV VIRTUAL_ENV="/app/.venv"
ENV PATH="/app/.venv/bin:$PATH"

COPY . ./

ENTRYPOINT ["python", "signals/main.py"]
