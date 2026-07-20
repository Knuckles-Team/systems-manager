FROM python:3-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1
COPY --from=ghcr.io/astral-sh/uv:0.11.7@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a /uv /uvx /bin/

ARG HOST=127.0.0.1
ARG PORT=8000
ARG TRANSPORT="stdio"
ARG AUTH_TYPE="none"

ENV HOST=${HOST} \
    PORT=${PORT} \
    TRANSPORT=${TRANSPORT} \
    AUTH_TYPE=${AUTH_TYPE} \
    PYTHONUNBUFFERED=1 \
    HOME=/home/systems-manager \
    XDG_CACHE_HOME=/workspace/.cache \
    XDG_CONFIG_HOME=/workspace/.config \
    XDG_DATA_HOME=/workspace/.local/share \
    SYSTEMS_MANAGER_FILESYSTEM_ROOT=/workspace \
    PATH="/home/systems-manager/.local/bin:/usr/local/bin:${PATH}" \
    UV_HTTP_TIMEOUT=3600 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=0

# Install only bounded local-debug dependencies; avoid remote shell installers.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ripgrep tree fd-find nano build-essential cmake libssl-dev libcurl4-openssl-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Compile and install package in-place
RUN uv pip install --system --upgrade --verbose --no-cache --break-system-packages --prerelease=allow .[agent]

RUN groupadd --system --gid 10001 systems-manager \
    && useradd --system --uid 10001 --gid 10001 --home-dir /home/systems-manager --create-home systems-manager \
    && mkdir -p /workspace \
    && chown systems-manager:systems-manager /workspace

USER 10001:10001
WORKDIR /workspace
CMD ["systems-manager-mcp"]
