FROM python:3.11-alpine3.22 AS builder

WORKDIR /opt/arangodb-mcp

RUN apk upgrade --no-cache && \
    pip install --no-cache-dir poetry==2.1.3 && \
    poetry config virtualenvs.in-project true

COPY pyproject.toml poetry.lock ./
COPY README.md LICENSE ./
COPY src ./src
RUN poetry install --no-interaction --no-ansi --only main --no-root && \
    poetry build --format wheel && \
    .venv/bin/pip install --no-deps dist/*.whl && \
    .venv/bin/python -c "import arangodb_mcp; import importlib.resources as r; assert r.files('arangodb_mcp.catalog').joinpath('tools.yaml').is_file()" && \
    .venv/bin/pip uninstall --yes pip setuptools wheel

FROM python:3.11-alpine3.22 AS runtime

RUN apk upgrade --no-cache && \
    python -m pip uninstall --yes pip setuptools wheel && \
    addgroup -S mcp && \
    adduser -S -D -H -G mcp -h /nonexistent mcp && \
    mkdir -p /app && \
    chmod 0555 /app

WORKDIR /app
COPY --from=builder --chown=root:root /opt/arangodb-mcp/.venv /opt/arangodb-mcp/.venv
RUN chmod -R a-w /opt/arangodb-mcp/.venv

ENV PATH="/opt/arangodb-mcp/.venv/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV LOG_LEVEL=INFO

# SECURITY: streamable-http transport requires MCP_AUTH_TOKEN when binding non-loopback.
# Set at runtime, e.g.:
#   docker run -e MCP_AUTH_TOKEN=$(openssl rand -hex 32) ...
# Without it, the server will refuse to start on a non-loopback host.

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2)"]

USER mcp

CMD ["arangodb-mcp"]
