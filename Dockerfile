FROM python:3.11-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --without dev

COPY . .

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
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["python", "main.py"]
