FROM python:3.13 AS base

# Install system dependencies
RUN apt-get update && apt-get install -y curl

# Install uv (latest)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Create virtual environment and sync Python dependencies
COPY pyproject.toml uv.lock .python-version ./
RUN uv venv && \
    uv sync
ENV VIRTUAL_ENV="/app/.venv"
ENV PATH="/app/.venv/bin:$PATH"

COPY . ./

FROM base AS prod

ENTRYPOINT ["python", "signals/main.py"]

FROM base AS dev

RUN apt-get update && apt-get install -y git

# Setup git
ARG GIT_USER_NAME
ARG GIT_USER_EMAIL
ENV GIT_USER_NAME=${GIT_USER_NAME}
ENV GIT_USER_EMAIL=${GIT_USER_EMAIL}
RUN git config --global --add safe.directory /app && \
    git config --global push.autoSetupRemote true
RUN if [ -n "$GIT_USER_NAME" ] && [ -n "$GIT_USER_EMAIL" ]; then \
    git config --global user.name "$GIT_USER_NAME" && \
    git config --global user.email "$GIT_USER_EMAIL"; \
    fi
