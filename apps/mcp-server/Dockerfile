# multi-stage build for the openproject-mcp server
# stage 1: build
ARG TARGETPLATFORM
ARG BUILDPLATFORM
FROM --platform=$BUILDPLATFORM python:3.11-alpine AS builder

WORKDIR /app

# build deps
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    rust

COPY pyproject.toml ./

# python deps
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir build

# source
COPY src/ ./src/
COPY .env.example ./

# build the wheel
RUN python -m build --wheel

# stage 2: runtime
# debian-slim because some deps (aiokafka, cryptography on certain
# platforms) ship manylinux wheels but no musllinux wheels. falling back
# to a source build in alpine wants gcc + librdkafka headers, not worth
# the pain.
FROM python:3.11-slim AS runtime

ARG VERSION=dev
ARG REVISION=unknown

LABEL org.opencontainers.image.source="https://github.com/t3ja/openproject-mcp"
LABEL org.opencontainers.image.title="openproject-mcp"
LABEL org.opencontainers.image.description="MCP server for OpenProject"
LABEL org.opencontainers.image.version="$VERSION"
LABEL org.opencontainers.image.revision="$REVISION"
LABEL org.opencontainers.image.licenses="MIT"

# non-root user
RUN groupadd -g 1001 mcpuser && \
    useradd -u 1001 -g mcpuser -s /usr/sbin/nologin -M mcpuser

WORKDIR /app

# runtime deps only
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# copy the built wheel
COPY --from=builder /app/dist/*.whl ./

# install
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir *.whl && \
    rm -f *.whl

# config template
COPY --from=builder /app/.env.example ./

# logs + data dir
RUN mkdir -p /app/logs /app/data && \
    chown -R mcpuser:mcpuser /app

# drop privileges
USER mcpuser

# env
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_FORMAT=json
ENV LOG_LEVEL=INFO

# health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from openproject_mcp_server.config import Config; Config.from_env(); print('Health check passed')" || exit 1

# port (MCP usually uses stdio, but the http transport needs one)
EXPOSE 3000

# default command
CMD ["python", "-m", "openproject_mcp_server"]

